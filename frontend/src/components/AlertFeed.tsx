import type { Alert } from "../api/client";

const ALERT_STYLES: Record<string, { label: string; color: string }> = {
  weapon_detected: { label: "Weapon", color: "#ef4444" },
  zone_intrusion: { label: "Zone Intrusion", color: "#f97316" },
  line_breach: { label: "Line Breach", color: "#eab308" },
  fast_movement: { label: "Fast Movement", color: "#3b82f6" },
  dropped_object: { label: "Dropped Object", color: "#a855f7" },
  group_gathering: { label: "Group Gathering", color: "#14b8a6" },
};

export function AlertFeed({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) {
    return <p className="muted">No suspicious activity detected yet.</p>;
  }

  const recent = [...alerts].slice(-200).reverse();

  return (
    <ul className="alert-feed">
      {recent.map((alert, idx) => {
        const style = ALERT_STYLES[alert.type] ?? { label: alert.type, color: "#94a3b8" };
        return (
          <li key={`${alert.frame}-${alert.type}-${alert.track_id ?? "g"}-${idx}`} className="alert-item">
            <span className="alert-badge" style={{ backgroundColor: style.color }}>
              {style.label}
            </span>
            <span className="alert-message">{alert.message}</span>
            <span className="alert-frame">frame {alert.frame}</span>
          </li>
        );
      })}
    </ul>
  );
}
