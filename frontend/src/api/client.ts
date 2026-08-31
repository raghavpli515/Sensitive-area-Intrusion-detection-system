// Typed wrapper around the backend API. The base URL comes from an env var,
// empty/unset meaning "same origin as the page" (used when the backend
// serves the built frontend itself — see app.main's static-file mount) —
// so the same build works in local dev, Docker Compose, and a single-
// container deploy (e.g. Hugging Face Spaces) without code changes.

export interface Detection {
  track_id: number;
  class_name: string;
  confidence: number;
  bbox: [number, number, number, number];
}

export interface Alert {
  frame: number;
  type: string;
  message: string;
  track_id: number | null;
  // "started": a condition just began. "ended": it just cleared (or the
  // track was lost, or processing finished while it was still active).
  // One-off events (line_breach) are always "started" with no "ended".
  event: "started" | "ended";
  duration_seconds: number | null; // set only on "ended"
}

export interface JobStatus {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  progress: number;
  error: string | null;
  total_frames: number | null;
  processed_frames: number;
  alerts: Alert[];
  output_video_url: string | null;
}

// Defaults to the local backend for zero-config `npm run dev`. Deploys that
// serve the frontend and API from the same origin (e.g. the Hugging Face
// Space image) set VITE_API_URL="" at build time to get same-origin
// requests instead — see deploy/huggingface/Dockerfile.
const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function resolveUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export async function submitVideo(file: File, confidenceThreshold: number): Promise<JobStatus> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("confidence_threshold", String(confidenceThreshold));

  const res = await fetch(resolveUrl("/infer/video"), { method: "POST", body: formData });
  if (!res.ok) {
    throw new Error((await safeErrorDetail(res)) ?? `Upload failed (HTTP ${res.status})`);
  }
  return (await res.json()) as JobStatus;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(resolveUrl(`/infer/video/${jobId}`));
  if (!res.ok) {
    throw new Error((await safeErrorDetail(res)) ?? `Failed to fetch job status (HTTP ${res.status})`);
  }
  return (await res.json()) as JobStatus;
}

async function safeErrorDetail(res: Response): Promise<string | null> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : null;
  } catch {
    return null;
  }
}

export function jobVideoUrl(jobId: string): string {
  return resolveUrl(`/infer/video/${jobId}/file`);
}

export function streamSocketUrl(): string {
  // Second arg as base: harmless when resolveUrl() already returned an
  // absolute URL (the URL constructor ignores the base then), required
  // when it returned a same-origin relative path (empty VITE_API_URL) —
  // `new URL("/ws/stream")` with no base throws.
  const url = new URL(resolveUrl("/ws/stream"), window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}
