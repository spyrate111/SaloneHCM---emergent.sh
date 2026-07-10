import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { useFeatures } from "../lib/features";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import {
  Award, Building2, Coins, UserCog, Plus, Trash2, AlertTriangle,
  Layers, Tag, ShieldAlert, X, CheckCircle2, Calendar, Download, FileText, Play, Wallet,
} from "lucide-react";
import RetroPayPanel from "../components/RetroPayPanel";

const TABS = [
  { id: "grades", label: "Grades & Steps", icon: Layers },
  { id: "allowances", label: "Allowance Rules", icon: Coins },
  { id: "budgets", label: "Budget Codes", icon: Tag },
  { id: "actings", label: "Acting Allowances", icon: UserCog },
  { id: "increments", label: "Step Increments", icon: Calendar },
  { id: "retro", label: "Retro-pay", icon: Wallet },
  { id: "ghosts", label: "Ghost-Worker Audit", icon: ShieldAlert },
];

export default function CivilService() {
  const { user } = useAuth();
  const { has, loaded } = useFeatures();
  const [tab, setTab] = useState("grades");

  if (loaded && !has("civil_service")) {
    return (
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center">
        <Award className="w-10 h-10 mx-auto text-[#A1A5AB]" strokeWidth={1.3} />
        <h2 className="font-heading text-xl font-semibold mt-3">Civil Service module</h2>
        <p className="text-sm text-[#525860] mt-2">This module is included with the Government tier. Upgrade to access grades, allowance rules, budget codes, and ghost-worker reports.</p>
      </div>
    );
  }

  if (user?.role !== "admin" && user?.role !== "superadmin") {
    return <div className="text-center py-12 text-sm text-[#686D76]">Admin access required.</div>;
  }

  return (
    <div className="space-y-6" data-testid="civil-service-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Government Payroll</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Civil Service configuration</h1>
        <p className="text-[#525860] text-sm mt-1">Sierra Leone civil-service grade structure, allowances, MDA budget codes, and ghost-worker controls.</p>
      </div>
      <div className="flex border-b border-[#E2DFD6] gap-1 flex-wrap" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            data-testid={`tab-${t.id}`}
            onClick={() => setTab(t.id)}
            role="tab"
            aria-selected={tab === t.id}
            className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition ${
              tab === t.id ? "text-[#133326] border-[#133326]" : "text-[#686D76] border-transparent hover:text-[#1A1C1E]"
            }`}
          >
            <t.icon className="w-4 h-4" strokeWidth={1.5} /> {t.label}
          </button>
        ))}
      </div>
      {tab === "grades" && <GradesTab />}
      {tab === "allowances" && <AllowancesTab />}
      {tab === "budgets" && <BudgetCodesTab />}
      {tab === "actings" && <ActingsTab />}
      {tab === "increments" && <IncrementsTab />}
      {tab === "retro" && <RetroPayPanel />}
      {tab === "ghosts" && <GhostsTab />}
    </div>
  );
}

// =============== Grades & Steps ===============

function GradesTab() {
  const [grades, setGrades] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", cadre: "General" });
  const [editing, setEditing] = useState(null); // {grade, steps[]}

  const load = useCallback(async () => {
    const r = await api.get("/civil-service/grades");
    setGrades(r.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/civil-service/grades", form);
      toast.success("Grade created");
      setOpen(false); setForm({ code: "", name: "", cadre: "General" }); load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not create");
    }
  };

  const remove = async (code) => {
    if (!window.confirm(`Delete grade ${code}?`)) return;
    try {
      await api.delete(`/civil-service/grades/${code}`);
      toast.success("Deleted"); load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Cannot delete");
    }
  };

  const saveSteps = async (code, steps) => {
    try {
      const payload = steps.filter((s) => s.monthly_amount_sle > 0).map((s) => ({
        step_number: Number(s.step_number),
        monthly_amount_sle: Number(s.monthly_amount_sle),
      }));
      await api.put(`/civil-service/grades/${code}/steps`, payload);
      toast.success(`Saved ${payload.length} steps for ${code}`);
      setEditing(null); load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xl font-semibold">Civil-service grades</h2>
        <button data-testid="grade-new" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white text-sm px-4 py-2 rounded-md">
          <Plus className="w-4 h-4" /> New grade
        </button>
      </div>
      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Code", "Name", "Cadre", "Steps", "Step range (SLE)", ""].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {grades.map((g) => {
              const amounts = g.steps?.map((s) => s.monthly_amount_sle) || [];
              const min = amounts.length ? Math.min(...amounts) : 0;
              const max = amounts.length ? Math.max(...amounts) : 0;
              return (
                <tr key={g.code} className="border-t border-[#E2DFD6]" data-testid={`grade-row-${g.code}`}>
                  <td className="py-3 px-4 font-data font-semibold">{g.code}</td>
                  <td className="py-3 px-4 font-medium">{g.name}</td>
                  <td className="py-3 px-4 text-[#525860]">{g.cadre}</td>
                  <td className="py-3 px-4 font-data">{g.steps?.length || 0}</td>
                  <td className="py-3 px-4 font-data text-[#26547C]">{min ? `${fmtSLE(min)} → ${fmtSLE(max)}` : "—"}</td>
                  <td className="py-3 px-4 text-right">
                    <button data-testid={`edit-steps-${g.code}`} onClick={() => setEditing({ grade: g, steps: g.steps?.length ? g.steps : [{ step_number: 1, monthly_amount_sle: 0 }] })} className="text-xs text-[#26547C] hover:underline mr-3">Edit steps</button>
                    <button onClick={() => remove(g.code)} className="text-xs text-[#B83A3A] hover:underline"><Trash2 className="w-3.5 h-3.5 inline" /></button>
                  </td>
                </tr>
              );
            })}
            {!grades.length && <tr><td colSpan={6} className="py-12 text-center text-sm text-[#686D76]">No grades yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {open && (
        <Modal title="New grade" onClose={() => setOpen(false)}>
          <form onSubmit={submit} className="space-y-3">
            <Field label="Code (e.g. GR1)"><input data-testid="grade-code" required maxLength={12} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" /></Field>
            <Field label="Name"><input data-testid="grade-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
            <Field label="Cadre"><input value={form.cadre} onChange={(e) => setForm({ ...form, cadre: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setOpen(false)} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="grade-submit" type="submit" className="text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2 rounded-md">Create</button>
            </div>
          </form>
        </Modal>
      )}

      {editing && (
        <Modal title={`Step schedule · ${editing.grade.code}`} onClose={() => setEditing(null)} wide>
          <div className="space-y-3">
            {editing.steps.map((s, i) => (
              <div key={s._uid || `step-${i}`} className="grid grid-cols-3 gap-3 items-center">
                <input type="number" min="1" max="20" value={s.step_number} onChange={(e) => {
                  const next = [...editing.steps]; next[i] = { ...next[i], step_number: e.target.value };
                  setEditing({ ...editing, steps: next });
                }} className="bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
                <input type="number" min="0" step="50" value={s.monthly_amount_sle} onChange={(e) => {
                  const next = [...editing.steps]; next[i] = { ...next[i], monthly_amount_sle: e.target.value };
                  setEditing({ ...editing, steps: next });
                }} className="col-span-2 bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" placeholder="Monthly SLE" />
              </div>
            ))}
            <button type="button" onClick={() => setEditing({ ...editing, steps: [...editing.steps, { _uid: `new-${Date.now()}`, step_number: editing.steps.length + 1, monthly_amount_sle: 0 }] })} className="text-xs text-[#26547C] hover:underline inline-flex items-center gap-1">
              <Plus className="w-3.5 h-3.5" /> Add step
            </button>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setEditing(null)} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="steps-save" onClick={() => saveSteps(editing.grade.code, editing.steps)} className="text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2 rounded-md">Save schedule</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// =============== Allowance Rules ===============

function AllowancesTab() {
  const [rules, setRules] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ kind: "housing", label: "", flat_sle: "", pct_of_basic: "", enabled: true });

  const load = useCallback(async () => {
    const r = await api.get("/civil-service/allowance-rules");
    setRules(r.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    const payload = { kind: form.kind, label: form.label, enabled: form.enabled };
    if (form.flat_sle) payload.flat_sle = Number(form.flat_sle);
    else if (form.pct_of_basic) payload.pct_of_basic = Number(form.pct_of_basic);
    try {
      await api.post("/civil-service/allowance-rules", payload);
      toast.success("Allowance rule created");
      setOpen(false); setForm({ kind: "housing", label: "", flat_sle: "", pct_of_basic: "", enabled: true }); load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not create");
    }
  };

  const remove = async (rid) => {
    if (!window.confirm("Delete this rule?")) return;
    await api.delete(`/civil-service/allowance-rules/${rid}`);
    toast.success("Deleted"); load();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xl font-semibold">Allowance rules</h2>
        <button data-testid="allowance-new" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white text-sm px-4 py-2 rounded-md">
          <Plus className="w-4 h-4" /> New rule
        </button>
      </div>
      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Kind", "Label", "Amount", "Restricted to grades", "Enabled", ""].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id} className="border-t border-[#E2DFD6]" data-testid={`rule-row-${r.id}`}>
                <td className="py-3 px-4 capitalize text-[#26547C]">{r.kind}</td>
                <td className="py-3 px-4 font-medium">{r.label}</td>
                <td className="py-3 px-4 font-data">
                  {r.flat_sle ? fmtSLE(r.flat_sle) : `${(r.pct_of_basic * 100).toFixed(0)}% of basic`}
                </td>
                <td className="py-3 px-4 font-data text-xs">{r.applies_to_grades?.length ? r.applies_to_grades.join(", ") : "All"}</td>
                <td className="py-3 px-4">
                  <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${r.enabled ? "bg-[#E6F4EC] text-[#2D7A5D]" : "bg-[#EBE8E0] text-[#525860]"}`}>{r.enabled ? "On" : "Off"}</span>
                </td>
                <td className="py-3 px-4 text-right">
                  <button onClick={() => remove(r.id)} className="text-xs text-[#B83A3A] hover:underline"><Trash2 className="w-3.5 h-3.5 inline" /></button>
                </td>
              </tr>
            ))}
            {!rules.length && <tr><td colSpan={6} className="py-12 text-center text-sm text-[#686D76]">No allowance rules.</td></tr>}
          </tbody>
        </table>
      </div>

      {open && (
        <Modal title="New allowance rule" onClose={() => setOpen(false)}>
          <form onSubmit={submit} className="space-y-3">
            <Field label="Kind">
              <select data-testid="rule-kind" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                <option value="housing">Housing</option>
                <option value="transport">Transport</option>
                <option value="responsibility">Responsibility</option>
                <option value="hardship">Hardship-posting</option>
                <option value="acting">Acting (legacy)</option>
              </select>
            </Field>
            <Field label="Label"><input data-testid="rule-label" required value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
            <Field label="Flat SLE (leave blank for percent-of-basic)"><input data-testid="rule-flat" type="number" min="0" value={form.flat_sle} onChange={(e) => setForm({ ...form, flat_sle: e.target.value, pct_of_basic: "" })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" /></Field>
            <Field label="% of basic (0.15 = 15%)"><input data-testid="rule-pct" type="number" min="0" max="2" step="0.01" value={form.pct_of_basic} onChange={(e) => setForm({ ...form, pct_of_basic: e.target.value, flat_sle: "" })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" /></Field>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setOpen(false)} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="rule-submit" type="submit" className="text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2 rounded-md">Create</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

// =============== Budget Codes ===============

function BudgetCodesTab() {
  const [codes, setCodes] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", ministry: "", program: "", fiscal_year: 2026 });

  const load = useCallback(async () => {
    const r = await api.get("/civil-service/budget-codes");
    setCodes(r.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/civil-service/budget-codes", { ...form, fiscal_year: Number(form.fiscal_year) });
      toast.success("Budget code created");
      setOpen(false); setForm({ code: "", name: "", ministry: "", program: "", fiscal_year: 2026 }); load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not create");
    }
  };

  const remove = async (code) => {
    if (!window.confirm(`Delete budget code ${code}?`)) return;
    try {
      await api.delete(`/civil-service/budget-codes/${code}`);
      toast.success("Deleted"); load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Cannot delete");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xl font-semibold">MDA budget codes</h2>
        <button data-testid="budget-new" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white text-sm px-4 py-2 rounded-md">
          <Plus className="w-4 h-4" /> New code
        </button>
      </div>
      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Code", "Name", "Ministry", "Programme", "FY", ""].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {codes.map((c) => (
              <tr key={c.code} className="border-t border-[#E2DFD6]" data-testid={`budget-row-${c.code}`}>
                <td className="py-3 px-4 font-data font-semibold">{c.code}</td>
                <td className="py-3 px-4 font-medium">{c.name}</td>
                <td className="py-3 px-4 text-[#525860]">{c.ministry}</td>
                <td className="py-3 px-4 text-[#525860]">{c.program}</td>
                <td className="py-3 px-4 font-data">{c.fiscal_year || "—"}</td>
                <td className="py-3 px-4 text-right">
                  <button onClick={() => remove(c.code)} className="text-xs text-[#B83A3A] hover:underline"><Trash2 className="w-3.5 h-3.5 inline" /></button>
                </td>
              </tr>
            ))}
            {!codes.length && <tr><td colSpan={6} className="py-12 text-center text-sm text-[#686D76]">No budget codes.</td></tr>}
          </tbody>
        </table>
      </div>

      {open && (
        <Modal title="New budget code" onClose={() => setOpen(false)}>
          <form onSubmit={submit} className="space-y-3">
            <Field label="Code (e.g. 110.01.001)"><input data-testid="budget-code" required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" /></Field>
            <Field label="Name"><input data-testid="budget-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
            <Field label="Ministry"><input value={form.ministry} onChange={(e) => setForm({ ...form, ministry: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
            <Field label="Programme"><input value={form.program} onChange={(e) => setForm({ ...form, program: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
            <Field label="Fiscal year"><input type="number" min="2024" max="2100" value={form.fiscal_year} onChange={(e) => setForm({ ...form, fiscal_year: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" /></Field>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setOpen(false)} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="budget-submit" type="submit" className="text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2 rounded-md">Create</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

// =============== Acting Allowances ===============

function ActingsTab() {
  const [actings, setActings] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ employee_id: "", acting_role_title: "", monthly_allowance_sle: 0, start_date: new Date().toISOString().split("T")[0], end_date: "" });

  const load = useCallback(async () => {
    const [a, e] = await Promise.all([api.get("/civil-service/actings"), api.get("/employees")]);
    setActings(a.data);
    setEmployees(e.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form, monthly_allowance_sle: Number(form.monthly_allowance_sle) };
      if (!payload.end_date) delete payload.end_date;
      await api.post("/civil-service/actings", payload);
      toast.success("Acting role created");
      setOpen(false);
      setForm({ employee_id: "", acting_role_title: "", monthly_allowance_sle: 0, start_date: new Date().toISOString().split("T")[0], end_date: "" });
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not create");
    }
  };

  const remove = async (aid) => {
    if (!window.confirm("Delete this acting allowance?")) return;
    await api.delete(`/civil-service/actings/${aid}`);
    toast.success("Deleted"); load();
  };

  const today = new Date().toISOString().split("T")[0];
  const isActive = (a) => a.start_date <= today && (!a.end_date || a.end_date >= today);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-heading text-xl font-semibold">Acting allowances</h2>
          <p className="text-xs text-[#686D76] mt-0.5">Temporary acting-in-role allowances automatically appear on payslips during the active period.</p>
        </div>
        <button data-testid="acting-new" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white text-sm px-4 py-2 rounded-md">
          <Plus className="w-4 h-4" /> New acting
        </button>
      </div>
      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Employee", "Acting role", "Monthly allowance", "Start", "End", "Status", ""].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {actings.map((a) => (
              <tr key={a.id} className="border-t border-[#E2DFD6]" data-testid={`acting-row-${a.id}`}>
                <td className="py-3 px-4 font-medium">{a.employee_name}</td>
                <td className="py-3 px-4 text-[#525860]">{a.acting_role_title}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(a.monthly_allowance_sle)}</td>
                <td className="py-3 px-4 font-data">{a.start_date}</td>
                <td className="py-3 px-4 font-data">{a.end_date || <span className="text-[#A1A5AB]">open</span>}</td>
                <td className="py-3 px-4">
                  <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${isActive(a) ? "bg-[#E6F4EC] text-[#2D7A5D]" : "bg-[#EBE8E0] text-[#525860]"}`}>{isActive(a) ? "Active" : "Inactive"}</span>
                </td>
                <td className="py-3 px-4 text-right">
                  <button onClick={() => remove(a.id)} className="text-xs text-[#B83A3A] hover:underline"><Trash2 className="w-3.5 h-3.5 inline" /></button>
                </td>
              </tr>
            ))}
            {!actings.length && <tr><td colSpan={7} className="py-12 text-center text-sm text-[#686D76]">No acting allowances configured.</td></tr>}
          </tbody>
        </table>
      </div>
      {open && (
        <Modal title="New acting allowance" onClose={() => setOpen(false)}>
          <form onSubmit={submit} className="space-y-3">
            <Field label="Employee">
              <select data-testid="acting-employee" required value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                <option value="">— Select —</option>
                {employees.map((em) => <option key={em.id} value={em.id}>{em.first_name} {em.last_name} · {em.job_title}</option>)}
              </select>
            </Field>
            <Field label="Acting role title">
              <input data-testid="acting-role" required value={form.acting_role_title} onChange={(e) => setForm({ ...form, acting_role_title: e.target.value })} placeholder="e.g. Acting Director General" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
            </Field>
            <Field label="Monthly allowance (SLE)">
              <input data-testid="acting-amount" required type="number" min="0" step="50" value={form.monthly_allowance_sle} onChange={(e) => setForm({ ...form, monthly_allowance_sle: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Start date">
                <input required type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
              </Field>
              <Field label="End date (optional)">
                <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
              </Field>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setOpen(false)} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="acting-submit" type="submit" className="text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2 rounded-md">Create</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

// =============== Step Increments ===============

function IncrementsTab() {
  const [history, setHistory] = useState([]);
  const [preview, setPreview] = useState(null);
  const [targetDate, setTargetDate] = useState(new Date().toISOString().split("T")[0]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const r = await api.get("/civil-service/step-increments/history");
    setHistory(r.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const runDry = async () => {
    setBusy(true);
    try {
      const r = await api.post("/civil-service/step-increments/run", { dry_run: true, target_date: targetDate });
      setPreview(r.data);
      if (r.data.count === 0) toast.info("No employees eligible on this date");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Preview failed");
    } finally { setBusy(false); }
  };

  const apply = async () => {
    if (!window.confirm(`Apply step increments to ${preview.count} employee(s)? This will bump their basic salary.`)) return;
    setBusy(true);
    try {
      const r = await api.post("/civil-service/step-increments/run", { dry_run: false, target_date: targetDate });
      toast.success(`Applied ${r.data.count} step increments`);
      setPreview(null); load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Apply failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-heading text-xl font-semibold">Annual step increments</h2>
        <p className="text-xs text-[#686D76] mt-0.5">Automatically bumps each civil servant by +1 step on their work anniversary. Runs daily at 02:00 UTC; admins can also preview/apply manually.</p>
      </div>
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-5">
        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Target date</label>
            <input data-testid="increment-target-date" type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} className="bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
          </div>
          <button data-testid="increment-preview" disabled={busy} onClick={runDry} className="inline-flex items-center gap-2 bg-white border border-[#26547C] text-[#26547C] hover:bg-[#E5EEF6] text-sm px-4 py-2 rounded-md disabled:opacity-50">
            <Play className="w-4 h-4" /> Preview eligibility
          </button>
          {preview && preview.count > 0 && (
            <button data-testid="increment-apply" disabled={busy} onClick={apply} className="inline-flex items-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white text-sm px-4 py-2 rounded-md disabled:opacity-50">
              Apply {preview.count} increment{preview.count > 1 ? "s" : ""}
            </button>
          )}
        </div>
        {preview && preview.count > 0 && (
          <div data-testid="increment-preview-table" className="mt-5">
            <div className="text-sm font-medium mb-2 text-[#1A1C1E]">{preview.count} employee{preview.count > 1 ? "s" : ""} eligible:</div>
            <table className="w-full text-xs border border-[#E2DFD6] rounded">
              <thead className="bg-[#F7F6F2]">
                <tr>{["Employee", "Grade", "From step", "To step", "Δ SLE"].map((h) => (
                  <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2 px-3 font-medium">{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {preview.applied.map((a) => (
                  <tr key={a.employee_id} className="border-t border-[#E2DFD6]" data-testid={`increment-row-${a.employee_id}`}>
                    <td className="py-2 px-3 font-medium">{a.employee_name}</td>
                    <td className="py-2 px-3 font-data">{a.grade_code}</td>
                    <td className="py-2 px-3 font-data">{a.from_step}</td>
                    <td className="py-2 px-3 font-data text-[#2D7A5D] font-semibold">{a.to_step}</td>
                    <td className="py-2 px-3 font-data text-[#26547C]">+{fmtSLE(a.delta_sle)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {preview && preview.count === 0 && (
          <div className="mt-4 text-sm text-[#686D76] bg-[#F7F6F2] rounded-md px-3 py-2">No employees have an anniversary on {targetDate}.</div>
        )}
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-6 py-3 border-b border-[#E2DFD6]">
          <h3 className="font-heading text-sm font-semibold">Increment history</h3>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Date", "Employee", "Grade", "Step", "Basic delta", "Applied by"].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={`${h.employee_id}-${h.year}`} className="border-t border-[#E2DFD6]">
                <td className="py-2.5 px-4 font-data text-xs">{(h.applied_at || "").slice(0, 10)}</td>
                <td className="py-2.5 px-4 font-medium">{h.employee_name}</td>
                <td className="py-2.5 px-4 font-data">{h.grade_code}</td>
                <td className="py-2.5 px-4 font-data">{h.from_step} → {h.to_step}</td>
                <td className="py-2.5 px-4 font-data text-[#2D7A5D]">+{fmtSLE(h.delta_sle)}</td>
                <td className="py-2.5 px-4 text-xs text-[#525860]">{h.applied_by}</td>
              </tr>
            ))}
            {!history.length && <tr><td colSpan={6} className="py-10 text-center text-sm text-[#686D76]">No step increments recorded yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =============== Ghost-worker Audit ===============

function GhostsTab() {
  const [runs, setRuns] = useState([]);
  const [selected, setSelected] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get("/payroll/runs").then((r) => setRuns(r.data));
  }, []);

  const loadReport = async (rid) => {
    setSelected(rid); setLoading(true); setReport(null);
    try {
      const r = await api.get(`/civil-service/ghost-workers/${rid}`);
      setReport(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not load report");
    } finally { setLoading(false); }
  };

  const downloadReport = async (kind) => {
    if (!selected) return;
    const url = `/civil-service/ghost-workers/${selected}.${kind}`;
    try {
      const resp = await api.get(url, { responseType: "blob" });
      const blob = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = blob; a.download = `ghost-worker-${report?.period || "report"}.${kind}`; a.click();
      URL.revokeObjectURL(blob);
    } catch (e) {
      toast.error("Download failed");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="font-heading text-xl font-semibold">Ghost-worker audit</h2>
          <p className="text-xs text-[#686D76] mt-0.5">Employees who never acknowledged their payslip — potential ghost workers.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select data-testid="ghost-run-select" value={selected || ""} onChange={(e) => e.target.value && loadReport(e.target.value)} className="bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
            <option value="">Select payroll run…</option>
            {runs.map((r) => <option key={r.id} value={r.id}>{r.period} — {r.totals?.employee_count} slips</option>)}
          </select>
          {report && (
            <>
              <button data-testid="ghost-pdf" onClick={() => downloadReport("pdf")} className="inline-flex items-center gap-1.5 text-xs bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#133326] px-3 py-2 rounded-md">
                <FileText className="w-3.5 h-3.5" /> PDF
              </button>
              <button data-testid="ghost-csv" onClick={() => downloadReport("csv")} className="inline-flex items-center gap-1.5 text-xs bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#133326] px-3 py-2 rounded-md">
                <Download className="w-3.5 h-3.5" /> CSV
              </button>
            </>
          )}
        </div>
      </div>

      {loading && <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center text-sm text-[#686D76]">Loading…</div>}

      {report && (
        <div data-testid="ghost-report">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Kpi label="Total slips" value={report.total_slips} />
            <Kpi label="Acknowledged" value={report.acknowledged} tone="success" />
            <Kpi label="Ghost suspects" value={report.ghost_suspects} tone={report.ghost_suspects > 0 ? "danger" : "muted"} />
            <Kpi label="Unack rate" value={`${(report.ghost_rate * 100).toFixed(0)}%`} tone={report.ghost_rate > 0.3 ? "danger" : "muted"} />
          </div>
          {report.suspects.length > 0 && (
            <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
              <div className="px-6 py-3 bg-[#FBEAEA] border-b border-[#F2D0D0] flex items-center gap-2 text-sm text-[#B83A3A]">
                <AlertTriangle className="w-4 h-4" /> {report.ghost_suspects} unacknowledged payslip{report.ghost_suspects !== 1 ? "s" : ""} totalling {fmtSLE(report.suspects.reduce((a, s) => a + s.net_unacknowledged_sle, 0))} in net pay
              </div>
              <table className="w-full text-sm">
                <thead className="bg-[#F7F6F2]">
                  <tr>{["Employee", "Department", "Ministry", "Grade", "Budget code", "Net (SLE)", "Hire date"].map((h) => (
                    <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-4 font-medium">{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {report.suspects.map((s) => (
                    <tr key={s.employee_id} className="border-t border-[#E2DFD6]" data-testid={`ghost-row-${s.employee_id}`}>
                      <td className="py-2.5 px-4 font-medium">{s.employee_name}</td>
                      <td className="py-2.5 px-4 text-[#525860] text-xs">{s.department || "—"}</td>
                      <td className="py-2.5 px-4 text-[#525860] text-xs">{s.ministry || "—"}</td>
                      <td className="py-2.5 px-4 font-data text-xs">{s.grade_code || "—"}</td>
                      <td className="py-2.5 px-4 font-data text-xs">{s.budget_code || "—"}</td>
                      <td className="py-2.5 px-4 font-data font-semibold text-[#B83A3A]">{fmtSLE(s.net_unacknowledged_sle)}</td>
                      <td className="py-2.5 px-4 font-data text-xs">{s.hire_date || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!report.suspects.length && (
            <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center">
              <CheckCircle2 className="w-12 h-12 mx-auto text-[#2D7A5D]" strokeWidth={1.3} />
              <div className="font-heading text-lg font-semibold mt-3">No ghost workers detected</div>
              <p className="text-sm text-[#525860] mt-1">All employees acknowledged this period&rsquo;s payslips.</p>
            </div>
          )}
        </div>
      )}
      {!report && !loading && !selected && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center text-sm text-[#686D76]">Select a payroll run to audit.</div>
      )}
    </div>
  );
}

// =============== Helpers ===============

function Modal({ title, children, onClose, wide }) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className={`bg-white rounded-lg w-full ${wide ? "max-w-2xl" : "max-w-md"} p-6`}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-heading text-xl font-semibold">{title}</h3>
          <button onClick={onClose} className="text-[#525860] hover:text-[#1A1C1E]"><X className="w-4 h-4" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  );
}

function Kpi({ label, value, tone }) {
  const tones = {
    success: "text-[#2D7A5D]",
    danger: "text-[#B83A3A]",
    muted: "text-[#525860]",
  };
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-4">
      <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{label}</div>
      <div className={`font-heading text-2xl font-bold mt-1 font-data ${tones[tone] || "text-[#1A1C1E]"}`}>{value}</div>
    </div>
  );
}
