import { useMemo } from "react";
import type { Alert } from "../api/client";

const ALERT_STYLES: Record<string, { label: string; color: string }> = {
  weapon_detected: { label: "Weapon", color: "#ef4444" },
  zone_intrusion: { label: "Zone Intrusion", color: "#f97316" },
  line_breach: { label: "Line Breach", color: "#eab308" },
  fast_movement: { label: "Fast Movement", color: "#3b82f6" },
  dropped_object: { label: "Dropped Object", color: "#a855f7" },
  group_gathering: { label: "Group Gathering", color: "#14b8a6" },
};

function styleFor(type: string) {
  return ALERT_STYLES[type] ?? { label: type, color: "#94a3b8" };
}

function incidentKey(alert: Alert): string {
  return `${alert.type}:${alert.track_id ?? "group"}`;
}

/** Alerts arrive in chronological order (increasing frame). An incident is
 * "active" if it has a "started" event with no later "ended" for the same
 * (type, track) pair. */
function computeActiveIncidents(alerts: Alert[]): Alert[] {
  const open = new Map<string, Alert>();
  for (const alert of alerts) {
    const key = incidentKey(alert);
    if (alert.event === "started") {
      open.set(key, alert);
    } else {
      open.delete(key);
    }
  }
  return [...open.values()];
}

export function AlertFeed({ alerts }: { alerts: Alert[] }) {
  const active = useMemo(() => computeActiveIncidents(alerts), [alerts]);

  if (alerts.length === 0) {
    return <p className="muted">No suspicious activity detected yet.</p>;
  }

  const timeline = [...alerts].slice(-200).reverse();

  return (
    <div className="alert-timeline">
      {active.length > 0 && (
        <div className="active-incidents">
          <h3>Active now</h3>
          <ul className="alert-feed">
            {active.map((alert) => {
              const style = styleFor(alert.type);
              return (
                <li key={incidentKey(alert)} className="alert-item alert-active">
                  <span className="alert-badge" style={{ backgroundColor: style.color }}>
                    {style.label}
                  </span>
                  <span className="alert-message">{alert.message}</span>
                  <span className="alert-frame">since frame {alert.frame}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <h3 className="timeline-heading">Timeline</h3>
      <ul className="alert-feed">
        {timeline.map((alert, idx) => {
          const style = styleFor(alert.type);
          const isEnded = alert.event === "ended";
          return (
            <li
              key={`${alert.frame}-${alert.type}-${alert.track_id ?? "g"}-${alert.event}-${idx}`}
              className={`alert-item ${isEnded ? "alert-ended" : ""}`}
            >
              <span
                className="alert-badge"
                style={isEnded ? { borderColor: style.color, color: style.color } : { backgroundColor: style.color }}
              >
                {style.label}
                {isEnded ? " · ended" : ""}
              </span>
              <span className="alert-message">{alert.message}</span>
              <span className="alert-frame">
                {isEnded && alert.duration_seconds != null
                  ? `${alert.duration_seconds.toFixed(1)}s · `
                  : ""}
                frame {alert.frame}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
