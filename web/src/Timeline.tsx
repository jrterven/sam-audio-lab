import { useEffect, useRef } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.esm.js";
import type { Region } from "./types";

type Props = {
  media: HTMLAudioElement | null;
  url: string;
  peaks: number[];
  duration: number;
  offset: number;
  regions: Region[];
  tool: "+" | "-" | null;
  onRegions: (r: Region[]) => void;
  onSeek: (t: number) => void;
};
export function Timeline({
  media,
  url,
  peaks,
  duration,
  offset,
  regions,
  tool,
  onRegions,
  onSeek,
}: Props) {
  const container = useRef<HTMLDivElement>(null),
    wave = useRef<WaveSurfer | null>(null),
    plugin = useRef<RegionsPlugin | null>(null);
  const callbacks = useRef({ onRegions, onSeek });
  callbacks.current = { onRegions, onSeek };
  const drawingTool = useRef(tool);
  drawingTool.current = tool;
  const loaded = useRef(false),
    writing = useRef(false),
    regionRef = useRef(regions);
  regionRef.current = regions;
  useEffect(() => {
    if (!container.current || !media || !url) return;
    loaded.current = false;
    writing.current = true;
    const p = RegionsPlugin.create();
    plugin.current = p;
    const w = WaveSurfer.create({
      container: container.current,
      waveColor: "#829ed0",
      progressColor: "#2563eb",
      cursorColor: "#1e3a8a",
      height: 104,
      barWidth: 2,
      barGap: 2,
      barRadius: 2,
      normalize: false,
      plugins: [p],
    });
    wave.current = w;
    const sync = () => w.setTime(media.currentTime);
    media.addEventListener("timeupdate", sync);
    const publish = () => {
      if (loaded.current && !writing.current)
        callbacks.current.onRegions(
          p.getRegions().map((r) => ({
            sign: r.content?.textContent === "−" ? "-" : "+",
            start: r.start + offset,
            end: r.end + offset,
          })),
        );
    };
    w.on("interaction", (t) => callbacks.current.onSeek(t));
    p.on("region-created", (r) => {
      if (writing.current) return;
      r.setOptions({ content: drawingTool.current === "-" ? "−" : "+" });
      publish();
    });
    p.on("region-updated", publish);
    p.on("region-removed", publish);
    w.on("ready", () => {
      loaded.current = true;
      writing.current = true;
      p.clearRegions();
      for (const r of regionRef.current)
        p.addRegion({
          start: r.start - offset,
          end: r.end - offset,
          content: r.sign === "-" ? "−" : "+",
          color:
            r.sign === "+" ? "rgba(37,99,235,.18)" : "rgba(249,115,22,.20)",
          minLength: 0.04,
        });
      writing.current = false;
    });
    w.load("", [peaks.length ? peaks : [0]], duration)
      .then(sync)
      .catch((e) => console.error("Could not render the waveform", e));
    return () => {
      media.removeEventListener("timeupdate", sync);
      loaded.current = false;
      writing.current = true;
      w.destroy();
      wave.current = null;
      plugin.current = null;
    };
  }, [media, duration, offset]);
  useEffect(() => {
    const p = plugin.current;
    if (!p || !loaded.current) return;
    const actual = p.getRegions().map((r) => ({
      sign: r.content?.textContent === "−" ? "-" : "+",
      start: r.start + offset,
      end: r.end + offset,
    }));
    if (JSON.stringify(actual) === JSON.stringify(regions)) return;
    writing.current = true;
    p.clearRegions();
    for (const r of regions)
      p.addRegion({
        start: r.start - offset,
        end: r.end - offset,
        content: r.sign === "-" ? "−" : "+",
        color: r.sign === "+" ? "rgba(37,99,235,.18)" : "rgba(249,115,22,.20)",
        minLength: 0.04,
      });
    writing.current = false;
  }, [regions, offset]);
  useEffect(() => {
    if (tool && plugin.current)
      return plugin.current.enableDragSelection({
        color: tool === "+" ? "rgba(37,99,235,.18)" : "rgba(249,115,22,.20)",
        minLength: 0.04,
      });
  }, [tool, duration, offset, media]);
  return (
    <div className={"wave-wrap " + (tool ? "drawing" : "")}>
      <div ref={container} />
      <div className="ruler">
        {Array.from({ length: 7 }, (_, i) => (
          <span key={i}>{((duration * i) / 6).toFixed(1)}s</span>
        ))}
      </div>
    </div>
  );
}
