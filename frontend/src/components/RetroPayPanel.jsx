import { useCallback, useEffect, useState } from "react";
import api, { fmtSLE } from "../lib/api";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import {
  Plus, Trash2, CheckCircle2, XCircle, AlertTriangle, X, Send,
  Wallet, Loader2, ShieldCheck, Clock,
} from "lucide-react";

const SOURCE_LABEL = {
  grade_change: "Grade change",
  step_increment: "Step increment",
  acting: "Acting allowance",
  manual: "Manual",
};

const STATUS_STYLE = {
  pending: "bg-[#E6EEF6] text-[#26547C]",
  pending_approval: "bg-[#FBF1DE] text-[#8B6A14]",
  rejected: "bg-[#FBEAEA] text-[#8C2F2F]",
  settled: "bg-[#E6F4EC] text-[#2D7A5D]",
};

/** Retro-pay CRUD panel — Option C UI polish.
 *  Lets admins list, create, MoF-approve/reject, and delete pending retro-pay
 *  adjustments. Settled rows are read-only (historical audit record). */
export default function RetroPayPanel() {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [busy, setBusy] = useState(true);
  const [filter, setFilter] = useState("all");
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [r1, r2] = await Promise.all([
        api.get("/civil-service/retro-pay"),
        api.get("/employees"),
      ]);
      setRows(r1.data);
      setEmployees(r2.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load retro-pay");
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = filter === "all" ? rows : rows.filter((r) => r.status === filter);

  const del = async (rid) => {
    if (!window.confirm("Delete this pending retro adjustment?")) return;
    try {
      await api.delete(`/civil-service/retro-pay/${rid}`);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  const decide = async (rid, approve) => {
    const note = approve
      ? window.prompt("Optional approval note?", "")
      : window.prompt("Rejection reason? (required)", "");
    if (!approve && !note) return;
    try {
      await api.post(`/civil-service/retro-pay/${rid}/approve`, {
        id: rid, approve, note: note || "",
      });
      toast.success(approve ? "Approved" : "Rejected");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Action failed");
    }
  };

  return (
    <div className="space-y-4" data-testid="retro-pay-panel">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="font-heading text-xl font-bold flex items-center gap-2">
            <Wallet className="w-5 h-5 text-[#26547C]" strokeWidth={1.5} />
            Retro-pay adjustments
          </h2>
          <p className="text-sm text-[#525860] mt-1">
            Backdated grade/step/acting adjustments. Auto-settled on next payroll run. ≥10% of basic requires MoF approver sign-off.
          </p>
        </div>
        <button
          data-testid="retro-add-btn"
          onClick={() => setShowForm(true)}
          className="inline-flex items-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white text-sm px-4 py-2.5 rounded-md"
        >
          <Plus className="w-4 h-4" strokeWidth={1.7} /> New adjustment
        </button>
      </div>

      <div className="flex items-center gap-1 flex-wrap" data-testid="retro-filters">
        {[
          { id: "all", label: "All" },
          { id: "pending", label: "Pending settlement" },
          { id: "pending_approval", label: "Awaiting MoF" },
          { id: "settled", label: "Settled" },
          { id: "rejected", label: "Rejected" },
        ].map((f) => (
          <button
            key={f.id}
            data-testid={`retro-filter-${f.id}`}
            onClick={() => setFilter(f.id)}
            className={`text-xs px-3 py-1.5 rounded-full border transition ${
              filter === f.id
                ? "bg-[#133326] text-white border-[#133326]"
                : "bg-white text-[#525860] border-[#E2DFD6] hover:bg-[#F7F6F2]"
            }`}
          >{f.label}</button>
        ))}
      </div>

      {busy ? (
        <div className="py-16 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-[#133326]" /></div>
      ) : filtered.length === 0 ? (
        <div className="bg-white border border-[#E2DFD6] rounded-lg py-12 text-center" data-testid="retro-empty">
          <div className="w-12 h-12 rounded-full bg-[#F1EEE6] grid place-items-center mx-auto"><Wallet className="w-5 h-5 text-[#525860]" /></div>
          <p className="mt-3 text-sm text-[#525860]">No retro-pay adjustments in this view.</p>
        </div>
      ) : (
        <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#F7F6F2]">
              <tr>{[
                "Employee", "Source", "Period range", "Monthly Δ", "Total owed",
                "% of basic", "Status", "",
              ].map((h) => (
                <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-4 font-medium">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id} data-testid={`retro-row-${r.id}`} className="border-t border-[#F1EEE6]">
                  <td className="px-4 py-2.5 font-medium">{r.employee_name}</td>
                  <td className="px-4 py-2.5 text-[#525860] text-[13px]">{SOURCE_LABEL[r.source] || r.source}</td>
                  <td className="px-4 py-2.5 font-data text-[13px]">{r.effective_from} → {r.effective_to} <span className="text-[#686D76]">({r.months}m)</span></td>
                  <td className={`px-4 py-2.5 font-data ${r.monthly_delta_sle < 0 ? "text-[#8C2F2F]" : "text-[#26547C]"}`}>{r.monthly_delta_sle > 0 && "+"}{fmtSLE(r.monthly_delta_sle)}</td>
                  <td className="px-4 py-2.5 font-data font-semibold">{fmtSLE(r.total_owed_sle)}</td>
                  <td className={`px-4 py-2.5 font-data ${r.ratio_pct >= 10 ? "text-[#8C2F2F] font-semibold" : "text-[#525860]"}`}>{r.ratio_pct}%</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STATUS_STYLE[r.status] || "bg-[#EBE8E0] text-[#525860]"}`}>
                      {r.status.replace("_", " ")}
                    </span>
                    {r.status === "settled" && r.settled_run_id && (
                      <div className="text-[10px] text-[#686D76] mt-1 font-data">Run {r.settled_run_id.slice(0, 8)}</div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      {r.status === "pending_approval" && (user?.mof_approver || user?.role === "superadmin") && (
                        <>
                          <button
                            data-testid={`retro-approve-${r.id}`}
                            onClick={() => decide(r.id, true)}
                            title="MoF Approve"
                            className="text-[#2D7A5D] hover:bg-[#E6F4EC] p-1.5 rounded"
                          ><CheckCircle2 className="w-4 h-4" /></button>
                          <button
                            data-testid={`retro-reject-${r.id}`}
                            onClick={() => decide(r.id, false)}
                            title="Reject"
                            className="text-[#8C2F2F] hover:bg-[#FBEAEA] p-1.5 rounded"
                          ><XCircle className="w-4 h-4" /></button>
                        </>
                      )}
                      {r.status !== "settled" && (
                        <button
                          data-testid={`retro-del-${r.id}`}
                          onClick={() => del(r.id)}
                          title="Delete"
                          className="text-[#8C2F2F] hover:bg-[#FBEAEA] p-1.5 rounded"
                        ><Trash2 className="w-4 h-4" /></button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <RetroPayForm
          employees={employees}
          onClose={() => setShowForm(false)}
          onCreated={() => { setShowForm(false); load(); }}
        />
      )}
    </div>
  );
}

function RetroPayForm({ employees, onClose, onCreated }) {
  const nowY = new Date().getFullYear();
  const nowM = new Date().getMonth() + 1;
  const currentPeriod = `${nowY}-${String(nowM).padStart(2, "0")}`;
  const [form, setForm] = useState({
    employee_id: "",
    monthly_delta_sle: "",
    effective_from: currentPeriod,
    effective_to: currentPeriod,
    source: "manual",
    reason: "",
  });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/civil-service/retro-pay", {
        ...form,
        monthly_delta_sle: Number(form.monthly_delta_sle),
      });
      toast.success("Retro adjustment created");
      onCreated();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Create failed");
    } finally { setBusy(false); }
  };

  const upd = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" data-testid="retro-form-modal">
      <form onSubmit={submit} className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-lg p-6 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-[#525860]">Anti-fraud rail</div>
            <h3 className="font-heading text-lg font-semibold mt-0.5">Create retro-pay adjustment</h3>
            <p className="text-xs text-[#525860] mt-1">Adjustments &ge;10% of basic require an MoF approver&rsquo;s sign-off before settlement.</p>
          </div>
          <button type="button" onClick={onClose} className="text-[#525860]"><X className="w-4 h-4" /></button>
        </div>
        <Field label="Employee">
          <select data-testid="retro-emp" required value={form.employee_id} onChange={upd("employee_id")} className="w-full h-10 px-3 bg-white border border-[#E2DFD6] rounded-md text-sm">
            <option value="">Choose…</option>
            {employees.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name} — {e.department}</option>)}
          </select>
        </Field>
        <Field label="Monthly delta (SLE)">
          <input data-testid="retro-monthly" type="number" step="0.01" required value={form.monthly_delta_sle} onChange={upd("monthly_delta_sle")} placeholder="e.g. 250 for a grade-change owed each month" className="w-full h-10 px-3 bg-white border border-[#E2DFD6] rounded-md text-sm font-data" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Effective from (YYYY-MM)">
            <input data-testid="retro-from" pattern="^\d{4}-\d{2}$" required value={form.effective_from} onChange={upd("effective_from")} className="w-full h-10 px-3 bg-white border border-[#E2DFD6] rounded-md text-sm font-data" />
          </Field>
          <Field label="Effective to (YYYY-MM)">
            <input data-testid="retro-to" pattern="^\d{4}-\d{2}$" required value={form.effective_to} onChange={upd("effective_to")} className="w-full h-10 px-3 bg-white border border-[#E2DFD6] rounded-md text-sm font-data" />
          </Field>
        </div>
        <Field label="Source">
          <select data-testid="retro-source" value={form.source} onChange={upd("source")} className="w-full h-10 px-3 bg-white border border-[#E2DFD6] rounded-md text-sm">
            <option value="manual">Manual</option>
            <option value="grade_change">Grade change</option>
            <option value="step_increment">Step increment</option>
            <option value="acting">Acting allowance</option>
          </select>
        </Field>
        <Field label="Reason (min 10 chars)">
          <textarea data-testid="retro-reason" rows={3} minLength={10} maxLength={500} required value={form.reason} onChange={upd("reason")} placeholder="e.g. Grade change GR3→GR4 approved by MoF on 15-Jan, retroactive to Jan payroll." className="w-full px-3 py-2 bg-white border border-[#E2DFD6] rounded-md text-sm" />
        </Field>
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#F1EEE6]">
          <button type="button" onClick={onClose} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]">Cancel</button>
          <button type="submit" disabled={busy} data-testid="retro-submit" className="inline-flex items-center gap-2 bg-[#133326] hover:bg-[#0F281E] disabled:opacity-60 text-white text-sm px-4 py-2 rounded-md">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Create
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">{label}</label>
      {children}
    </div>
  );
}
