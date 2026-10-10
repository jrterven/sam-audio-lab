export type Region = { sign: "+" | "-"; start: number; end: number };
export type Point = { x: number; y: number; label: 0 | 1 };
export type Annotation = {
  frame: number;
  points: Point[];
  detection_id?: string;
  tracking_id?: string;
  candidate?: number;
};
export type Recipe = {
  media_id: string;
  start: number;
  end: number;
  model: "small" | "base" | "large";
  prompt: string;
  regions: Region[];
  tracking_id: string | null;
  seed: number;
};
export type Media = {
  id: string;
  name: string;
  status: string;
  duration: number;
  video: boolean;
  width: number;
  height: number;
  peaks: number[];
  error?: string;
};
export type Job = {
  id: string;
  created: number;
  operation: string;
  status: string;
  stage: string;
  message: string;
  progress?: number;
  result?: any;
};
export type Draft = {
  mediaId: string;
  start: number;
  end: number;
  prompt: string;
  model: Recipe["model"];
  regions: Region[];
  trackingId: string | null;
  visualText: string;
  annotations: Annotation[];
  clipId: string | null;
  resultId: string | null;
};
export const fileUrl = (path: string, download = false) =>
  "/api/files/" +
  path.split("/").map(encodeURIComponent).join("/") +
  (download ? "?download=true" : "");
export async function api<T = any>(
  path: string,
  body?: unknown,
  method = "POST",
): Promise<T> {
  const response = await fetch(
    "/api" + path,
    body === undefined
      ? undefined
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((e: any) => e.msg).join(" · ")
          : "No se pudo completar la operación.",
    );
  return data;
}
export const time = (seconds: number) =>
  `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${(seconds % 60).toFixed(2).padStart(5, "0")}`;
export const seconds = (value: number | undefined) =>
  value == null ? "—" : `${value.toFixed(2)} s`;
