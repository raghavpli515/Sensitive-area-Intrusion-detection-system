import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { getJobStatus, jobVideoUrl, submitVideo, type JobStatus } from "../api/client";
import { AlertFeed } from "../components/AlertFeed";
import { ConfidenceSlider } from "../components/ConfidenceSlider";
import { JobProgress } from "../components/JobProgress";

const POLL_INTERVAL_MS = 1500;

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [confidence, setConfidence] = useState(0.4);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;

    setSubmitting(true);
    setSubmitError(null);
    setJob(null);
    stopPolling();

    try {
      const created = await submitVideo(file, confidence);
      setJob(created);

      pollRef.current = window.setInterval(async () => {
        try {
          const updated = await getJobStatus(created.job_id);
          setJob(updated);
          if (updated.status === "done" || updated.status === "error") {
            stopPolling();
          }
        } catch (err) {
          stopPolling();
          setSubmitError(err instanceof Error ? err.message : "Failed to poll job status");
        }
      }, POLL_INTERVAL_MS);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="page">
      <h1>Upload Surveillance Footage</h1>
      <p className="muted">
        Upload a video to run YOLOv8 detection, DeepSORT tracking, and rule-based
        suspicious-activity alerting — restricted-zone intrusion, perimeter-line
        breach, fast movement, dropped objects, weapon detection, and group
        gathering.
      </p>

      <form className="upload-form" onSubmit={handleSubmit}>
        <input
          type="file"
          accept="video/mp4,video/avi,video/quicktime,.mp4,.avi,.mov"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <ConfidenceSlider value={confidence} onChange={setConfidence} disabled={submitting} />
        <button type="submit" disabled={!file || submitting}>
          {submitting ? "Uploading…" : "Start Detection"}
        </button>
      </form>

      {submitError && <p className="error-text">{submitError}</p>}

      {job && (
        <div className="results">
          <JobProgress job={job} />

          {job.status === "done" && job.output_video_url && (
            <video className="result-video" controls src={jobVideoUrl(job.job_id)} />
          )}

          <h2>Alerts</h2>
          <AlertFeed alerts={job.alerts} />
        </div>
      )}
    </section>
  );
}
