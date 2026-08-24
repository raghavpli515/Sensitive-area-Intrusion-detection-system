import { useEffect, useRef, useState } from "react";
import { streamSocketUrl, type Alert, type Detection } from "../api/client";
import { AlertFeed } from "../components/AlertFeed";

// ~5 fps: fast enough to feel live, slow enough to keep CPU-only inference
// viable on a laptop demo. Documented, not hidden.
const CAPTURE_INTERVAL_MS = 200;

type ConnectionState = "idle" | "connecting" | "connected" | "error" | "closed";

interface StreamMessage {
  image_b64?: string;
  detections?: Detection[];
  alerts?: Alert[];
  error?: string;
}

export function LivePage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const captureCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<number | null>(null);
  const sendingRef = useRef(false);

  const [connection, setConnection] = useState<ConnectionState>("idle");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [detectionCount, setDetectionCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => stop, []);

  function stopCapture() {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  function stop() {
    stopCapture();
    socketRef.current?.close();
    socketRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setConnection("idle");
  }

  function drawFrame(imageB64: string) {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const img = new Image();
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
    };
    img.src = `data:image/jpeg;base64,${imageB64}`;
  }

  function captureAndSend() {
    const video = videoRef.current;
    const socket = socketRef.current;
    if (!video || !socket || socket.readyState !== WebSocket.OPEN) return;
    if (sendingRef.current) return; // backpressure: skip a tick rather than pile up frames

    if (!captureCanvasRef.current) {
      captureCanvasRef.current = document.createElement("canvas");
    }
    const canvas = captureCanvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx || canvas.width === 0 || canvas.height === 0) return;

    ctx.drawImage(video, 0, 0);
    sendingRef.current = true;
    canvas.toBlob(
      (blob) => {
        sendingRef.current = false;
        if (blob && socket.readyState === WebSocket.OPEN) {
          blob.arrayBuffer().then((buf) => socket.send(buf));
        }
      },
      "image/jpeg",
      0.7,
    );
  }

  async function start() {
    setErrorMessage(null);
    setAlerts([]);
    setConnection("connecting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err) {
      setConnection("error");
      setErrorMessage(
        "Could not access the camera: " + (err instanceof Error ? err.message : String(err)),
      );
      return;
    }

    const socket = new WebSocket(streamSocketUrl());
    socketRef.current = socket;

    socket.onopen = () => {
      setConnection("connected");
      intervalRef.current = window.setInterval(captureAndSend, CAPTURE_INTERVAL_MS);
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data as string) as StreamMessage;

      if (data.error) {
        setErrorMessage(data.error);
        return;
      }
      if (data.image_b64) {
        drawFrame(data.image_b64);
      }
      setDetectionCount(data.detections?.length ?? 0);
      if (data.alerts && data.alerts.length > 0) {
        setAlerts((prev) => [...prev, ...data.alerts!].slice(-300));
      }
    };

    socket.onerror = () => {
      setConnection("error");
      setErrorMessage("Live connection failed. Is the backend running?");
    };

    socket.onclose = () => {
      setConnection((current) => (current === "error" ? current : "closed"));
      stopCapture();
    };
  }

  const canStart = connection === "idle" || connection === "closed" || connection === "error";

  return (
    <section className="page">
      <h1>Live Camera Detection</h1>
      <p className="muted">
        Streams webcam frames to the backend over a WebSocket at ~5 fps and
        renders the annotated result in real time. One tracker + rule engine
        is kept alive for the whole connection, so speed/zone/line/stationary
        rules work correctly across frames instead of resetting every message.
      </p>

      <div className="live-controls">
        <span className={`status-pill status-${connection}`}>{connection}</span>
        {canStart ? (
          <button onClick={start}>Start Camera</button>
        ) : (
          <button onClick={stop}>Stop Camera</button>
        )}
        <span className="muted">{detectionCount} object(s) tracked</span>
      </div>

      {errorMessage && <p className="error-text">{errorMessage}</p>}

      <div className="live-layout">
        {/* Hidden source element feeding the capture canvas; the visible feed is the annotated canvas below. */}
        <video ref={videoRef} muted playsInline className="hidden-video" />
        <canvas ref={canvasRef} className="live-canvas" />
        <div className="live-alerts">
          <h2>Alerts</h2>
          <AlertFeed alerts={alerts} />
        </div>
      </div>
    </section>
  );
}
