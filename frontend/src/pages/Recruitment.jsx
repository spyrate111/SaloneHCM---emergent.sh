import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { Briefcase, Plus, Link2, Download, UserPlus } from "lucide-react";

const STAGES = ["applied", "shortlisted", "interview", "offer", "hired", "rejected"];
const STAGE_CLS = {
  applied: "bg-[#F7F6F2] text-[#525860]", shortlisted: "bg-[#E5EEF6] text-[#26547C]",
  interview: "bg-[#F6EDD8] text-[#8B6A14]", offer: "bg-[#FBF1DE] text-[#D1603D]",
  hired: "bg-[#E4F7E7] text-[#0A4A1E]", rejected: "bg-[#FBE9E9] text-[#B03A2E]",
};

export default function Recruitment() {
  const [vacancies, setVacancies] = useState([]);
  const [selected, setSelected] = useState(null);
  const [apps, setApps] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [hireApp, setHireApp] = useState(null);

  const load = useCallback(() => {
    api.get("/recruitment/vacancies").then((r) => setVacancies(r.data)).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const openVacancy = async (v) => {
    setSelected(v);
    const r = await api.get(`/recruitment/vacancies/${v.id}/applications`);
    setApps(r.data);
  };

  const copyLink = (v) => {
    navigator.clipboard.writeText(`${window.location.origin}/apply/${v.public_token}`);
    toast.success("Public application link copied");
  };

  const setStage = async (app, stage) => {
    try {
      const { data } = await api.patch(`/recruitment/applications/${app.id}/stage`, { stage });
      setApps((prev) => prev.map((a) => (a.id === app.id ? { ...a, stage } : a)));
      if (data.prompt_create_employee) setHireApp({ ...app, stage });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Stage update failed");
    }
  };

  const downloadCv = async (app) => {
    const r = await api.get(`/recruitment/applications/${app.id}/cv`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = app.cv?.filename || "cv.pdf"; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6" data-testid="recruitment-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Hiring</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Recruitment</h1>
          <p className="text-[#525860] text-sm mt-1">Post vacancies, share the public apply link, and move candidates through stages.</p>
        </div>
        <button onClick={() => setShowForm(true)} data-testid="vacancy-new-button"
          className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm font-medium px-4 py-2.5 rounded-md">
          <Plus className="w-4 h-4" /> Post vacancy
        </button>
      </div>

      {showForm && <VacancyForm onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <section className="bg-white border border-[#E2DFD6] rounded-lg p-4 space-y-2" data-testid="vacancy-list">
          {vacancies.length === 0 && (
            <div className="text-sm text-[#686D76] p-4 flex items-center gap-2"><Briefcase className="w-4 h-4" /> No vacancies yet.</div>
          )}
          {vacancies.map((v) => (
            <button key={v.id} onClick={() => openVacancy(v)}
              className={`w-full text-left rounded-lg p-3 border transition ${selected?.id === v.id ? "border-[#0A4A1E] bg-[#F2F8F3]" : "border-[#F0EEE8] hover:border-[#E2DFD6]"}`}
              data-testid={`vacancy-${v.id}`}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">{v.title}</span>
                <span className={`text-[10px] uppercase px-2 py-0.5 rounded-full ${v.status === "open" ? "bg-[#E4F7E7] text-[#0A4A1E]" : "bg-[#F7F6F2] text-[#686D76]"}`}>{v.status}</span>
              </div>
              <div className="text-xs text-[#686D76] mt-0.5">{v.department} · Grade {v.grade_level || "—"} · closes {v.closing_date}</div>
              <div className="text-[11px] text-[#8A8F96] mt-0.5">{v.application_count} application{v.application_count === 1 ? "" : "s"}</div>
            </button>
          ))}
        </section>

        <section className="lg:col-span-2 bg-white border border-[#E2DFD6] rounded-lg p-5" data-testid="applications-panel">
          {!selected ? (
            <div className="text-sm text-[#686D76] p-6 text-center">Select a vacancy to manage its applications.</div>
          ) : (
            <>
              <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
                <div>
                  <div className="font-heading text-lg font-semibold">{selected.title}</div>
                  <div className="text-xs text-[#686D76]">{apps.length} candidate{apps.length === 1 ? "" : "s"}</div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => copyLink(selected)} data-testid="vacancy-copy-link"
                    className="inline-flex items-center gap-1.5 text-xs border border-[#26547C] text-[#26547C] px-3 py-2 rounded-md">
                    <Link2 className="w-3.5 h-3.5" /> Copy apply link
                  </button>
                  <button data-testid="vacancy-toggle-status"
                    onClick={async () => {
                      const status = selected.status === "open" ? "closed" : "open";
                      await api.put(`/recruitment/vacancies/${selected.id}`, { status });
                      setSelected({ ...selected, status }); load();
                    }}
                    className="text-xs border border-[#E2DFD6] px-3 py-2 rounded-md">
                    {selected.status === "open" ? "Close vacancy" : "Reopen"}
                  </button>
                </div>
              </div>
              {apps.length === 0 ? (
                <div className="text-sm text-[#686D76] py-6">No applications yet — share the public link.</div>
              ) : apps.map((a) => (
                <div key={a.id} className="border-b border-[#F0EEE8] py-3 flex items-center justify-between gap-3 flex-wrap" data-testid={`application-${a.id}`}>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold">{a.name}</div>
                    <div className="text-xs text-[#686D76]">{a.email}{a.phone ? ` · ${a.phone}` : ""}</div>
                    {a.cover_note && <div className="text-xs text-[#8A8F96] mt-1 max-w-lg truncate" title={a.cover_note}>{a.cover_note}</div>}
                  </div>
                  <div className="flex items-center gap-2">
                    {a.cv && (
                      <button onClick={() => downloadCv(a)} className="p-1.5 text-[#26547C]" title="Download CV" data-testid={`application-cv-${a.id}`}>
                        <Download className="w-4 h-4" />
                      </button>
                    )}
                    {a.hired_employee_id ? (
                      <span className="text-[10px] uppercase px-2 py-1 rounded-full bg-[#E4F7E7] text-[#0A4A1E]">Employee created</span>
                    ) : a.stage === "hired" ? (
                      <button onClick={() => setHireApp(a)} data-testid={`application-hire-${a.id}`}
                        className="inline-flex items-center gap-1 text-xs bg-[#0A4A1E] text-white px-2.5 py-1.5 rounded-md">
                        <UserPlus className="w-3.5 h-3.5" /> Create employee
                      </button>
                    ) : null}
                    <select value={a.stage} onChange={(e) => setStage(a, e.target.value)}
                      className={`text-xs rounded-md px-2 py-1.5 border border-[#E2DFD6] capitalize ${STAGE_CLS[a.stage]}`}
                      data-testid={`application-stage-${a.id}`}>
                      {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                </div>
              ))}
            </>
          )}
        </section>
      </div>

      {hireApp && (
        <HireModal app={hireApp} vacancy={selected}
          onClose={() => setHireApp(null)}
          onHired={() => { setHireApp(null); openVacancy(selected); }} />
      )}
    </div>
  );
}

function VacancyForm({ onClose, onSaved }) {
  const [f, setF] = useState({ title: "", department: "", grade_level: "", closing_date: "", description: "" });
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/recruitment/vacancies", f);
      toast.success("Vacancy posted");
      onSaved();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };
  const inp = "mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2 text-sm";
  return (
    <form onSubmit={submit} className="bg-white border border-[#E2DFD6] rounded-lg p-6 grid grid-cols-1 sm:grid-cols-2 gap-4" data-testid="vacancy-form">
      <label className="text-xs text-[#525860]">Title
        <input required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className={inp} data-testid="vacancy-form-title" /></label>
      <label className="text-xs text-[#525860]">Department
        <input required value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} className={inp} data-testid="vacancy-form-department" /></label>
      <label className="text-xs text-[#525860]">Grade level
        <input value={f.grade_level} onChange={(e) => setF({ ...f, grade_level: e.target.value })} className={inp} data-testid="vacancy-form-grade" /></label>
      <label className="text-xs text-[#525860]">Closing date
        <input required type="date" value={f.closing_date} onChange={(e) => setF({ ...f, closing_date: e.target.value })} className={inp} data-testid="vacancy-form-closing" /></label>
      <label className="text-xs text-[#525860] sm:col-span-2">Description
        <textarea rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className={inp} data-testid="vacancy-form-description" /></label>
      <div className="sm:col-span-2 flex gap-2">
        <button className="bg-[#0A4A1E] text-white text-sm px-5 py-2.5 rounded-md" data-testid="vacancy-form-submit">Post vacancy</button>
        <button type="button" onClick={onClose} className="border border-[#E2DFD6] text-sm px-5 py-2.5 rounded-md">Cancel</button>
      </div>
    </form>
  );
}

function HireModal({ app, vacancy, onClose, onHired }) {
  const [f, setF] = useState({
    job_title: vacancy?.title || "", department: vacancy?.department || "",
    basic_salary_sle: "", hire_date: new Date().toISOString().slice(0, 10),
  });
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/recruitment/applications/${app.id}/create-employee`,
        { ...f, basic_salary_sle: parseFloat(f.basic_salary_sle) });
      toast.success(`${app.name} added as an employee`);
      onHired();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed to create employee"); }
  };
  const inp = "mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2 text-sm";
  return (
    <div className="fixed inset-0 bg-black/40 grid place-items-center z-50 p-4" data-testid="hire-modal">
      <form onSubmit={submit} className="bg-white rounded-xl p-6 w-full max-w-md space-y-3">
        <div className="font-heading text-lg font-semibold">Create employee record</div>
        <p className="text-xs text-[#686D76]">Pre-filled from {app.name}&rsquo;s application ({app.email}).</p>
        <label className="text-xs text-[#525860] block">Job title
          <input required value={f.job_title} onChange={(e) => setF({ ...f, job_title: e.target.value })} className={inp} data-testid="hire-form-title" /></label>
        <label className="text-xs text-[#525860] block">Department
          <input required value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} className={inp} data-testid="hire-form-department" /></label>
        <label className="text-xs text-[#525860] block">Basic salary (SLE)
          <input required type="number" min="1" step="0.01" value={f.basic_salary_sle}
            onChange={(e) => setF({ ...f, basic_salary_sle: e.target.value })} className={`${inp} font-data`} data-testid="hire-form-salary" /></label>
        <label className="text-xs text-[#525860] block">Hire date
          <input required type="date" value={f.hire_date} onChange={(e) => setF({ ...f, hire_date: e.target.value })} className={inp} data-testid="hire-form-date" /></label>
        <div className="flex gap-2 pt-1">
          <button className="bg-[#0A4A1E] text-white text-sm px-5 py-2.5 rounded-md flex-1" data-testid="hire-form-submit">Create employee</button>
          <button type="button" onClick={onClose} className="border border-[#E2DFD6] text-sm px-4 py-2.5 rounded-md">Later</button>
        </div>
      </form>
    </div>
  );
}
