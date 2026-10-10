"""Text-prompted SAM Audio inference on Apple Metal, once weights are authorized."""

import argparse
import json
import time
from pathlib import Path

import soundfile as sf
import torch
from huggingface_hub import hf_hub_download
from huggingface_hub.utils import GatedRepoError
from torchcodec.decoders import AudioDecoder

from sam_audio import SAMAudio, SAMAudioProcessor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("description", help='Descripción breve, p. ej. "man speaking"')
    parser.add_argument("--model", default="facebook/sam-audio-small")
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    parser.add_argument("--seconds", type=float, default=10.0,
                        help="Procesar los primeros N segundos (predeterminado: 10)")
    parser.add_argument("--output", type=Path, default=Path("outputs/separation"))
    args = parser.parse_args()
    if not args.audio.is_file():
        parser.error(f"No existe el archivo: {args.audio}")
    if args.seconds <= 0:
        parser.error("--seconds debe ser positivo")
    if args.device == "mps" and not torch.backends.mps.is_available():
        parser.error("Metal no disponible en este proceso; prueba desde Terminal o usa --device cpu")

    # Check authorization before downloading large checkpoints or allocating the model.
    try:
        hf_hub_download(args.model, "config.json")
    except GatedRepoError:
        raise SystemExit(
            f"Acceso pendiente. Solicita acceso en https://huggingface.co/{args.model} "
            "y autentica la cuenta autorizada con: hf auth login"
        ) from None

    torch.set_num_threads(8)
    torch.manual_seed(42)
    started = time.perf_counter()
    print(f"Cargando {args.model} en {args.device}...", flush=True)
    # These optional features pull in CUDA-oriented dependencies and additional models.
    model = SAMAudio.from_pretrained(args.model, span_predictor=None,
                                    text_ranker=None, visual_ranker=None).eval().to(args.device)
    processor = SAMAudioProcessor.from_pretrained(args.model)
    load_seconds = time.perf_counter() - started
    sample_rate = processor.audio_sampling_rate
    decoder = AudioDecoder(str(args.audio), sample_rate=sample_rate, num_channels=1)
    duration = min(args.seconds, decoder.metadata.duration_seconds)
    audio = decoder.get_samples_played_in_range(0, duration).data
    batch = processor(audios=[audio], descriptions=[args.description]).to(args.device)
    if args.device == "mps":
        torch.mps.synchronize()
    started = time.perf_counter()
    print(f"Separando {audio.shape[-1] / sample_rate:.2f} segundos...", flush=True)
    with torch.inference_mode():
        result = model.separate(batch, predict_spans=False, reranking_candidates=1)
    if args.device == "mps":
        torch.mps.synchronize()
    elapsed = time.perf_counter() - started
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ("target", "residual"):
        waveform = getattr(result, name)[0].detach().float().cpu()[:audio.shape[-1]]
        if not torch.isfinite(waveform).all():
            raise RuntimeError(f"{name} contiene valores no finitos")
        sf.write(args.output / f"{name}.wav", waveform.numpy(), sample_rate, subtype="FLOAT")
    report = {"model": args.model, "device": args.device, "torch": torch.__version__,
              "prompt": args.description, "audio_seconds": audio.shape[-1] / sample_rate,
              "load_seconds": load_seconds, "separation_seconds": elapsed,
              "real_time_factor": elapsed / (audio.shape[-1] / sample_rate)}
    (args.output / "run.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print(f"Resultados: {args.output.resolve()}")


if __name__ == "__main__":
    main()
