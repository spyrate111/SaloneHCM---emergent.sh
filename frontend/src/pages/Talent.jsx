import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Briefcase, Star, GraduationCap, Plus, X, RefreshCw, Download } from "lucide-react";
import {
  DndContext, PointerSensor, useSensor, useSensors, closestCenter, DragOverlay,
} from "@dnd-kit/core";
import {
  SortableContext, useSortable, verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import TrainingProgressPanel from "../components/TrainingProgressPanel";
import ReminderNudgeStats from "../components/ReminderNudgeStats";
import PostJobModal from "../components/PostJobModal";

const STAGES = ["applied", "screening", "interview", "offer", "hired", "rejected"];
const STAGE_BG = {
  applied: "bg-[#EBE8E0] text-[#525860]",
  screening: "bg-[#E5EEF6] text-[#26547C]",
  interview: "bg-[#FBF1DE] text-[#8B6A14]",
  offer: "bg-[#FBE9DF] text-[#B84F2F]",
  hired: "bg-[#E4F7E7] text-[#17A035]",
  rejected: "bg-[#E9F2FB] text-[#3A7CB8]",
};

function Tab({ active, onClick, icon: Icon, children, testId }) {
  return (
    <button data-testid={testId} role="tab" aria-selected={active} onClick={onClick} className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition ${
      active ? "text-[#0A4A1E] border-[#0A4A1E]" : "text-[#686D76] border-transparent hover:text-[#1A1C1E]"
    }`}>
      <Icon className="w-4 h-4" strokeWidth={1.5} /> {children}
    </button>
  );
}

export default function Talent() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [tab, setTab] = useState("recruitment");

  return (
    <div className="space-y-6" data-testid="talent-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Talent & Development</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Talent</h1>
        <p className="text-[#525860] text-sm mt-1">Hire, review, and develop your team.</p>
      </div>
      <div className="flex border-b border-[#E2DFD6] gap-1" role="tablist">
        <Tab active={tab === "recruitment"} onClick={() => setTab("recruitment")} icon={Briefcase} testId="tab-recruitment">Recruitment</Tab>
        <Tab active={tab === "learning"} onClick={() => setTab("learning")} icon={GraduationCap} testId="tab-learning">Learning</Tab>
      </div>
      {tab === "recruitment" && <Recruitment isAdmin={isAdmin} />}
      {tab === "learning" && (
        <>
          <Learning isAdmin={isAdmin} />
          <TrainingProgressPanel />
          <ReminderNudgeStats />
        </>
      )}
    </div>
  );
}

function Recruitment({ isAdmin }) {
  const [postings, setPostings] = useState([]);
  const [pipeline, setPipeline] = useState({ stages: [], grouped: {}, total: 0 });
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    const ps = await api.get("/talent/postings");
    setPostings(ps.data);
    if (isAdmin) {
      const ap = await api.get("/talent/applicants/pipeline");
      setPipeline(ap.data);
    }
  }, [isAdmin]);
  useEffect(() => { load(); }, [load]);

  const advance = async (aid, stage) => { await api.patch(`/talent/applicants/${aid}/stage`, { stage }); load(); };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xl font-semibold">Open positions</h2>
        {isAdmin && (
          <button data-testid="post-job" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white text-sm font-medium px-4 py-2 rounded-md">
            <Plus className="w-4 h-4" /> Post job
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {postings.map((p) => (
          <div
            key={p.id}
            data-testid={p.source === "establishment" ? `posting-establishment-${p.id}` : `posting-manual-${p.id}`}
            className={`bg-white border rounded-lg p-5 ${p.source === "establishment" ? "border-[#C9D7E2]" : "border-[#E2DFD6]"}`}
          >
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <div className="min-w-0">
                <div className="text-[10px] uppercase tracking-wider text-[#525860]">{p.department} · {p.location}</div>
                <h3 className="font-heading text-lg font-semibold mt-0.5 truncate">{p.title}</h3>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap">
                {p.source === "establishment" && (
                  <span
                    data-testid="posting-source-establishment"
                    title={`Auto-published from Establishment Control (${p.establishment_meta?.ministry || ""})`}
                    className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#E6EEF6] text-[#26547C] border border-[#C9D7E2]"
                  >
                    From Establishment
                  </span>
                )}
                <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${p.status === "open" ? "bg-[#E4F7E7] text-[#17A035]" : "bg-[#EBE8E0] text-[#525860]"}`}>{p.status}</span>
              </div>
            </div>
            <div className="mt-3 text-sm text-[#525860]">
              {p.employment_type} · {fmtSLE(p.salary_min_sle)} – {fmtSLE(p.salary_max_sle)}
            </div>
            {p.description && <p className="text-xs text-[#686D76] mt-2">{p.description}</p>}
            {p.source === "establishment" && p.establishment_meta && (
              <div className="mt-3 pt-3 border-t border-[#F1EEE6] flex items-center gap-3 flex-wrap text-[11px] text-[#525860]">
                <span>{p.establishment_meta.ministry}</span>
                {p.establishment_meta.grade_code && <span className="font-data">Grade {p.establishment_meta.grade_code}</span>}
                {p.establishment_meta.budget_code && <span className="font-data">{p.establishment_meta.budget_code}</span>}
                <span className="ml-auto font-data">{p.establishment_meta.vacancy_count} vacancy(s) / {p.establishment_meta.approved_count} approved</span>
              </div>
            )}
          </div>
        ))}
        {!postings.length && <div className="col-span-2 text-center py-12 text-sm text-[#686D76]">No open positions.</div>}
      </div>

      {isAdmin && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="applicant-kanban">
          <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="font-heading text-lg font-semibold">Applicant pipeline</h3>
              <p className="text-xs text-[#686D76] mt-0.5">Drag any card between columns to advance the stage. {pipeline.total} candidates in flight.</p>
            </div>
          </div>
          <KanbanBoard pipeline={pipeline} onMove={advance} />
        </div>
      )}

      {open && (
        <PostJobModal
          onClose={() => setOpen(false)}
          onPosted={() => { setOpen(false); load(); }}
        />
      )}
    </div>
  );
}

function Performance({ isAdmin }) {
  const [reviews, setReviews] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ employee_id: "", period: "2026-Q1", rating: 4, notes: "" });

  const load = useCallback(async () => {
    const r = await api.get("/talent/reviews");
    setReviews(r.data);
    if (isAdmin) { const e = await api.get("/employees"); setEmployees(e.data); }
  }, [isAdmin]);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    await api.post("/talent/reviews", { ...form, rating: Number(form.rating) });
    setOpen(false); load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xl font-semibold">Performance reviews</h2>
        {isAdmin && (
          <button data-testid="add-review" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white text-sm font-medium px-4 py-2 rounded-md">
            <Plus className="w-4 h-4" /> New review
          </button>
        )}
      </div>
      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Employee", "Period", "Rating", "Reviewer", "Notes"].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {reviews.map((r) => (
              <tr key={r.id} className="border-t border-[#E2DFD6]">
                <td className="py-3 px-4 font-medium">{r.employee_name}</td>
                <td className="py-3 px-4 font-data text-[#525860]">{r.period}</td>
                <td className="py-3 px-4">
                  <div className="flex gap-0.5">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <Star key={n} className={`w-3.5 h-3.5 ${n <= r.rating ? "text-[#D1603D] fill-[#D1603D]" : "text-[#E2DFD6]"}`} />
                    ))}
                  </div>
                </td>
                <td className="py-3 px-4 text-xs text-[#686D76]">{r.reviewer}</td>
                <td className="py-3 px-4 text-xs text-[#686D76] max-w-md truncate">{r.notes || "—"}</td>
              </tr>
            ))}
            {!reviews.length && <tr><td colSpan={5} className="py-10 text-center text-sm text-[#686D76]">No reviews yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setOpen(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="bg-white rounded-lg w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-heading text-xl font-semibold">New performance review</h2>
              <button type="button" onClick={() => setOpen(false)} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Employee</label>
                <select required value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                  <option value="">Select…</option>
                  {employees.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Period</label>
                  <input value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Rating (1-5)</label>
                  <input required type="number" min="1" max="5" value={form.rating} onChange={(e) => setForm({ ...form, rating: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Notes</label>
                <textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button type="submit" className="px-4 py-2 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white rounded-md">Save</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function Learning({ isAdmin }) {
  const [programs, setPrograms] = useState([]);
  const [completions, setCompletions] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", provider: "", hours: 8, skill_area: "", description: "", is_recurring: false, frequency: "annual" });

  const load = useCallback(async () => {
    const [p, c] = await Promise.all([api.get("/talent/programs"), api.get("/talent/completions")]);
    setPrograms(p.data); setCompletions(c.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    const payload = { ...form, hours: Number(form.hours) };
    if (!payload.is_recurring) { delete payload.frequency; delete payload.next_due_at; }
    await api.post("/talent/programs", payload);
    setOpen(false); load();
  };

  const markComplete = async (programId) => {
    await api.post("/talent/completions", { program_id: programId, completed_on: new Date().toISOString().split("T")[0], score: 90 });
    load();
  };

  const downloadCert = async (cid) => {
    try {
      const resp = await api.get(`/talent/completions/${cid}/certificate.pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url; a.download = `certificate-${cid.slice(0, 8)}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Certificate download failed");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xl font-semibold">Training programs</h2>
        {isAdmin && (
          <button data-testid="add-program" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white text-sm font-medium px-4 py-2 rounded-md">
            <Plus className="w-4 h-4" /> New program
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {programs.map((p) => (
          <div key={p.id} className="bg-white border border-[#E2DFD6] rounded-lg p-5 flex flex-col" data-testid={`program-card-${p.id}`}>
            <div className="flex items-start justify-between">
              <div className="w-9 h-9 rounded-md bg-[#E5EEF6] grid place-items-center"><GraduationCap className="w-[18px] h-[18px] text-[#26547C]" strokeWidth={1.5} /></div>
              {p.is_recurring && (
                <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-medium px-2 py-0.5 rounded-full bg-[#FBF1DE] text-[#8B6A14]" data-testid={`recurring-badge-${p.id}`}>
                  <RefreshCw className="w-3 h-3" /> Recurring · {p.frequency}
                </span>
              )}
            </div>
            <div className="mt-3 flex-1">
              <div className="text-[10px] uppercase tracking-wider text-[#525860]">{p.skill_area}</div>
              <h3 className="font-heading text-base font-semibold mt-0.5">{p.title}</h3>
              <div className="text-xs text-[#686D76] mt-1">{p.provider || "Internal"} · {p.hours}h</div>
              {p.description && <p className="text-xs text-[#686D76] mt-2">{p.description}</p>}
              {p.is_recurring && p.next_due_at && (
                <div className="mt-2 text-[10px] text-[#8B6A14] font-data">Next due: {new Date(p.next_due_at).toLocaleDateString()}</div>
              )}
            </div>
            <button onClick={() => markComplete(p.id)} className="mt-3 text-xs bg-[#0A4A1E] hover:bg-[#063514] text-white rounded px-3 py-2 font-medium">Mark complete</button>
          </div>
        ))}
        {!programs.length && <div className="col-span-3 text-center py-12 text-sm text-[#686D76]">No programs yet.</div>}
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-[#E2DFD6]"><h3 className="font-heading text-lg font-semibold">Completions</h3></div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Employee", "Program", "Skill", "Date", "Score", ""].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {completions.map((c) => (
              <tr key={c.id} className="border-t border-[#E2DFD6]" data-testid={`completion-row-${c.id}`}>
                <td className="py-3 px-4">{c.employee_name}</td>
                <td className="py-3 px-4 font-medium">
                  {c.program_title}
                  {c.program_is_recurring && <span className="ml-2 text-[10px] uppercase tracking-wider text-[#8B6A14]">recurring</span>}
                </td>
                <td className="py-3 px-4 text-[#525860]">{c.program_skill_area}</td>
                <td className="py-3 px-4 font-data">{c.completed_on}</td>
                <td className="py-3 px-4 font-data">{c.score ?? "—"}{c.score && "%"}</td>
                <td className="py-3 px-4 text-right">
                  <button data-testid={`cert-download-${c.id}`} onClick={() => downloadCert(c.id)} className="inline-flex items-center gap-1 text-xs bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#0A4A1E] px-2.5 py-1.5 rounded">
                    <Download className="w-3.5 h-3.5" /> Certificate
                  </button>
                </td>
              </tr>
            ))}
            {!completions.length && <tr><td colSpan={6} className="py-10 text-center text-sm text-[#686D76]">No completions yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setOpen(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="bg-white rounded-lg w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-heading text-xl font-semibold">New training program</h2>
              <button type="button" onClick={() => setOpen(false)} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-3">
              {[["title", "Title"], ["provider", "Provider"], ["skill_area", "Skill area"]].map(([k, l]) => (
                <div key={k}>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">{l}</label>
                  <input required={k !== "provider"} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
                </div>
              ))}
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Hours</label>
                <input required type="number" value={form.hours} onChange={(e) => setForm({ ...form, hours: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Description</label>
                <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </div>
              <div className="border-t border-[#F1EEE6] pt-3">
                <label className="inline-flex items-center gap-2 text-sm cursor-pointer" data-testid="program-recurring-toggle">
                  <input type="checkbox" checked={form.is_recurring} onChange={(e) => setForm({ ...form, is_recurring: e.target.checked })} className="w-4 h-4 accent-[#0A4A1E]" />
                  <span><RefreshCw className="w-3.5 h-3.5 inline mr-1" />Recurring (mandatory refresher)</span>
                </label>
                {form.is_recurring && (
                  <div className="mt-3">
                    <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Frequency</label>
                    <select data-testid="program-frequency" value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                      <option value="monthly">Monthly</option>
                      <option value="quarterly">Quarterly</option>
                      <option value="biannual">Biannual</option>
                      <option value="annual">Annual</option>
                    </select>
                  </div>
                )}
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button type="submit" className="px-4 py-2 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white rounded-md">Save</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function KanbanBoard({ pipeline, onMove }) {
  // Local mirror so the UI updates instantly while the server call runs
  const [grouped, setGrouped] = useState(pipeline.grouped);
  useEffect(() => { setGrouped(pipeline.grouped); }, [pipeline.grouped]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));
  const [activeId, setActiveId] = useState(null);

  const findCard = (id) => {
    for (const s of pipeline.stages) {
      const c = (grouped[s] || []).find((a) => a.id === id);
      if (c) return { card: c, stage: s };
    }
    return null;
  };

  const onDragEnd = ({ active, over }) => {
    setActiveId(null);
    if (!over) return;
    const src = findCard(active.id);
    if (!src) return;
    // Container ids are the stage names (we set them on SortableContext id below)
    const destStage = pipeline.stages.includes(over.id) ? over.id : findCard(over.id)?.stage;
    if (!destStage || destStage === src.stage) return;
    setGrouped((g) => {
      const fromList = (g[src.stage] || []).filter((a) => a.id !== active.id);
      const toList = [{ ...src.card, stage: destStage }, ...(g[destStage] || [])];
      return { ...g, [src.stage]: fromList, [destStage]: toList };
    });
    onMove(active.id, destStage);
  };

  const active = activeId ? findCard(activeId)?.card : null;

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={(e) => setActiveId(e.active.id)} onDragEnd={onDragEnd}>
      <div className="p-4 overflow-x-auto">
        <div className="grid grid-cols-6 gap-3 min-w-[1100px]">
          {pipeline.stages.map((s) => (
            <KanbanColumn key={s} stage={s} items={grouped[s] || []} />
          ))}
        </div>
      </div>
      <DragOverlay>{active ? <KanbanCardView a={active} dragging /> : null}</DragOverlay>
    </DndContext>
  );
}

function KanbanColumn({ stage, items }) {
  const { setNodeRef, isOver } = useSortable({ id: stage, data: { type: "column" } });
  return (
    <div
      ref={setNodeRef}
      data-testid={`kanban-col-${stage}`}
      className={`bg-[#F7F6F2] border rounded-md p-2.5 min-h-[280px] transition ${isOver ? "border-[#26547C] bg-[#E5EEF6]" : "border-[#E2DFD6]"}`}
    >
      <div className="flex items-center justify-between mb-2.5">
        <span className={`text-[10px] uppercase tracking-wider font-medium px-2 py-0.5 rounded-full ${STAGE_BG[stage]}`}>{stage}</span>
        <span className="text-[11px] text-[#686D76] font-data">{items.length}</span>
      </div>
      <SortableContext id={stage} items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
        <div className="space-y-2 min-h-[200px]">
          {items.map((a) => <KanbanCard key={a.id} a={a} />)}
          {!items.length && <div className="text-[11px] text-[#A1A5AB] text-center py-6">—</div>}
        </div>
      </SortableContext>
    </div>
  );
}

function KanbanCard({ a }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: a.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      style={style}
      data-testid={`kanban-card-${a.id}`}
      className="bg-white border border-[#E2DFD6] rounded-md p-2.5 shadow-[0_1px_2px_rgba(0,0,0,0.04)] cursor-grab active:cursor-grabbing"
    >
      <KanbanCardView a={a} />
    </div>
  );
}

function KanbanCardView({ a, dragging }) {
  return (
    <div className={dragging ? "bg-white border border-[#26547C] rounded-md p-2.5 shadow-lg" : ""}>
      <div className="flex items-start justify-between gap-1.5">
        <div className="text-[13px] font-medium text-[#1A1C1E] truncate flex-1">{a.name}</div>
        {a.source === "public_careers" && (
          <span
            data-testid="applicant-source-public"
            title="Applied via public /careers page"
            className="shrink-0 text-[9px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-[#FFF2E5] text-[#B84F2F] border border-[#F1C3A1]"
          >
            Public
          </span>
        )}
      </div>
      <div className="text-[11px] text-[#525860] truncate mt-0.5">{a.posting_title}</div>
      <div className="text-[11px] text-[#686D76] truncate mt-0.5 font-data">{a.email}</div>
      {a.application_ref && (
        <div className="text-[10px] text-[#9aa0a6] truncate mt-0.5 font-data">{a.application_ref}</div>
      )}
    </div>
  );
}

