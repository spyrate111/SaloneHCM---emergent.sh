import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Briefcase, Star, GraduationCap, Plus, X } from "lucide-react";

const STAGES = ["applied", "screening", "interview", "offer", "hired", "rejected"];
const STAGE_BG = {
  applied: "bg-[#EBE8E0] text-[#525860]",
  screening: "bg-[#E5EEF6] text-[#26547C]",
  interview: "bg-[#FBF1DE] text-[#8B6A14]",
  offer: "bg-[#FBE9DF] text-[#B84F2F]",
  hired: "bg-[#E6F4EC] text-[#2D7A5D]",
  rejected: "bg-[#FBEAEA] text-[#B83A3A]",
};

function Tab({ active, onClick, icon: Icon, children, testId }) {
  return (
    <button data-testid={testId} onClick={onClick} className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition ${
      active ? "text-[#133326] border-[#133326]" : "text-[#686D76] border-transparent hover:text-[#1A1C1E]"
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
      <div className="flex border-b border-[#E2DFD6] gap-1">
        <Tab active={tab === "recruitment"} onClick={() => setTab("recruitment")} icon={Briefcase} testId="tab-recruitment">Recruitment</Tab>
        <Tab active={tab === "performance"} onClick={() => setTab("performance")} icon={Star} testId="tab-performance">Performance</Tab>
        <Tab active={tab === "learning"} onClick={() => setTab("learning")} icon={GraduationCap} testId="tab-learning">Learning</Tab>
      </div>
      {tab === "recruitment" && <Recruitment isAdmin={isAdmin} />}
      {tab === "performance" && <Performance isAdmin={isAdmin} />}
      {tab === "learning" && <Learning isAdmin={isAdmin} />}
    </div>
  );
}

function Recruitment({ isAdmin }) {
  const [postings, setPostings] = useState([]);
  const [applicants, setApplicants] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", department: "", location: "Freetown", employment_type: "Full-time", salary_min_sle: 0, salary_max_sle: 0, description: "", status: "open" });

  const load = useCallback(async () => {
    const ps = await api.get("/talent/postings");
    setPostings(ps.data);
    if (isAdmin) {
      const ap = await api.get("/talent/applicants");
      setApplicants(ap.data);
    }
  }, [isAdmin]);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    await api.post("/talent/postings", { ...form, salary_min_sle: Number(form.salary_min_sle), salary_max_sle: Number(form.salary_max_sle) });
    setOpen(false); load();
  };

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
          <div key={p.id} className="bg-white border border-[#E2DFD6] rounded-lg p-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[#525860]">{p.department} · {p.location}</div>
                <h3 className="font-heading text-lg font-semibold mt-0.5">{p.title}</h3>
              </div>
              <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${p.status === "open" ? "bg-[#E6F4EC] text-[#2D7A5D]" : "bg-[#EBE8E0] text-[#525860]"}`}>{p.status}</span>
            </div>
            <div className="mt-3 text-sm text-[#525860]">{p.employment_type} · {fmtSLE(p.salary_min_sle)} – {fmtSLE(p.salary_max_sle)}</div>
            {p.description && <p className="text-xs text-[#686D76] mt-2">{p.description}</p>}
          </div>
        ))}
        {!postings.length && <div className="col-span-2 text-center py-12 text-sm text-[#686D76]">No open positions.</div>}
      </div>

      {isAdmin && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-[#E2DFD6]"><h3 className="font-heading text-lg font-semibold">Applicants</h3></div>
          <table className="w-full text-sm">
            <thead className="bg-[#F7F6F2]">
              <tr>{["Name", "Posting", "Stage", "Email", ""].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {applicants.map((a) => (
                <tr key={a.id} className="border-t border-[#E2DFD6]">
                  <td className="py-3 px-4 font-medium">{a.name}</td>
                  <td className="py-3 px-4 text-[#525860]">{a.posting_title}</td>
                  <td className="py-3 px-4">
                    <select value={a.stage} onChange={(e) => advance(a.id, e.target.value)} className={`text-[11px] uppercase tracking-wider px-2 py-1 rounded-full ${STAGE_BG[a.stage]} border-0 outline-none cursor-pointer`}>
                      {STAGES.map((s) => <option key={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="py-3 px-4 text-[#525860] text-xs">{a.email}</td>
                  <td className="py-3 px-4 text-right text-xs text-[#686D76]">{a.phone}</td>
                </tr>
              ))}
              {!applicants.length && <tr><td colSpan={5} className="py-10 text-center text-sm text-[#686D76]">No applicants yet.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setOpen(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="bg-white rounded-lg w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-heading text-xl font-semibold">New job posting</h2>
              <button type="button" onClick={() => setOpen(false)} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-3">
              {[["title", "Title"], ["department", "Department"], ["location", "Location"]].map(([k, l]) => (
                <div key={k}>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">{l}</label>
                  <input required value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
                </div>
              ))}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Min SLE</label>
                  <input type="number" value={form.salary_min_sle} onChange={(e) => setForm({ ...form, salary_min_sle: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Max SLE</label>
                  <input type="number" value={form.salary_max_sle} onChange={(e) => setForm({ ...form, salary_max_sle: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Description</label>
                <textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button type="submit" className="px-4 py-2 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white rounded-md">Post</button>
            </div>
          </form>
        </div>
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
  const [form, setForm] = useState({ title: "", provider: "", hours: 8, skill_area: "", description: "" });

  const load = useCallback(async () => {
    const [p, c] = await Promise.all([api.get("/talent/programs"), api.get("/talent/completions")]);
    setPrograms(p.data); setCompletions(c.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    await api.post("/talent/programs", { ...form, hours: Number(form.hours) });
    setOpen(false); load();
  };

  const markComplete = async (programId) => {
    await api.post("/talent/completions", { program_id: programId, completed_on: new Date().toISOString().split("T")[0], score: 90 });
    load();
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
          <div key={p.id} className="bg-white border border-[#E2DFD6] rounded-lg p-5 flex flex-col">
            <div className="w-9 h-9 rounded-md bg-[#E5EEF6] grid place-items-center"><GraduationCap className="w-[18px] h-[18px] text-[#26547C]" strokeWidth={1.5} /></div>
            <div className="mt-3 flex-1">
              <div className="text-[10px] uppercase tracking-wider text-[#525860]">{p.skill_area}</div>
              <h3 className="font-heading text-base font-semibold mt-0.5">{p.title}</h3>
              <div className="text-xs text-[#686D76] mt-1">{p.provider || "Internal"} · {p.hours}h</div>
              {p.description && <p className="text-xs text-[#686D76] mt-2">{p.description}</p>}
            </div>
            <button onClick={() => markComplete(p.id)} className="mt-3 text-xs bg-[#133326] hover:bg-[#0F281E] text-white rounded px-3 py-2 font-medium">Mark complete</button>
          </div>
        ))}
        {!programs.length && <div className="col-span-3 text-center py-12 text-sm text-[#686D76]">No programs yet.</div>}
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-[#E2DFD6]"><h3 className="font-heading text-lg font-semibold">Completions</h3></div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Employee", "Program", "Skill", "Date", "Score"].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {completions.map((c) => (
              <tr key={c.id} className="border-t border-[#E2DFD6]">
                <td className="py-3 px-4">{c.employee_name}</td>
                <td className="py-3 px-4 font-medium">{c.program_title}</td>
                <td className="py-3 px-4 text-[#525860]">{c.program_skill_area}</td>
                <td className="py-3 px-4 font-data">{c.completed_on}</td>
                <td className="py-3 px-4 font-data">{c.score ?? "—"}{c.score && "%"}</td>
              </tr>
            ))}
            {!completions.length && <tr><td colSpan={5} className="py-10 text-center text-sm text-[#686D76]">No completions yet.</td></tr>}
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
