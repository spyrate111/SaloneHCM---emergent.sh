import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { Megaphone, Plus, Trash2, AlertTriangle, Archive } from "lucide-react";

export default function Announcements() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);

  const load = useCallback(() => {
    api.get("/announcements", { params: { include_expired: true } })
      .then((r) => setRows(r.data)).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const remove = async (id) => {
    if (!window.confirm("Delete this announcement permanently?")) return;
    try {
      await api.delete(`/announcements/${id}`);
      toast.success("Announcement deleted");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  const active = rows.filter((r) => !r.expired);
  const archived = rows.filter((r) => r.expired);

  const Row = ({ a }) => (
    <div className="flex items-start justify-between gap-3 border-b border-[#F0EEE8] py-3 last:border-0"
      data-testid={`announcement-row-${a.id}`}>
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {a.priority === "urgent" && (
            <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full bg-[#FBE9E9] text-[#B03A2E]">
              <AlertTriangle className="w-3 h-3" /> Urgent
            </span>
          )}
          <span className="text-sm font-semibold text-[#1A1C1E]">{a.title}</span>
        </div>
        <p className="text-sm text-[#525860] mt-1 whitespace-pre-wrap">{a.body}</p>
        <div className="text-[11px] text-[#8A8F96] mt-1">
          {a.posted_by} · posted {(a.created_at || "").slice(0, 10)}
          {a.expires_at ? ` · expires ${a.expires_at}` : " · no expiry"}
        </div>
      </div>
      <button onClick={() => remove(a.id)} className="p-1.5 rounded text-[#B03A2E] hover:bg-[#FBE9E9] shrink-0"
        title="Delete" data-testid={`announcement-delete-${a.id}`}>
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );

  return (
    <div className="space-y-6" data-testid="announcements-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Notice board</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Announcements</h1>
          <p className="text-[#525860] text-sm mt-1">
            Staff see active announcements on their dashboard. Urgent ones also show as a top banner, and every post sends a push notification.
          </p>
        </div>
        <button onClick={() => setOpen(true)} data-testid="announcement-new-button"
          className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm font-medium px-4 py-2.5 rounded-md">
          <Plus className="w-4 h-4" /> New announcement
        </button>
      </div>

      {open && <AnnouncementForm onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load(); }} />}

      <section className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="announcements-active-section">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860] mb-1">Active</div>
        {active.length === 0 ? (
          <div className="text-sm text-[#686D76] py-4 flex items-center gap-2">
            <Megaphone className="w-4 h-4" /> No active announcements.
          </div>
        ) : active.map((a) => <Row key={a.id} a={a} />)}
      </section>

      <section className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="announcements-archive-section">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860] mb-1 inline-flex items-center gap-1.5">
          <Archive className="w-3.5 h-3.5" /> Archive (expired — hidden from staff)
        </div>
        {archived.length === 0 ? (
          <div className="text-sm text-[#686D76] py-4">No expired announcements yet.</div>
        ) : archived.map((a) => <Row key={a.id} a={a} />)}
      </section>
    </div>
  );
}

function AnnouncementForm({ onClose, onSaved }) {
  const [f, setF] = useState({ title: "", body: "", priority: "normal", expires_at: "" });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/announcements", { ...f, expires_at: f.expires_at || null });
      toast.success("Announcement posted — staff notified");
      onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Post failed");
    } finally { setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="bg-white border border-[#E2DFD6] rounded-lg p-6 grid grid-cols-1 sm:grid-cols-2 gap-4"
      data-testid="announcement-form">
      <label className="text-xs text-[#525860] sm:col-span-2">Title
        <input required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })}
          className="mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" data-testid="announcement-form-title" />
      </label>
      <label className="text-xs text-[#525860] sm:col-span-2">Body
        <textarea required rows={4} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })}
          className="mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" data-testid="announcement-form-body" />
      </label>
      <label className="text-xs text-[#525860]">Priority
        <select value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}
          className="mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2 text-sm capitalize" data-testid="announcement-form-priority">
          <option value="normal">normal</option>
          <option value="urgent">urgent</option>
        </select>
      </label>
      <label className="text-xs text-[#525860]">Expiry date (optional)
        <input type="date" value={f.expires_at} onChange={(e) => setF({ ...f, expires_at: e.target.value })}
          className="mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" data-testid="announcement-form-expiry" />
      </label>
      <div className="sm:col-span-2 flex gap-2">
        <button disabled={busy} className="bg-[#0A4A1E] text-white text-sm px-5 py-2.5 rounded-md disabled:opacity-50"
          data-testid="announcement-form-submit">
          {busy ? "Posting…" : "Post announcement"}
        </button>
        <button type="button" onClick={onClose} className="border border-[#E2DFD6] text-sm px-5 py-2.5 rounded-md">Cancel</button>
      </div>
    </form>
  );
}
