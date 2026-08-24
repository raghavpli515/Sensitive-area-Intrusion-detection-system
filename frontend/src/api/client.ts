// Typed wrapper around the backend API. The base URL comes from an env var
// so the same build works in local dev (Vite proxy or direct localhost) and
// in Docker Compose (service-name hostname) without code changes.

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
  const url = new URL(resolveUrl("/ws/stream"));
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}
