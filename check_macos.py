"""Check Apple Metal and SAM Audio components without downloading model weights."""

import argparse
import copy
import json
import platform
import time
from pathlib import Path

import torch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-access", action="store_true")
    parser.add_argument("--report", type=Path, default=Path("outputs/macos-check.json"))
    args = parser.parse_args()
    report = {
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "torch": torch.__version__,
        "mps_built": torch.backends.mps.is_built(),
        "mps_available": torch.backends.mps.is_available(),
        "pretrained_inference_tested": False,
    }
    print(json.dumps(report, indent=2), flush=True)
    if not report["mps_available"]:
        raise SystemExit("Metal no disponible. Ejecuta desde una Terminal con acceso a la GPU.")

    from torchcodec.decoders import AudioDecoder
    from sam_audio import SAMAudio, SAMAudioProcessor
    from sam_audio.model.codec import DACVAE
    from sam_audio.model.config import DACVAEConfig, TransformerConfig
    from sam_audio.model.transformer import DiT

    report["sam_audio_import"] = SAMAudio.__name__
    sample = Path(__file__).parent / "examples/assets/office.mp4"
    audio = AudioDecoder(str(sample), sample_rate=48000, num_channels=1).get_all_samples().data
    report["example_duration_seconds"] = audio.shape[-1] / 48000
    processor = SAMAudioProcessor(audio_hop_length=1920, audio_sampling_rate=48000)
    batch = processor(audios=[audio[:, :11520]], descriptions=["man speaking"]).to("mps")
    report["processor_device"] = str(batch.audios.device)

    # Random weights validate operators and numerical agreement, NOT separation quality.
    torch.manual_seed(42)
    torch.set_num_threads(8)
    with torch.inference_mode():
        print("Probando DACVAE (arquitectura por defecto, pesos aleatorios)...", flush=True)
        codec = DACVAE(DACVAEConfig()).eval()
        waveform = batch.audios.cpu()
        cpu_encoded = codec(waveform)
        # DACVAE generates a random watermark message on CPU on each decode.
        # Replay the RNG state so CPU and MPS compare the same watermarked audio.
        decoder_rng_state = torch.random.get_rng_state()
        cpu_decoded = codec.decode(cpu_encoded)
        codec = codec.to("mps")
        started = time.perf_counter()
        mps_encoded = codec(batch.audios)
        torch.random.set_rng_state(decoder_rng_state)
        mps_decoded = codec.decode(mps_encoded)
        torch.mps.synchronize()
        torch.testing.assert_close(mps_encoded.cpu(), cpu_encoded, rtol=2e-3, atol=2e-4)
        torch.testing.assert_close(mps_decoded.cpu(), cpu_decoded, rtol=2e-3, atol=2e-4)
        assert torch.isfinite(mps_decoded).all(), "Non-finite codec output"
        report["codec"] = {
            "device": str(mps_decoded.device),
            "cpu_mps_agree": True,
            "output_shape": list(mps_decoded.shape),
            "seconds_including_first_run_setup": time.perf_counter() - started,
        }
        del codec
        torch.mps.empty_cache()

        print("Probando DiT reducido (atención, RoPE y condicionamiento)...", flush=True)
        cfg = TransformerConfig(dim=128, n_heads=4, n_layers=2, context_dim=128,
                                out_channels=256, dropout=0.0, max_positions=128)
        cpu_dit = DiT(cfg).eval()
        mps_dit = copy.deepcopy(cpu_dit).to("mps")
        x, t, memory = torch.randn(1, 25, 128), torch.tensor([0.5]), torch.randn(1, 4, 128)
        expected = cpu_dit(x, t, memory=memory)
        actual = mps_dit(x.to("mps"), t.to("mps"), memory=memory.to("mps"))
        torch.mps.synchronize()
        torch.testing.assert_close(actual.cpu(), expected, rtol=2e-3, atol=2e-4)
        assert torch.isfinite(actual).all(), "Non-finite transformer output"
        report["dit"] = {"device": str(actual.device), "cpu_mps_agree": True,
                         "output_shape": list(actual.shape), "reduced_architecture": True}

    if args.check_access:
        from huggingface_hub import get_hf_file_metadata, get_token, hf_hub_url
        from huggingface_hub.utils import HfHubHTTPError

        report["model_access"] = {}
        for name in ("small", "base", "large"):
            repo = f"facebook/sam-audio-{name}"
            try:
                get_hf_file_metadata(hf_hub_url(repo, "config.json"), token=get_token())
                report["model_access"][repo] = "authorized"
            except HfHubHTTPError as exc:
                report["model_access"][repo] = f"HTTP {exc.response.status_code} ({type(exc).__name__})"

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)
    print(f"Informe: {args.report.resolve()}")


if __name__ == "__main__":
    main()
