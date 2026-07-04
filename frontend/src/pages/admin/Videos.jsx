import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Video, Plus, X, Pencil, Trash2, Eye, EyeOff, GripVertical,
  Save, ExternalLink, AlertTriangle, Search, Sparkles,
} from "lucide-react";
import api from "../../lib/api";
import VideoPlayer from "../../marketing/VideoPlayer";

const CATEGORIES = [
  { id: "getting_started", label: "Getting started" },
  { id: "by_persona",      label: "By industry" },
  { id: "deep_dive",       label: "Deep dive" },
];
const PERSONAS = [
  { id: "small_business", label: "Small business" },
  { id: "midsize",        label: "Midsize" },
  { id: "enterprise",     label: "Enterprise" },
  { id: "government",     label: "Government & MDAs" },
  { id: "ngo",            label: "NGO" },
  { id: "mining",         label: "Mining" },
  { id: "banking",        label: "Banking" },
  { id: "general",        label: "All clients" },
];

const EMPTY = {
  title: "",
  summary: "",
  src: "",
  poster: "",
  duration_s: 60,
  category: "getting_started",
  persona: "general",
  chapters: [],
  sort: 100,
  published: true,
};

export default function AdminVideos() {
  const [videos, setVideos] = useState([]);
  const [editing, setEditing] = useState(null); // null | "new" | video object
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [q, setQ] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(null);

  // Drag state
  const dragId = useRef(null);
  const [hoverId, setHoverId] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await api.get("/marketing/admin/videos");
      setVideos(r.data || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load videos");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const visible = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return videos;
    return videos.filter((v) => `${v.title} ${v.summary} ${v.persona} ${v.category}`.toLowerCase().includes(t));
  }, [videos, q]);

  const startNew = () => { setEditing("new"); setForm({ ...EMPTY, sort: (videos.at(-1)?.sort ?? 100) + 10 }); };
  const startEdit = (v) => { setEditing(v); setForm({ ...EMPTY, ...v }); };
  const closeForm = () => { setEditing(null); setForm(EMPTY); };

  const onChange = (k) => (e) => {
    const raw = e?.target ? e.target.value : e;
    const v = (k === "duration_s" || k === "sort") ? Number(raw) || 0 : raw;
    setForm((f) => ({ ...f, [k]: v }));
  };

  const save = async () => {
    if (!form.title.trim() || !form.src.trim() || !form.summary.trim()) {
      toast.error("Title, summary and source URL are required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        title: form.title.trim(),
        summary: form.summary.trim(),
        src: form.src.trim(),
        poster: form.poster?.trim() || null,
        chapters: Array.isArray(form.chapters) ? form.chapters.filter((c) => c.label && typeof c.t === "number") : [],
      };
      if (editing === "new") {
        await api.post("/marketing/admin/videos", payload);
        toast.success("Video created");
      } else {
        await api.patch(`/marketing/admin/videos/${editing.id}`, payload);
        toast.success("Video updated");
      }
      closeForm();
      load();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const togglePublish = async (v) => {
    try {
      await api.patch(`/marketing/admin/videos/${v.id}`, { ...v, published: !v.published });
      toast.success(v.published ? "Video unpublished" : "Video published");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Toggle failed");
    }
  };

  const doDelete = async () => {
    if (!confirmDelete) return;
    try {
      await api.delete(`/marketing/admin/videos/${confirmDelete.id}`);
      toast.success("Video deleted");
      setConfirmDelete(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  // ---- Native HTML5 drag-to-reorder ----
  const onDragStart = (id) => { dragId.current = id; };
  const onDragOver = (e, id) => { e.preventDefault(); setHoverId(id); };
  const onDragEnd = () => { dragId.current = null; setHoverId(null); };

  const onDrop = async (targetId) => {
    const srcId = dragId.current;
    setHoverId(null);
    dragId.current = null;
    if (!srcId || srcId === targetId) return;
    const next = [...videos];
    const from = next.findIndex((v) => v.id === srcId);
    const to = next.findIndex((v) => v.id === targetId);
    if (from < 0 || to < 0) return;
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    // Re-assign sort = (index+1)*10 so we leave room to insert later
    const renumbered = next.map((v, i) => ({ ...v, sort: (i + 1) * 10 }));
    setVideos(renumbered);
    try {
      // Persist sort for the affected items only (cheap O(N) PATCH)
      await Promise.all(
        renumbered.map((v) => api.patch(`/marketing/admin/videos/${v.id}`, v))
      );
      toast.success("Order saved");
    } catch (e) {
      toast.error("Reorder failed — refreshing");
      load();
    }
  };

  // Chapters editor helpers
  const addChapter = () => setForm((f) => ({ ...f, chapters: [...f.chapters, { t: 0, label: "" }] }));
  const updateChapter = (i, k, val) => setForm((f) => ({
    ...f,
    chapters: f.chapters.map((c, j) => j === i ? { ...c, [k]: k === "t" ? Number(val) || 0 : val } : c),
  }));
  const removeChapter = (i) => setForm((f) => ({ ...f, chapters: f.chapters.filter((_, j) => j !== i) }));

  return (
    <div className="p-6 lg:p-8 max-w-[1400px] mx-auto" data-testid="admin-videos-page">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#C02719]">Marketing</div>
          <h1 className="text-[28px] font-extrabold text-[#0F2C24] flex items-center gap-2">
            <Video className="w-6 h-6" /> Video library
          </h1>
          <p className="text-[13px] text-[#525860] mt-1 max-w-[640px]">
            Public training videos surfaced on <code className="bg-[#F1EEE6] px-1 py-0.5 rounded text-[12px]">/</code> and <code className="bg-[#F1EEE6] px-1 py-0.5 rounded text-[12px]">/videos</code>.
            Drag rows to reorder. Toggle the eye icon to publish or save as draft.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9aa0a6]" />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search videos…"
              className="pl-8 pr-3 h-9 w-[220px] border border-[#EAE7DF] rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0F2C24]"
              data-testid="admin-videos-search"
            />
          </div>
          <button
            type="button"
            onClick={startNew}
            className="inline-flex items-center gap-1.5 px-4 h-9 text-[13px] font-bold bg-[#C02719] text-white rounded-full hover:bg-[#9c1f14]"
            data-testid="admin-videos-add"
          >
            <Plus className="w-3.5 h-3.5" /> New video
          </button>
        </div>
      </div>

      <div className="mt-6 grid lg:grid-cols-12 gap-6">
        {/* Table */}
        <div className="lg:col-span-7">
          <div className="bg-white border border-[#EAE7DF] rounded-xl overflow-hidden">
            <table className="w-full text-[13px]" data-testid="admin-videos-table">
              <thead className="bg-[#F1EEE6]">
                <tr>
                  <th className="text-left py-2.5 pl-3 pr-2 w-6"></th>
                  <th className="text-left py-2.5 pr-3 text-[10px] uppercase tracking-[0.1em] text-[#525860] font-bold">Title</th>
                  <th className="text-left py-2.5 pr-3 text-[10px] uppercase tracking-[0.1em] text-[#525860] font-bold">Category</th>
                  <th className="text-left py-2.5 pr-3 text-[10px] uppercase tracking-[0.1em] text-[#525860] font-bold">Persona</th>
                  <th className="text-left py-2.5 pr-3 text-[10px] uppercase tracking-[0.1em] text-[#525860] font-bold">Status</th>
                  <th className="text-right py-2.5 pr-3 text-[10px] uppercase tracking-[0.1em] text-[#525860] font-bold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 && (
                  <tr><td colSpan="6" className="text-center py-12 text-[13px] text-[#525860]">No videos {q ? "match your search" : "yet"}. Click <strong className="text-[#0F2C24]">New video</strong> to add one.</td></tr>
                )}
                {visible.map((v) => (
                  <tr
                    key={v.id}
                    draggable
                    onDragStart={() => onDragStart(v.id)}
                    onDragOver={(e) => onDragOver(e, v.id)}
                    onDrop={() => onDrop(v.id)}
                    onDragEnd={onDragEnd}
                    className={`border-t border-[#F1EEE6] cursor-move ${hoverId === v.id ? "bg-[#FFF7F0]" : "hover:bg-[#FAF8F2]"}`}
                    data-testid={`admin-video-row-${v.id}`}
                  >
                    <td className="py-2.5 pl-3 pr-2 text-[#9aa0a6]"><GripVertical className="w-3.5 h-3.5" /></td>
                    <td className="py-2.5 pr-3">
                      <div className="font-bold text-[#0F2C24] leading-tight">{v.title}</div>
                      <div className="text-[11px] text-[#525860] mt-0.5">{fmt(v.duration_s)} · sort {v.sort}</div>
                    </td>
                    <td className="py-2.5 pr-3 text-[11px]">
                      <span className="px-2 py-0.5 rounded bg-[#FAF8F2] text-[#0F2C24]">{CATEGORIES.find((c) => c.id === v.category)?.label || v.category}</span>
                    </td>
                    <td className="py-2.5 pr-3 text-[11px]">
                      <span className="px-2 py-0.5 rounded bg-[#FFE9E5] text-[#C02719]">{PERSONAS.find((p) => p.id === v.persona)?.label || v.persona}</span>
                    </td>
                    <td className="py-2.5 pr-3 text-[11px]">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded ${v.published ? "bg-[#E6F2EC] text-[#1f6f55]" : "bg-[#FAF8F2] text-[#9aa0a6]"}`}>
                        {v.published ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                        {v.published ? "Published" : "Draft"}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-right whitespace-nowrap">
                      <button
                        type="button" onClick={() => togglePublish(v)}
                        title={v.published ? "Unpublish" : "Publish"}
                        className="text-[#525860] hover:text-[#1f6f55] mr-2"
                        data-testid={`admin-video-toggle-${v.id}`}
                      >
                        {v.published ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                      <button
                        type="button" onClick={() => startEdit(v)}
                        title="Edit"
                        className="text-[#525860] hover:text-[#0F2C24] mr-2"
                        data-testid={`admin-video-edit-${v.id}`}
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        type="button" onClick={() => setConfirmDelete(v)}
                        title="Delete"
                        className="text-[#525860] hover:text-[#C02719]"
                        data-testid={`admin-video-delete-${v.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-[#9aa0a6] mt-3 flex items-center gap-1.5">
            <GripVertical className="w-3 h-3" /> Drag any row by the handle to reorder. Sort values auto-renumber to leave room for inserts.
          </p>
        </div>

        {/* Side panel — Form OR Live preview placeholder */}
        <div className="lg:col-span-5">
          {editing ? (
            <FormPanel
              form={form}
              isNew={editing === "new"}
              onChange={onChange}
              onSave={save}
              onCancel={closeForm}
              saving={saving}
              addChapter={addChapter}
              updateChapter={updateChapter}
              removeChapter={removeChapter}
            />
          ) : (
            <div className="bg-white border border-[#EAE7DF] rounded-xl p-8 text-center" data-testid="admin-videos-empty-side">
              <div className="w-12 h-12 rounded-full bg-[#FAF8F2] grid place-items-center mx-auto">
                <Sparkles className="w-6 h-6 text-[#C02719]" />
              </div>
              <p className="mt-3 text-[14px] font-bold text-[#0F2C24]">Pick a video to edit</p>
              <p className="mt-1 text-[12.5px] text-[#525860] max-w-[320px] mx-auto leading-snug">
                Click <strong className="text-[#0F2C24]">Edit</strong> on any row, or <strong className="text-[#0F2C24]">New video</strong> to paste a YouTube / Vimeo / MP4 URL.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Delete confirm modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 bg-black/60 grid place-items-center p-4" onClick={() => setConfirmDelete(null)} data-testid="admin-videos-delete-modal">
          <div className="bg-white rounded-2xl max-w-[440px] w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-[#FFE9E5] grid place-items-center flex-none">
                <AlertTriangle className="w-5 h-5 text-[#C02719]" />
              </div>
              <div>
                <h3 className="text-[18px] font-extrabold text-[#0F2C24]">Delete this video?</h3>
                <p className="mt-1.5 text-[13px] text-[#525860]">
                  &ldquo;{confirmDelete.title}&rdquo; will be removed from the public site immediately. This can&rsquo;t be undone.
                </p>
              </div>
            </div>
            <div className="mt-5 flex items-center justify-end gap-2">
              <button type="button" onClick={() => setConfirmDelete(null)} className="px-4 h-9 text-[13px] font-semibold text-[#0F2C24] border border-[#EAE7DF] rounded-full hover:bg-[#FAF8F2]" data-testid="admin-videos-delete-cancel">
                Cancel
              </button>
              <button type="button" onClick={doDelete} className="px-4 h-9 text-[13px] font-bold text-white bg-[#C02719] rounded-full hover:bg-[#9c1f14]" data-testid="admin-videos-delete-confirm">
                Delete video
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FormPanel({ form, isNew, onChange, onSave, onCancel, saving, addChapter, updateChapter, removeChapter }) {
  const previewVideo = form.src ? form : null;
  return (
    <div className="bg-white border border-[#EAE7DF] rounded-xl overflow-hidden" data-testid="admin-videos-form-panel">
      <div className="px-5 py-3 border-b border-[#F1EEE6] flex items-center justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#C02719]">{isNew ? "Create" : "Edit"}</p>
          <h3 className="text-[15px] font-extrabold text-[#0F2C24]">{isNew ? "Add a new video" : "Edit video"}</h3>
        </div>
        <button type="button" onClick={onCancel} aria-label="Close" className="w-8 h-8 grid place-items-center text-[#525860] hover:text-[#0F2C24]" data-testid="admin-videos-form-close">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-5 space-y-3 max-h-[68vh] overflow-y-auto">
        {/* Live preview */}
        {previewVideo && (
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-[0.1em] text-[#525860] mb-1.5">Live preview</label>
            <VideoPlayer video={previewVideo} />
            <a href={form.src} target="_blank" rel="noreferrer" className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-[#525860] hover:text-[#C02719]">
              <ExternalLink className="w-3 h-3" /> Open source URL
            </a>
          </div>
        )}

        <Field label="Title (required)">
          <input value={form.title} onChange={onChange("title")} placeholder="e.g. First payroll run in under 2 hours"
            className="w-full h-10 px-3 border border-[#EAE7DF] rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="admin-videos-input-title" />
        </Field>
        <Field label="Source URL — YouTube, Vimeo or MP4 (required)">
          <input value={form.src} onChange={onChange("src")} placeholder="https://youtu.be/… or https://yourcdn.com/file.mp4"
            className="w-full h-10 px-3 border border-[#EAE7DF] rounded-lg text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="admin-videos-input-src" />
        </Field>
        <Field label="Summary (required)">
          <textarea value={form.summary} onChange={onChange("summary")} rows={3} placeholder="One or two sentences shown below the video card."
            className="w-full px-3 py-2 border border-[#EAE7DF] rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="admin-videos-input-summary" />
        </Field>
        <Field label="Poster image URL (optional)">
          <input value={form.poster || ""} onChange={onChange("poster")} placeholder="https://…/poster.jpg (defaults to a placeholder)"
            className="w-full h-10 px-3 border border-[#EAE7DF] rounded-lg text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="admin-videos-input-poster" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Duration (seconds)">
            <input type="number" min="10" max="14400" value={form.duration_s} onChange={onChange("duration_s")}
              className="w-full h-10 px-3 border border-[#EAE7DF] rounded-lg text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="admin-videos-input-duration" />
          </Field>
          <Field label="Sort order">
            <input type="number" value={form.sort} onChange={onChange("sort")}
              className="w-full h-10 px-3 border border-[#EAE7DF] rounded-lg text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="admin-videos-input-sort" />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Category">
            <select value={form.category} onChange={onChange("category")}
              className="w-full h-10 px-3 border border-[#EAE7DF] rounded-lg text-[13px] bg-white focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="admin-videos-select-category">
              {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          </Field>
          <Field label="Persona">
            <select value={form.persona} onChange={onChange("persona")}
              className="w-full h-10 px-3 border border-[#EAE7DF] rounded-lg text-[13px] bg-white focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="admin-videos-select-persona">
              {PERSONAS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </Field>
        </div>

        {/* Chapters */}
        <div>
          <div className="flex items-center justify-between">
            <label className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#525860]">Chapters ({form.chapters.length})</label>
            <button type="button" onClick={addChapter} className="text-[11px] font-bold text-[#C02719] hover:underline" data-testid="admin-videos-chapter-add">+ Add chapter</button>
          </div>
          <div className="space-y-1.5 mt-2">
            {form.chapters.map((c, i) => (
              <div key={i} className="flex items-center gap-2" data-testid={`admin-videos-chapter-${i}`}>
                <input type="number" min="0" value={c.t} onChange={(e) => updateChapter(i, "t", e.target.value)}
                  className="w-[80px] h-8 px-2 border border-[#EAE7DF] rounded-md text-[12px] font-mono focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" placeholder="seconds" />
                <input value={c.label} onChange={(e) => updateChapter(i, "label", e.target.value)}
                  className="flex-1 h-8 px-2 border border-[#EAE7DF] rounded-md text-[12px] focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" placeholder="Chapter label" />
                <button type="button" onClick={() => removeChapter(i)} aria-label="Remove chapter" className="text-[#9aa0a6] hover:text-[#C02719]"><X className="w-3.5 h-3.5" /></button>
              </div>
            ))}
            {form.chapters.length === 0 && (
              <p className="text-[11px] text-[#9aa0a6] italic">No chapters yet — add a few for navigable timestamps.</p>
            )}
          </div>
        </div>

        <Field label="Status">
          <label className="flex items-center gap-2 text-[13px] text-[#0F2C24]">
            <input type="checkbox" checked={!!form.published} onChange={(e) => onChange("published")(e.target.checked)} className="w-4 h-4" data-testid="admin-videos-input-published" />
            Published (visible on the public site)
          </label>
        </Field>
      </div>

      <div className="px-5 py-3 border-t border-[#F1EEE6] bg-[#FAF8F2] flex items-center justify-end gap-2">
        <button type="button" onClick={onCancel} className="px-4 h-9 text-[13px] font-semibold text-[#0F2C24] border border-[#EAE7DF] rounded-full hover:bg-white" data-testid="admin-videos-form-cancel">
          Cancel
        </button>
        <button type="button" onClick={onSave} disabled={saving} className="inline-flex items-center gap-1.5 px-4 h-9 text-[13px] font-bold text-white bg-[#C02719] rounded-full hover:bg-[#9c1f14] disabled:opacity-60" data-testid="admin-videos-form-save">
          <Save className="w-3.5 h-3.5" /> {saving ? "Saving…" : (isNew ? "Create video" : "Save changes")}
        </button>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[10px] font-bold uppercase tracking-[0.1em] text-[#525860] mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function fmt(s) {
  if (!s) return "0:00";
  const t = Math.floor(s);
  const m = Math.floor(t / 60);
  const r = t % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}
