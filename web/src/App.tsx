import { useEffect, useRef, useState } from "react";
import {
  AudioLines,
  Upload,
  Play,
  Pause,
  ArrowUpRight,
  Plus,
  Minus,
  MousePointer2,
  Scan,
  RefreshCw,
  Download,
  X,
  Check,
  Loader2,
  Clock3,
  ChevronDown,
  Copy,
  Film,
  Volume2,
  SlidersHorizontal,
  History,
  FolderOpen,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";
import {
  api,
  fileUrl,
  seconds,
  time,
  type Media,
  type Job,
  type Region,
  type Recipe,
  type Draft,
  type Annotation,
} from "./types";
import { Timeline } from "./Timeline";

const initial: Draft = {
  mediaId: "",
  start: 0,
  end: 5,
  prompt: "",
  model: "small",
  regions: [],
  trackingId: null,
  visualText: "",
  annotations: [],
  clipId: null,
  resultId: null,
};
const terminal = new Set(["done", "error", "cancelled", "interrupted"]);
export default function App() {
  const [draft, setDraft] = useState<Draft>(initial),
    [ready, setReady] = useState(false),
    [media, setMedia] = useState<Media[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [models, setModels] = useState<any[]>([]);
  const [error, setError] = useState(""),
    [uploading, setUploading] = useState(false),
    [tab, setTab] = useState<"text" | "visual">("text"),
    [tool, setTool] = useState<"+" | "-" | null>(null),
    [pointLabel, setPointLabel] = useState<0 | 1 | null>(null);
  const [detectionId, setDetectionId] = useState<string | null>(null),
    [candidate, setCandidate] = useState(0),
    [track, setTrack] = useState<"original" | "target" | "residual">(
      "original",
    ),
    [current, setCurrent] = useState(0),
    [playing, setPlaying] = useState(false),
    [audio, setAudio] = useState<HTMLAudioElement | null>(null),
    [exportId, setExportId] = useState<string | null>(null);
  const video = useRef<HTMLVideoElement>(null),
    fileInput = useRef<HTMLInputElement>(null),
    handled = useRef(new Set<string>()),
    boot = useRef(false);
  const selected = media.find((m) => m.id === draft.mediaId),
    clipJob = jobs.find((j) => j.id === draft.clipId),
    result = jobs.find((j) => j.id === draft.resultId)?.result,
    clip = clipJob?.status === "done" ? clipJob.result : result ? {
      audio: result.files.original, video: result.video, duration: result.duration,
      peaks: result.peaks, width: result.video_width, height: result.video_height,
    } : null;
  const videoWidth =
      clip?.width || result?.video_width || selected?.width || 16,
    videoHeight = clip?.height || result?.video_height || selected?.height || 9;
  const tracking = jobs.find((j) => j.id === draft.trackingId),
    detection = jobs.find((j) => j.id === detectionId);
  const busy = jobs.find((j) => !terminal.has(j.status)),
    runs = jobs.filter(
      (j) => j.operation === "separate" && j.status === "done",
    ),
    frame = Math.max(
      0,
      Math.min(
        Math.ceil((draft.end - draft.start) * 25) - 1,
        Math.floor(current * 25 + 0.001),
      ),
    );
  const source = result?.files?.[track] || (clip?.audio ?? ""),
    url = source ? fileUrl(source) : "",
    videoUrl = result?.video || clip?.video;
  const edit = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));
  const execute = async (fn: () => Promise<any>) => {
    setError("");
    try {
      return await fn();
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  };
  const recipe = (): Recipe => ({
    media_id: draft.mediaId,
    start: draft.start,
    end: draft.end,
    model: draft.model,
    prompt: draft.prompt,
    regions: draft.regions,
    tracking_id: draft.trackingId,
    seed: 42,
  });
  const addJob = (j: Job) =>
    setJobs((old) => [j, ...old.filter((x) => x.id !== j.id)]);
  const refresh = async () => {
    const s = await api("/state");
    setMedia(s.media);
    setJobs(s.jobs);
    return s;
  };
  useEffect(() => {
    if (boot.current) return;
    boot.current = true;
    execute(async () => {
      const s = await refresh();
      const saved = s.projects.find((p: any) => p.id === "workspace");
      if (saved?.draft)
        setDraft({
          ...initial,
          ...saved.draft,
          end: Number.isFinite(saved.draft.end) ? saved.draft.end : 5,
        });
      setModels((await api("/models")).audio);
      setReady(true);
    });
    const events = new EventSource("/api/events");
    events.onmessage = (e) => setJobs(JSON.parse(e.data));
    events.onerror = () => {};
    return () => events.close();
  }, []);
  useEffect(() => {
    if (!ready) return;
    const timer = setTimeout(() => {
      api("/projects/workspace", { draft }, "PUT").catch((e) =>
        setError(e.message),
      );
    }, 500);
    return () => clearTimeout(timer);
  }, [draft, ready]);
  useEffect(() => {
    for (const j of jobs) {
      if (!terminal.has(j.status) || handled.current.has(j.id)) continue;
      handled.current.add(j.id);
      if (j.status === "done" && j.operation === "separate")
        api("/models")
          .then((m) => setModels(m.audio))
          .catch(() => {});
      if (j.status === "error" && j.created > Date.now() / 1000 - 60)
        setError(j.message);
      if (j.operation === "import" && j.status !== "done")
        api("/state")
          .then((s) => setMedia(s.media))
          .catch(() => {});
      if (j.status === "done" && j.operation === "import")
        execute(async () => {
          const s = await refresh();
          const newest = s.media.find((m: Media) => m.status === "ready");
          if (newest && !draft.mediaId) chooseMedia(newest);
        });
    }
  }, [jobs]);
  useEffect(() => {
    if (clipJob?.status === "error") setError(clipJob.message);
  }, [clipJob?.status]);
  useEffect(() => {
    if (result) setTrack("target");
  }, [draft.resultId, result?.metadata]);
  useEffect(() => {
    if (!audio) return;
    const sync = () => {
      setCurrent(audio.currentTime);
      if (
        video.current &&
        Math.abs(video.current.currentTime - audio.currentTime) > 0.12
      )
        video.current.currentTime = audio.currentTime;
    };
    audio.addEventListener("timeupdate", sync);
    const ended = () => setPlaying(false);
    audio.addEventListener("ended", ended);
    return () => {
      audio.removeEventListener("timeupdate", sync);
      audio.removeEventListener("ended", ended);
    };
  }, [audio]);
  useEffect(() => {
    if (!audio || !url) return;
    const position = audio.currentTime;
    audio.pause();
    video.current?.pause();
    setPlaying(false);
    const loaded = () => {
      audio.currentTime = Math.min(position, audio.duration || 0);
      setCurrent(audio.currentTime);
      if (video.current) video.current.currentTime = audio.currentTime;
    };
    audio.addEventListener("loadedmetadata", loaded, { once: true });
    audio.src = url;
    audio.load();
    return () => audio.removeEventListener("loadedmetadata", loaded);
  }, [url, audio]);
  const seek = (t: number) => {
    if (audio) audio.currentTime = t;
    if (video.current) video.current.currentTime = t;
    setCurrent(t);
  };
  const play = () =>
    execute(async () => {
      if (!audio) return;
      if (playing) {
        audio.pause();
        video.current?.pause();
        setPlaying(false);
      } else {
        await audio.play();
        if (video.current) {
          video.current.currentTime = audio.currentTime;
          await video.current.play();
        }
        setPlaying(true);
      }
    });
  const chooseMedia = (m: Media) => {
    setDraft({
      ...initial,
      mediaId: m.id,
      end: Number.isFinite(m.duration) ? Math.min(5, m.duration) : 5,
    });
    setDetectionId(null);
    setTrack("original");
    seek(0);
    setTab("text");
  };
  const upload = async (file: File) => {
    setUploading(true);
    await execute(async () => {
      const body = new FormData();
      body.append("file", file);
      const r = await fetch("/api/media", { method: "POST", body });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail);
      setMedia((m) => [data.media, ...m]);
      setDraft({ ...initial, mediaId: data.media.id });
      addJob(data.job);
    });
    setUploading(false);
  };
  // Imported files have their metadata only after the import worker completes.
  useEffect(() => {
    if (
      selected?.status === "importing" &&
      jobs.some((j) => j.operation === "import" && j.status === "done")
    ) {
      api("/state")
        .then((s) => setMedia(s.media))
        .catch(() => {});
    }
  }, [jobs]);
  useEffect(() => {
    if (
      selected?.status === "ready" &&
      !draft.clipId &&
      draft.end > selected.duration
    )
      edit({ end: Math.min(5, selected.duration) });
  }, [selected?.status]);
  const prepare = () =>
    execute(async () => {
      const j = await api<Job>("/clips", recipe());
      addJob(j);
      edit({ clipId: j.id, resultId: null });
      setTrack("original");
      seek(0);
    });
  const crop = (patch: Partial<Draft>) => {
    edit({
      ...patch,
      clipId: null,
      resultId: null,
      trackingId: null,
      regions: [],
      annotations: [],
    });
    setDetectionId(null);
    setTrack("original");
    seek(0);
  };
  const run = () =>
    execute(async () => {
      const j = await api<Job>("/separate", recipe());
      addJob(j);
      edit({ resultId: j.id });
    });
  const visualRequest = () => ({
    media_id: draft.mediaId,
    start: draft.start,
    end: draft.end,
    frame,
    text: draft.visualText,
    annotations: draft.annotations,
  });
  const detect = () =>
    execute(async () => {
      const j = await api<Job>("/vision/detect", visualRequest());
      addJob(j);
      setDetectionId(j.id);
      setCandidate(0);
    });
  const selectCandidate = () => {
    if (!detectionId || !detection?.result) return;
    const f = detection.result.frame;
    edit({
      annotations: [
        ...draft.annotations.filter((a) => a.frame !== f),
        { frame: f, points: [], detection_id: detectionId, candidate },
      ],
      trackingId: null,
    });
    seek(f / 25);
  };
  const clickObject = (e: React.MouseEvent<HTMLDivElement>) => {
    if (pointLabel === null || !clip || busy) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const point = {
      x: Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)),
      label: pointLabel,
    };
    const existing = draft.annotations.find((a) => a.frame === frame);
    const next: Annotation = {
      ...(existing || { frame, points: [] }),
      tracking_id:
        tracking?.status === "done" ? tracking.id : existing?.tracking_id,
      points: [...(existing?.points || []), point],
    };
    edit({
      annotations: [
        ...draft.annotations.filter((a) => a.frame !== frame),
        next,
      ],
      trackingId: null,
    });
  };
  const follow = () =>
    execute(async () => {
      const j = await api<Job>("/vision/track", visualRequest());
      addJob(j);
      edit({ trackingId: j.id });
      setDetectionId(null);
      setPointLabel(null);
    });
  const restore = (j: Job, duplicate = false) => {
    seek(0);
    const r = j.result.recipe;
    setDraft({
      ...initial,
      mediaId: r.media_id,
      start: r.start,
      end: r.end,
      model: r.model,
      prompt: r.prompt,
      regions: r.regions,
      trackingId: r.tracking_id,
      annotations:
        jobs.find((x) => x.id === r.tracking_id)?.result?.annotations || [],
      visualText:
        jobs.find((x) => x.id === r.tracking_id)?.result?.request?.text || "",
      resultId: duplicate ? null : j.id,
    });
    setTrack(duplicate ? "original" : "target");
    setDetectionId(null);
    setCurrent(0);
    if (duplicate)
      execute(async () => {
        const c = await api<Job>("/clips", r);
        addJob(c);
        edit({ clipId: c.id });
      });
  };
  const exportVideo = () =>
    execute(async () => {
      const j = await api<Job>("/exports", {
        run_id: draft.resultId,
        track: track === "original" ? "target" : track,
      });
      addJob(j);
      setExportId(j.id);
    });
  const exported = jobs.find((j) => j.id === exportId);
  const activeMask =
    tracking?.status === "done"
      ? `/api/masks/${tracking.id}/${Math.min(frame, tracking.result.count - 1)}.png`
      : detection?.status === "done" &&
          detection.result.count > 0 &&
          frame === detection.result.frame
        ? `/api/masks/${detection.id}/${candidate}.png`
        : null;
  const currentPoints =
    draft.annotations.find((a) => a.frame === frame)?.points || [];
  const lastProblem = jobs.find(
    (j) =>
      j.id === draft.resultId ||
      j.id === draft.trackingId ||
      j.id === detectionId,
  );
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">
            <AudioLines size={24} />
          </span>
          <div>
            SAM Audio <span className="brand-light">Lab</span>
            <span className="brand-caption">
              UN LABORATORIO PARA ESCUCHAR DIFERENTE
            </span>
          </div>
        </div>
        <div className="header-right">
          <span className="local-badge">
            <i />
            Procesamiento local
          </span>
          <span className="version">EXPERIMENTAL / 01</span>
        </div>
      </header>
      <div className="workspace-heading">
        <div>
          <span className="eyebrow">TU ESPACIO DE EXPERIMENTACIÓN</span>
          <h1>
            Encuentra el sonido.
            <br className="mobile-break" /> Separa el resto.
          </h1>
          <p>Texto, tiempo o imagen. Tú eliges cómo aislarlo.</p>
        </div>
        <button
          className="button secondary"
          onClick={() => fileInput.current?.click()}
          disabled={uploading}
        >
          <Upload size={16} />
          {uploading ? "Subiendo…" : "Cargar archivo"}
        </button>
        <input
          ref={fileInput}
          type="file"
          hidden
          accept="audio/*,video/*,.mkv,.mov"
          onChange={(e) => {
            if (e.target.files?.[0]) upload(e.target.files[0]);
            e.target.value = "";
          }}
        />
      </div>
      {error && (
        <div className="alert" role="alert">
          <span>{error}</span>
          <button aria-label="Cerrar error" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      <main className="editor-grid">
        <section className="workspace panel">
          <div className="panel-bar">
            <div className="panel-label">
              <span className="number">01</span> Fuente{" "}
              <span className="file-name">
                {selected?.name || "Sin archivo"}
              </span>
            </div>
            {selected && (
              <select
                aria-label="Archivo actual"
                value={draft.mediaId}
                onChange={(e) => {
                  const m = media.find((m) => m.id === e.target.value);
                  if (m) chooseMedia(m);
                }}
              >
                {media.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            )}
          </div>
          {!selected ? (
            <div
              className="empty-source"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
              }}
            >
              <div className="ambient-wave">
                {Array.from({ length: 45 }, (_, i) => (
                  <i
                    key={i}
                    style={{
                      height:
                        14 +
                        Math.sin(i * 0.6) ** 2 * 50 +
                        Math.sin(i * 0.3) ** 2 * 30,
                    }}
                  />
                ))}
              </div>
              <div className="upload-symbol">
                <Upload size={24} />
              </div>
              <h2>Todo empieza con un sonido</h2>
              <p>
                Arrastra tu audio o video aquí.
                <br />
                Selecciona hasta 30 segundos para experimentar.
              </p>
              <button
                className="button primary"
                onClick={() => fileInput.current?.click()}
              >
                Elegir archivo <ArrowUpRight size={16} />
              </button>
              <button
                className="text-button"
                onClick={() =>
                  execute(async () => {
                    const s = await api("/example", {});
                    chooseMedia(s.media);
                    if (s.job) addJob(s.job);
                  })
                }
              >
                O probar con un video de ejemplo
              </button>
              <span className="format-hint">
                WAV · MP3 · FLAC · MP4 · MOV · WEBM
              </span>
            </div>
          ) : (
            <>
              <div className="crop-bar">
                <span>
                  <SlidersHorizontal size={14} /> Fragmento a procesar
                </span>
                <label>
                  Desde{" "}
                  <input
                    aria-label="Inicio del fragmento"
                    type="number"
                    min={0}
                    step={0.1}
                    value={draft.start}
                    onChange={(e) => crop({ start: Number(e.target.value) })}
                  />
                  <small>s</small>
                </label>
                <label>
                  Hasta{" "}
                  <input
                    aria-label="Fin del fragmento"
                    type="number"
                    min={0.04}
                    max={selected.duration}
                    step={0.1}
                    value={draft.end}
                    onChange={(e) => crop({ end: Number(e.target.value) })}
                  />
                  <small>s</small>
                </label>
                <button
                  className="button small secondary"
                  disabled={!!busy || selected.status !== "ready"}
                  onClick={prepare}
                >
                  {clip ? "Actualizar" : "Preparar clip"}
                </button>
              </div>
              <div
                className="source-overview"
                title="Duración total del archivo"
              >
                {(selected.peaks || [])
                  .filter(
                    (_, i) =>
                      i %
                        Math.max(
                          1,
                          Math.floor((selected.peaks || []).length / 160),
                        ) ===
                      0,
                  )
                  .slice(0, 160)
                  .map((p, i) => (
                    <i key={i} style={{ height: Math.max(2, p * 45) }} />
                  ))}
                <div
                  className="crop-indicator"
                  style={{
                    left: `${(draft.start / (selected.duration || 1)) * 100}%`,
                    width: `${((draft.end - draft.start) / (selected.duration || 1)) * 100}%`,
                  }}
                />
              </div>
              <div className="source-duration">
                <span>0:00</span>
                <span>Archivo completo · {time(selected.duration || 0)}</span>
              </div>
              <div className={"viewer " + (selected.video ? "" : "audio-only")}>
                {videoUrl ? (
                  <div
                    className={
                      "video-surface " +
                      (pointLabel !== null ? "selecting" : "")
                    }
                    style={{
                      aspectRatio: `${videoWidth}/${videoHeight}`,
                      width: `min(100%, ${(390 * videoWidth) / videoHeight}px)`,
                    }}
                    onClick={clickObject}
                  >
                    <video
                      ref={video}
                      src={fileUrl(videoUrl)}
                      muted
                      playsInline
                      onLoadedMetadata={() => {
                        if (video.current) video.current.currentTime = current;
                      }}
                    />
                    {activeMask && (
                      <img
                        className="mask-overlay"
                        src={activeMask}
                        alt="Máscara del objeto seleccionado"
                      />
                    )}
                    {currentPoints.map((p, i) => (
                      <span
                        key={i}
                        className={
                          "point " + (p.label ? "positive" : "negative")
                        }
                        style={{ left: p.x * 100 + "%", top: p.y * 100 + "%" }}
                      >
                        {p.label ? "+" : "−"}
                      </span>
                    ))}
                    <span className="viewer-tag">
                      <Film size={12} /> VIDEO · 25 FPS
                    </span>
                    {pointLabel !== null && (
                      <span className="click-tip">
                        Clic para {pointLabel ? "incluir" : "excluir"} ·
                        fotograma {frame}
                      </span>
                    )}
                  </div>
                ) : (
                  <div className="audio-placeholder">
                    <AudioLines size={64} strokeWidth={1} />
                    <p>
                      {selected.status === "importing"
                        ? "Analizando archivo…"
                        : ["error", "cancelled", "interrupted"].includes(
                              selected.status,
                            )
                          ? selected.error
                          : clip
                            ? "Tu sonido, en primer plano."
                            : "Prepara el fragmento para comenzar."}
                    </p>
                  </div>
                )}
              </div>
              {(clip || result) && (
                <>
                  <div className="transport">
                    <button
                      className="play-button"
                      aria-label={playing ? "Pausar" : "Reproducir"}
                      onClick={play}
                    >
                      {playing ? (
                        <Pause size={19} fill="currentColor" />
                      ) : (
                        <Play size={19} fill="currentColor" />
                      )}
                    </button>
                    <span className="timecode">
                      {time(current)}{" "}
                      <span>/ {time(draft.end - draft.start)}</span>
                    </span>
                    <div
                      className="track-switch"
                      aria-label="Pista de reproducción"
                    >
                      {(["original", "target", "residual"] as const).map(
                        (t) => (
                          <button
                            key={t}
                            disabled={t !== "original" && !result}
                            className={track === t ? "active" : ""}
                            onClick={() => {
                              setPlaying(false);
                              audio?.pause();
                              video.current?.pause();
                              setTrack(t);
                            }}
                          >
                            {t === "original"
                              ? "Original"
                              : t === "target"
                                ? "Aislado"
                                : "Residual"}
                          </button>
                        ),
                      )}
                    </div>
                    <Volume2 size={16} className="volume-icon" />
                  </div>
                  <div className="timeline-toolbar">
                    <span>REGIONES DE REFERENCIA</span>
                    <div>
                      <button
                        aria-label="Mover cursor"
                        className={tool === null ? "selected" : ""}
                        onClick={() => setTool(null)}
                      >
                        <MousePointer2 size={13} />
                      </button>
                      <button
                        className={tool === "+" ? "selected positive-text" : ""}
                        onClick={() => setTool(tool === "+" ? null : "+")}
                      >
                        <Plus size={14} /> Presente
                      </button>
                      <button
                        className={tool === "-" ? "selected negative-text" : ""}
                        onClick={() => setTool(tool === "-" ? null : "-")}
                      >
                        <Minus size={14} /> Ausente
                      </button>
                    </div>
                  </div>
                  <Timeline
                    key={`${draft.mediaId}:${draft.start}:${draft.end}`}
                    media={audio}
                    url={url}
                    peaks={result?.peaks || clip?.peaks || selected.peaks || []}
                    duration={draft.end - draft.start}
                    offset={draft.start}
                    regions={draft.regions}
                    tool={tool}
                    onRegions={(regions) => edit({ regions })}
                    onSeek={seek}
                  />
                  <p className="timeline-help">
                    {tool
                      ? "Arrastra sobre la onda para marcar una región."
                      : "Marca dónde aparece o no aparece el sonido que buscas."}{" "}
                    Las regiones guían la separación; no recortan la salida.
                  </p>
                  {!!draft.regions.length && (
                    <div className="region-list">
                      {draft.regions.map((r, i) => (
                        <span
                          className={
                            "region-chip " +
                            (r.sign === "+" ? "positive" : "negative")
                          }
                          key={i}
                        >
                          {r.sign} {time(r.start - draft.start)}–
                          {time(r.end - draft.start)}
                          <button
                            aria-label="Eliminar región"
                            onClick={() =>
                              edit({
                                regions: draft.regions.filter(
                                  (_, k) => k !== i,
                                ),
                              })
                            }
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </section>
        <aside className="controls panel">
          <div className="panel-bar">
            <div className="panel-label">
              <span className="number">02</span> Define tu sonido
            </div>
            <SlidersHorizontal size={16} />
          </div>
          <div className="controls-body">
            <div className="tabs">
              <button
                className={tab === "text" ? "active" : ""}
                onClick={() => setTab("text")}
              >
                <AudioLines size={15} /> Texto y tiempo
              </button>
              <button
                className={tab === "visual" ? "active" : ""}
                onClick={() => setTab("visual")}
              >
                <Scan size={15} /> Objeto visual
              </button>
            </div>
            {tab === "text" ? (
              <div className="prompt-section">
                <label className="field-label" htmlFor="prompt">
                  ¿Qué quieres escuchar?
                </label>
                <textarea
                  id="prompt"
                  value={draft.prompt}
                  onChange={(e) => edit({ prompt: e.target.value })}
                  placeholder="Describe el sonido que quieres aislar…"
                  rows={4}
                />
                <p className="field-hint">
                  Una descripción breve y específica. Prueba con ejemplos en
                  inglés.
                </p>
                <div className="suggestions">
                  {["man speaking", "dog barking", "guitar"].map((s) => (
                    <button onClick={() => edit({ prompt: s })} key={s}>
                      {s}
                      <Plus size={11} />
                    </button>
                  ))}
                </div>
                <div className="tip-card">
                  <span className="tip-icon">
                    <Plus size={17} />
                  </span>
                  <div>
                    <strong>Afina con la línea del tiempo</strong>
                    <p>
                      Marca tramos donde el sonido está presente o ausente para
                      darle más contexto al modelo.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="visual-controls">
                <label className="field-label" htmlFor="visual-prompt">
                  Encuentra un objeto en este fotograma
                </label>
                <input
                  id="visual-prompt"
                  value={draft.visualText}
                  onChange={(e) => edit({ visualText: e.target.value })}
                  placeholder="the person on the left"
                />
                <button
                  className="button secondary full"
                  disabled={
                    !clip ||
                    !selected?.video ||
                    !!busy ||
                    !draft.visualText.trim()
                  }
                  onClick={detect}
                >
                  <Scan size={15} /> Buscar objeto
                </button>
                <div className="point-controls">
                  <button
                    disabled={!clip || !selected?.video}
                    className={pointLabel === 1 ? "selected" : ""}
                    onClick={() => setPointLabel(pointLabel === 1 ? null : 1)}
                  >
                    <Plus size={14} /> Incluir
                  </button>
                  <button
                    disabled={!clip || !selected?.video}
                    className={pointLabel === 0 ? "selected" : ""}
                    onClick={() => setPointLabel(pointLabel === 0 ? null : 0)}
                  >
                    <Minus size={14} /> Excluir
                  </button>
                  <button
                    title="Limpiar selección"
                    onClick={() => {
                      edit({ annotations: [], trackingId: null });
                      setDetectionId(null);
                    }}
                  >
                    <RefreshCw size={14} />
                  </button>
                </div>
                <p className="field-hint">
                  Pausa el video y haz clic sobre el objeto. Puedes corregirlo
                  en cualquier fotograma.
                </p>
                <div className="frame-nav">
                  <button
                    aria-label="Fotograma anterior"
                    disabled={!clip}
                    onClick={() => seek(Math.max(0, (frame - 1) / 25))}
                  >
                    <ArrowLeft size={13} />
                  </button>
                  <span>
                    Fotograma {frame} · {time(current)}
                  </span>
                  <button
                    aria-label="Fotograma siguiente"
                    disabled={!clip}
                    onClick={() =>
                      seek(
                        Math.min(
                          draft.end - draft.start - 0.04,
                          (frame + 1) / 25,
                        ),
                      )
                    }
                  >
                    <ArrowRight size={13} />
                  </button>
                </div>
                {detection?.status === "done" && (
                  <div className="candidate-picker">
                    {detection.result.count ? (
                      <>
                        <label>
                          Objeto{" "}
                          <select
                            value={candidate}
                            onChange={(e) => {
                              setCandidate(Number(e.target.value));
                              seek(detection.result.frame / 25);
                            }}
                          >
                            {Array.from(
                              { length: detection.result.count },
                              (_, i) => (
                                <option key={i} value={i}>
                                  {i + 1} ·{" "}
                                  {(detection.result.scores[i] * 100).toFixed(
                                    0,
                                  )}
                                  %
                                </option>
                              ),
                            )}
                          </select>
                        </label>
                        <button
                          className="button small secondary"
                          onClick={selectCandidate}
                        >
                          <Check size={13} /> Elegir
                        </button>
                      </>
                    ) : (
                      <p>
                        No se encontraron objetos. Prueba otra descripción o usa
                        clics.
                      </p>
                    )}
                  </div>
                )}
                <button
                  className="button secondary full"
                  disabled={!draft.annotations.length || !!busy}
                  onClick={follow}
                >
                  <Scan size={15} />
                  {tracking?.status === "done"
                    ? "Repetir seguimiento"
                    : "Seguir objeto en el clip"}
                </button>
                <p className="tracking-status">
                  {tracking?.status === "done"
                    ? `${tracking.result.visible_frames}/${tracking.result.count} fotogramas con objeto · ${tracking.result.device.toUpperCase()}`
                    : `${draft.annotations.length} fotogramas anotados`}
                </p>
                {tracking?.status === "done" && (
                  <button
                    className="text-button"
                    onClick={() => edit({ trackingId: null, annotations: [] })}
                  >
                    Quitar guía visual
                  </button>
                )}
              </div>
            )}
            <div className="model-section">
              <div className="field-label">
                Modelo de separación <span className="badge">SAM AUDIO</span>
              </div>
              <div className="model-select">
                <select
                  aria-label="Modelo SAM Audio"
                  value={draft.model}
                  onChange={(e) =>
                    edit({ model: e.target.value as Recipe["model"] })
                  }
                >
                  {["small", "base", "large"].map((m) => (
                    <option key={m} value={m}>
                      {m[0].toUpperCase() + m.slice(1)}
                      {models.find((x) => x.id === m)?.cached
                        ? " · descargado"
                        : " · descarga inicial"}
                    </option>
                  ))}
                </select>
                <ChevronDown size={15} />
              </div>
              <p className="field-hint">
                {draft.model === "small"
                  ? "El punto de partida más ligero."
                  : draft.model === "base"
                    ? "Una variante intermedia para comparar."
                    : "La variante de mayor tamaño."}{" "}
                Ejecuta uno a la vez.
              </p>
              <div className="settings-line">
                <span>48 kHz · mono</span>
                <span>Semilla 42</span>
              </div>
            </div>
            <button
              className="button primary full separate"
              disabled={
                !selected ||
                selected.status !== "ready" ||
                !!busy ||
                (draft.annotations.length > 0 && tracking?.status !== "done") ||
                (!draft.prompt.trim() &&
                  !draft.regions.length &&
                  !draft.trackingId)
              }
              onClick={run}
            >
              {busy ? (
                <Loader2 size={18} className="spin" />
              ) : (
                <AudioLines size={18} />
              )}{" "}
              Separar sonido <ArrowUpRight size={17} />
            </button>
            {!busy && draft.annotations.length > 0 && tracking?.status !== "done" && (
              <p className="field-hint">Completa el seguimiento o limpia la selección visual antes de separar.</p>
            )}
            {busy ? (
              <div className="job-status" aria-live="polite">
                <div>
                  <span>{busy.message}</span>
                  <button
                    onClick={() =>
                      execute(() => api(`/jobs/${busy.id}/cancel`, {}))
                    }
                  >
                    Cancelar
                  </button>
                </div>
                <div
                  className={
                    "progress-track " +
                    (busy.progress == null ? "indeterminate" : "")
                  }
                >
                  <i
                    style={{
                      width:
                        busy.progress == null
                          ? "35%"
                          : busy.progress * 100 + "%",
                    }}
                  />
                </div>
              </div>
            ) : (
              <p className="privacy-note">
                <span className="status-dot" /> Tus archivos permanecen en esta
                computadora.
              </p>
            )}
            {lastProblem &&
              ["error", "interrupted"].includes(lastProblem.status) && (
                <div className="inline-error" role="alert">
                  {lastProblem.message}
                </div>
              )}
          </div>
        </aside>
      </main>
      {result && (
        <section className="result-panel panel">
          <div className="result-title">
            <span className="success-icon">
              <Check size={18} />
            </span>
            <div>
              <h3>Un sonido, en primer plano</h3>
              <p>
                {result.model.toUpperCase()} · {result.device.toUpperCase()} ·{" "}
                {result.duration.toFixed(2)} s de audio
              </p>
            </div>
            <a className="text-button" href={fileUrl(result.metadata, true)}>
              Metadatos <Download size={13} />
            </a>
          </div>
          <div className="metrics">
            {[
              ["Inferencia", result.timings.separate],
              ["Carga del modelo", result.timings.load],
              ["Descarga / caché", result.timings.download],
              ["Procesamiento visual", result.timings.visual],
              ["Tiempo total", result.timings.total],
            ].map(([label, value]) => (
              <div key={String(label)}>
                <span>{label}</span>
                <strong>{seconds(value as number)}</strong>
              </div>
            ))}
            <div>
              <span>Tiempo real</span>
              <strong>{result.rtf.toFixed(2)}×</strong>
            </div>
          </div>
          <div className="export-row">
            <span>
              <Download size={15} /> Lleva tu resultado
            </span>
            <a
              className="button small secondary"
              href={fileUrl(result.files.target, true)}
            >
              Aislado WAV
            </a>
            <a
              className="button small secondary"
              href={fileUrl(result.files.residual, true)}
            >
              Residual WAV
            </a>
            {result.video && (
              <button
                className="button small secondary"
                disabled={!!busy}
                onClick={exportVideo}
              >
                <Film size={14} /> Exportar video ·{" "}
                {track === "residual" ? "residual" : "aislado"}
              </button>
            )}
            {exported?.status === "done" && (
              <a
                className="button small primary"
                href={fileUrl(exported.result.file, true)}
              >
                Descargar MP4 <Download size={13} />
              </a>
            )}
          </div>
        </section>
      )}
      <section className="history-section">
        <div className="section-heading">
          <h2>
            <History size={18} /> Tus experimentos{" "}
            <span>{runs.length.toString().padStart(2, "0")}</span>
          </h2>
          <p>Guardados localmente, listos para volver a escuchar.</p>
        </div>
        {runs.length ? (
          <div className="history-table">
            <div className="history-row table-head">
              <span>FUENTE / PROMPT</span>
              <span>MODELO</span>
              <span>INFERENCIA</span>
              <span>FACTOR</span>
              <span />
            </div>
            {runs.map((j) => (
              <div
                className={
                  "history-row " + (j.id === draft.resultId ? "current" : "")
                }
                key={j.id}
              >
                <button className="history-main" onClick={() => restore(j)}>
                  <span className="history-icon">
                    <AudioLines size={17} />
                  </span>
                  <span>
                    <strong>
                      {media.find((m) => m.id === j.result.recipe.media_id)
                        ?.name || "Archivo"}
                    </strong>
                    <small>
                      {j.result.recipe.prompt || "Guía temporal / visual"} ·{" "}
                      {time(j.result.recipe.start)}–{time(j.result.recipe.end)}
                    </small>
                  </span>
                </button>
                <span className="model-tag">{j.result.model}</span>
                <span className="mono">
                  {seconds(j.result.timings.separate)}
                </span>
                <span className="mono muted">{j.result.rtf.toFixed(2)}×</span>
                <button
                  className="button small ghost"
                  onClick={() => restore(j, true)}
                >
                  <Copy size={13} /> Duplicar
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-history">
            <FolderOpen size={22} />
            <p>Tu primera separación aparecerá aquí.</p>
            <span>Cambia de modelo y compara tus resultados a tu ritmo.</span>
          </div>
        )}
      </section>
      <footer>
        <span>
          <AudioLines size={13} /> SAM Audio Lab
        </span>
        <span>HECHO PARA EXPLORAR, ESCUCHAR Y COMPARAR.</span>
        <span>Powered by Meta SAM Audio</span>
      </footer>
      <audio ref={setAudio} preload="auto" />
    </div>
  );
}
