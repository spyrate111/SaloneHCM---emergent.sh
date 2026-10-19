import { useEffect, useState } from "react";
import api from "../lib/api";
import { Megaphone, AlertTriangle } from "lucide-react";

/** Dashboard notice card — active company announcements for every logged-in role. */
export default function AnnouncementsCard() {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    api.get("/announcements").then((r) => setRows(r.data)).catch(() => {});
  }, []);

  if (rows.length === 0) return null;
  return (
    <section className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="announcements-card">
      <div className="flex items-center gap-2 mb-3">
        <Megaphone className="w-4 h-4 text-[#0A4A1E]" strokeWidth={1.7} />
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Notice board</div>
      </div>
      <div className="space-y-4">
        {rows.map((a) => (
          <div key={a.id} className="border-b border-[#F0EEE8] last:border-0 pb-4 last:pb-0"
            data-testid={`announcement-notice-${a.id}`}>
            <div className="flex items-center gap-2 flex-wrap">
              {a.priority === "urgent" && (
                <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full bg-[#FBE9E9] text-[#B03A2E]">
                  <AlertTriangle className="w-3 h-3" /> Urgent
                </span>
              )}
              <span className="text-sm font-semibold text-[#1A1C1E]">{a.title}</span>
            </div>
            <p className="text-sm text-[#525860] mt-1 whitespace-pre-wrap">{a.body}</p>
            <div className="text-[11px] text-[#8A8F96] mt-1.5">
              {a.posted_by} · {(a.created_at || "").slice(0, 10)}
              {a.expires_at ? ` · expires ${a.expires_at}` : ""}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
