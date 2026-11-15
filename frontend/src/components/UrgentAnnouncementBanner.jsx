import { useEffect, useState } from "react";
import api from "../lib/api";
import { AlertTriangle, X } from "lucide-react";

const DISMISS_KEY = "shcm_dismissed_announcements";
const readDismissed = () => {
  try { return JSON.parse(sessionStorage.getItem(DISMISS_KEY) || "[]"); } catch { return []; }
};

/** Red top-of-screen banner for every active urgent announcement. */
export default function UrgentAnnouncementBanner() {
  const [rows, setRows] = useState([]);
  const [dismissed, setDismissed] = useState(readDismissed);

  useEffect(() => {
    api.get("/announcements")
      .then((r) => setRows(r.data.filter((a) => a.priority === "urgent")))
      .catch(() => {});
  }, []);

  const dismiss = (id) => {
    const next = [...dismissed, id];
    setDismissed(next);
    sessionStorage.setItem(DISMISS_KEY, JSON.stringify(next));
  };

  const visible = rows.filter((a) => !dismissed.includes(a.id));
  if (visible.length === 0) return null;
  return (
    <>
      {visible.map((a) => (
        <div key={a.id} role="alert" data-testid="urgent-announcement-banner"
          className="bg-[#7A1F17] text-white px-6 py-2.5 flex items-center gap-3 text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" strokeWidth={1.7} />
          <div className="flex-1 min-w-0">
            <strong>{a.title}</strong>
            <span className="opacity-90"> — {a.body.length > 140 ? `${a.body.slice(0, 140)}…` : a.body}</span>
          </div>
          <button onClick={() => dismiss(a.id)} aria-label="Dismiss announcement"
            className="p-1 rounded hover:bg-white/15 shrink-0" data-testid={`urgent-dismiss-${a.id}`}>
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </>
  );
}
