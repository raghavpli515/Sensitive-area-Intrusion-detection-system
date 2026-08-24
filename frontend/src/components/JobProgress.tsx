import type { JobStatus } from "../api/client";

export function JobProgress({ job }: { job: JobStatus }) {
  const pct = Math.round(job.progress * 100);

  return (
    <div className="job-progress">
      <div className="job-progress-row">
        <span className={`status-pill status-${job.status}`}>{job.status}</span>
        <span className="muted">
          {job.processed_frames}
          {job.total_frames ? ` / ${job.total_frames}` : ""} frames
        </span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      {job.error && <p className="error-text">{job.error}</p>}
    </div>
  );
}
