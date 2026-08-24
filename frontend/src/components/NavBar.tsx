export type Page = "upload" | "live";

export function NavBar({ page, onNavigate }: { page: Page; onNavigate: (page: Page) => void }) {
  return (
    <nav className="navbar">
      <div className="brand">🚨 Intrusion Detection System</div>
      <div className="nav-links">
        <button className={page === "upload" ? "active" : ""} onClick={() => onNavigate("upload")}>
          Upload Video
        </button>
        <button className={page === "live" ? "active" : ""} onClick={() => onNavigate("live")}>
          Live Camera
        </button>
      </div>
    </nav>
  );
}
