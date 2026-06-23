import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { useFeatures } from "../lib/features";
import { toast } from "sonner";
import {
  Building2, ChevronDown, ChevronRight, Plus, X, AlertTriangle, Pencil, Trash2, Lock, Unlock,
} from "lucide-react";

export default function Establishment() {
  const { has } = useFeatures();
  const [tree, setTree] = useState({ ministries: [] });
  const [overruns, setOverruns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({});
  const [editing, setEditing] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const [t, o] = await Promise.all([
      api.get("/establishment/tree"),
      api.get("/establishment/overruns"),
    ]);
    setTree(t.data);
    setOverruns(o.data);
    setLoading(false);
  }, []);

  useEffect(() => { if (has("establishment_control")) refresh(); }, [refresh, has]);

  if (!has("establishment_control")) {
    return <FeatureLocked />;
  }

  const totalApproved = tree.ministries.reduce((a, m) => a + m.approved_count, 0);
  const totalFilled = tree.ministries.reduce((a, m) => a + m.filled_count, 0);
  const totalVacancy = totalApproved - totalFilled;

  return (
    <div className="space-y-6" data-testid="establishment-page">
      <Header
        totalApproved={totalApproved}
        totalFilled={totalFilled}
        totalVacancy={totalVacancy}
        ministries={tree.ministries.length}
        overruns={overruns.length}
        onNew={() => setEditing({})}
      />

      {overruns.length > 0 && <OverrunBanner overruns={overruns} />}

      {loading && <div className="text-sm text-[#525860]">Loading establishment…</div>}

      {!loading && tree.ministries.length === 0 && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center" data-testid="establishment-empty">
          <Building2 className="w-10 h-10 text-[#A1A5AB] mx-auto mb-3" strokeWidth={1.4} />
          <p className="text-sm text-[#525860]">No positions yet. Create your first establishment position to start tracking approved vs. filled headcount.</p>
          <button onClick={() => setEditing({})} className="mt-4 inline-flex items-center gap-1.5 bg-[#133326] text-white text-sm px-4 py-2 rounded-md">
            <Plus className="w-4 h-4" /> New position
          </button>
        </div>
      )}

      {!loading && tree.ministries.map((m) => (
        <MinistryCard
          key={m.name}
          ministry={m}
          expanded={expanded}
          setExpanded={setExpanded}
          onEdit={setEditing}
          onRefresh={refresh}
        />
      ))}

      {editing !== null && (
        <PositionModal
          initial={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); refresh(); }}
        />
      )}
    </div>
  );
}

function FeatureLocked() {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center">
      <Lock className="w-10 h-10 text-[#A1A5AB] mx-auto mb-3" strokeWidth={1.4} />
      <h3 className="font-heading text-xl">Establishment Control</h3>
      <p className="text-sm text-[#525860] mt-2 max-w-md mx-auto">
        Ministry → Directorate → Unit → Position headcount tracking is available on Enterprise and Government tiers.
      </p>
    </div>
  );
}

function Header({ totalApproved, totalFilled, totalVacancy, ministries, overruns, onNew }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Workforce planning</div>
          <h1 className="font-heading text-3xl font-bold mt-1">Establishment Control</h1>
          <p className="text-sm text-[#525860] mt-1 max-w-2xl">
            Tracks approved positions vs. who&rsquo;s actually on payroll. Vacancies highlight recruitment needs;
            overruns are an audit red flag for ghost-worker exposure.
          </p>
        </div>
        <button data-testid="establishment-new" onClick={onNew} className="inline-flex items-center gap-1.5 bg-[#133326] hover:bg-[#0F281E] text-white text-sm px-4 py-2.5 rounded-md">
          <Plus className="w-4 h-4" /> New position
        </button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-5">
        <KPI label="Ministries" value={ministries} />
        <KPI label="Approved" value={totalApproved} color="text-[#26547C]" />
        <KPI label="Filled" value={totalFilled} color="text-[#2D7A5D]" />
        <KPI label="Vacant" value={totalVacancy} color="text-[#8B6A14]" />
        <KPI label="Overruns" value={overruns} color={overruns > 0 ? "text-[#B83A3A]" : "text-[#2D7A5D]"} />
      </div>
    </div>
  );
}

function KPI({ label, value, color = "text-[#1A1C1E]" }) {
  return (
    <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-3">
      <div className="text-[10px] uppercase tracking-wider text-[#525860]">{label}</div>
      <div className={`font-heading text-2xl font-bold mt-1 font-data ${color}`}>{value}</div>
    </div>
  );
}

function OverrunBanner({ overruns }) {
  return (
    <div data-testid="establishment-overrun-banner" className="bg-[#FBEAEA] border border-[#E8A29C] rounded-md p-4 flex items-start gap-3">
      <AlertTriangle className="w-5 h-5 text-[#B83A3A] flex-shrink-0 mt-0.5" />
      <div className="text-sm">
        <div className="font-semibold text-[#8B2418]">{overruns.length} position(s) over-filled</div>
        <div className="text-[#7A2F26] text-xs mt-1">
          More employees are assigned than approved headcount allows. Investigate immediately —
          common causes: stale terminations, double-counting, or ghost workers.
        </div>
        <ul className="text-xs text-[#7A2F26] mt-2 space-y-0.5">
          {overruns.slice(0, 5).map((p) => (
            <li key={p.id} className="font-data">• {p.ministry} → {p.position_title}: <strong>{p.filled_count}/{p.approved_count}</strong> ({p.overrun_count} over)</li>
          ))}
          {overruns.length > 5 && <li>+ {overruns.length - 5} more</li>}
        </ul>
      </div>
    </div>
  );
}

function MinistryCard({ ministry, expanded, setExpanded, onEdit, onRefresh }) {
  const open = expanded[ministry.name] ?? true;
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid={`ministry-${ministry.name}`}>
      <button
        onClick={() => setExpanded((e) => ({ ...e, [ministry.name]: !open }))}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-[#F7F6F2]"
      >
        <div className="flex items-center gap-3">
          {open ? <ChevronDown className="w-4 h-4 text-[#525860]" /> : <ChevronRight className="w-4 h-4 text-[#525860]" />}
          <Building2 className="w-5 h-5 text-[#133326]" strokeWidth={1.5} />
          <div className="text-left">
            <h3 className="font-heading text-lg font-semibold">{ministry.name}</h3>
            <p className="text-xs text-[#525860]">
              {ministry.directorates.length} directorates · {ministry.filled_count}/{ministry.approved_count} filled · {ministry.vacancy_count} vacant
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <FillPill filled={ministry.filled_count} approved={ministry.approved_count} />
        </div>
      </button>
      {open && (
        <div className="border-t border-[#E2DFD6] divide-y divide-[#F1EEE6]">
          {ministry.directorates.map((d) => (
            <DirectorateRow key={d.name} directorate={d} onEdit={onEdit} onRefresh={onRefresh} />
          ))}
        </div>
      )}
    </div>
  );
}

function DirectorateRow({ directorate, onEdit, onRefresh }) {
  const [open, setOpen] = useState(false);
  return (
    <div data-testid={`directorate-${directorate.name}`}>
      <button onClick={() => setOpen((v) => !v)} className="w-full px-8 py-3 flex items-center justify-between hover:bg-[#F7F6F2] text-left">
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="w-3.5 h-3.5 text-[#525860]" /> : <ChevronRight className="w-3.5 h-3.5 text-[#525860]" />}
          <div>
            <div className="font-medium text-sm">{directorate.name}</div>
            <div className="text-[11px] text-[#686D76]">{directorate.units.length} units · {directorate.filled_count}/{directorate.approved_count} filled</div>
          </div>
        </div>
        <FillPill filled={directorate.filled_count} approved={directorate.approved_count} small />
      </button>
      {open && (
        <div className="bg-[#FBFAF6] divide-y divide-[#F1EEE6]">
          {directorate.units.map((u) => (
            <UnitBlock key={u.name} unit={u} onEdit={onEdit} onRefresh={onRefresh} />
          ))}
        </div>
      )}
    </div>
  );
}

function UnitBlock({ unit, onEdit, onRefresh }) {
  return (
    <div className="px-10 py-3">
      <div className="text-[10px] uppercase tracking-wider text-[#525860] mb-1.5">{unit.name} · {unit.filled_count}/{unit.approved_count}</div>
      <table className="w-full text-xs">
        <thead>
          <tr>{["Position", "Grade", "Budget code", "Filled / Approved", "Status", ""].map((h) => (
            <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#686D76] py-1.5 font-medium">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {unit.positions.map((p) => (
            <PositionRow key={p.id} position={p} onEdit={onEdit} onRefresh={onRefresh} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PositionRow({ position, onEdit, onRefresh }) {
  const onDelete = async () => {
    if (!window.confirm(`Delete position "${position.position_title}"?`)) return;
    try {
      await api.delete(`/establishment/positions/${position.id}`);
      toast.success("Position deleted");
      onRefresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };
  return (
    <tr className="border-t border-[#F1EEE6]" data-testid={`position-${position.id}`}>
      <td className="py-2 font-medium">{position.position_title}</td>
      <td className="py-2 font-data">{position.grade_code || "—"}</td>
      <td className="py-2 font-data">{position.budget_code || "—"}</td>
      <td className="py-2 font-data">
        <span className={position.overrun_count > 0 ? "text-[#B83A3A] font-semibold" : ""}>
          {position.filled_count}
        </span>
        <span className="text-[#A1A5AB]"> / {position.approved_count}</span>
        {position.overrun_count > 0 && (
          <span className="ml-2 text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-[#FBEAEA] text-[#B83A3A]">+{position.overrun_count} OVER</span>
        )}
      </td>
      <td className="py-2">
        {position.status === "active" ? (
          <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-[#2D7A5D]"><Unlock className="w-3 h-3" /> Active</span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-[#525860]"><Lock className="w-3 h-3" /> Frozen</span>
        )}
      </td>
      <td className="py-2 text-right">
        <button onClick={() => onEdit(position)} className="p-1 hover:bg-[#F1EEE6] rounded" title="Edit"><Pencil className="w-3.5 h-3.5 text-[#525860]" /></button>
        <button onClick={onDelete} className="p-1 hover:bg-[#FBEAEA] rounded" title="Delete"><Trash2 className="w-3.5 h-3.5 text-[#B83A3A]" /></button>
      </td>
    </tr>
  );
}

function FillPill({ filled, approved, small }) {
  const pct = approved ? filled / approved : 0;
  let color;
  if (pct >= 1) color = "bg-[#E6F4EC] text-[#2D7A5D]";
  else if (pct >= 0.7) color = "bg-[#E5EEF6] text-[#26547C]";
  else color = "bg-[#FBF1DE] text-[#8B6A14]";
  return (
    <span className={`inline-flex items-center text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full font-medium ${color} ${small ? "" : ""}`}>
      {Math.round(pct * 100)}% filled
    </span>
  );
}

function PositionModal({ initial, onClose, onSaved }) {
  const isNew = !initial.id;
  const [form, setForm] = useState({
    ministry: initial.ministry || "",
    directorate: initial.directorate || "",
    unit: initial.unit || "",
    position_title: initial.position_title || "",
    grade_code: initial.grade_code || "",
    step_number: initial.step_number || "",
    approved_count: initial.approved_count ?? 1,
    budget_code: initial.budget_code || "",
    status: initial.status || "active",
  });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = { ...form };
      payload.approved_count = Number(payload.approved_count);
      if (payload.step_number === "") delete payload.step_number;
      else payload.step_number = Number(payload.step_number);
      Object.keys(payload).forEach((k) => { if (payload[k] === "") delete payload[k]; });
      if (isNew) {
        await api.post("/establishment/positions", payload);
        toast.success("Position created");
      } else {
        await api.patch(`/establishment/positions/${initial.id}`, payload);
        toast.success("Position updated");
      }
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => !busy && onClose()}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="bg-white rounded-lg w-full max-w-xl p-6 space-y-3" data-testid="position-modal">
        <div className="flex items-center justify-between">
          <h3 className="font-heading text-xl">{isNew ? "Create position" : `Edit · ${initial.position_title}`}</h3>
          <button type="button" onClick={onClose} className="text-[#525860]"><X className="w-4 h-4" /></button>
        </div>
        <Field label="Ministry" required value={form.ministry} onChange={(v) => setForm({ ...form, ministry: v })} testid="pos-ministry" />
        <Field label="Directorate" required value={form.directorate} onChange={(v) => setForm({ ...form, directorate: v })} testid="pos-directorate" />
        <Field label="Unit" required value={form.unit} onChange={(v) => setForm({ ...form, unit: v })} testid="pos-unit" />
        <Field label="Position title" required value={form.position_title} onChange={(v) => setForm({ ...form, position_title: v })} testid="pos-title" />
        <div className="grid grid-cols-2 gap-3">
          <Field label="Grade code" value={form.grade_code} onChange={(v) => setForm({ ...form, grade_code: v })} testid="pos-grade" />
          <Field label="Step (1-30)" type="number" value={form.step_number} onChange={(v) => setForm({ ...form, step_number: v })} testid="pos-step" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Approved count" required type="number" value={form.approved_count} onChange={(v) => setForm({ ...form, approved_count: v })} testid="pos-approved" />
          <Field label="Budget code" value={form.budget_code} onChange={(v) => setForm({ ...form, budget_code: v })} testid="pos-budget" />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wider text-[#525860] block mb-1">Status</label>
          <select data-testid="pos-status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
                  className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
            <option value="active">Active</option>
            <option value="frozen">Frozen</option>
          </select>
        </div>
        <div className="flex justify-end gap-2 pt-3">
          <button type="button" onClick={onClose} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Cancel</button>
          <button data-testid="pos-save" type="submit" disabled={busy} className="text-sm bg-[#133326] text-white px-4 py-2 rounded-md disabled:opacity-60">
            {busy ? "Saving…" : isNew ? "Create" : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, value, onChange, required, type, testid }) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider text-[#525860] block mb-1">{label}{required && <span className="text-[#B83A3A] ml-0.5">*</span>}</label>
      <input
        data-testid={testid}
        required={required}
        type={type || "text"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
      />
    </div>
  );
}
