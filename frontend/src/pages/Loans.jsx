import { useEffect, useState, useCallback, useMemo } from "react";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useFeatures } from "../lib/features";
import { toast } from "sonner";
import {
  Wallet, Plus, X, Banknote, Clock, CheckCircle2, XCircle, Calendar,
} from "lucide-react";

const STATUS_PILL = {
  active: { color: "bg-[#E5EEF6] text-[#26547C]", icon: Clock, label: "Active" },
  paid: { color: "bg-[#E4F7E7] text-[#17A035]", icon: CheckCircle2, label: "Paid off" },
  cancelled: { color: "bg-[#EBE8E0] text-[#525860]", icon: XCircle, label: "Cancelled" },
  defaulted: { color: "bg-[#E9F2FB] text-[#3A7CB8]", icon: XCircle, label: "Defaulted" },
};

export default function Loans() {
  const { user } = useAuth();
  const { has } = useFeatures();
  const isAdmin = ["admin", "superadmin"].includes(user?.role);
  const [loans, setLoans] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [creating, setCreating] = useState(false);
  const [scheduleFor, setScheduleFor] = useState(null);

  const refresh = useCallback(async () => {
    const [l, e] = await Promise.all([
      api.get("/loans"),
      isAdmin ? api.get("/employees") : Promise.resolve({ data: [] }),
    ]);
    setLoans(l.data);
    setEmployees(e.data);
  }, [isAdmin]);

  useEffect(() => { if (has("loans_advances")) refresh(); }, [refresh, has]);

  if (!has("loans_advances")) {
    return (
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center">
        <Wallet className="w-10 h-10 text-[#A1A5AB] mx-auto mb-3" strokeWidth={1.4} />
        <h3 className="font-heading text-xl">Loans & Salary Advances</h3>
        <p className="text-sm text-[#525860] mt-2 max-w-md mx-auto">
          Available on Professional, Enterprise, and Government tiers.
        </p>
      </div>
    );
  }

  const active = loans.filter((l) => l.status === "active");
  const paid = loans.filter((l) => l.status === "paid");
  const cancelled = loans.filter((l) => l.status === "cancelled");
  const totalOutstanding = active.reduce((a, l) => a + l.remaining_balance_sle, 0);
  const totalMonthly = active.reduce((a, l) => a + l.monthly_deduction_sle, 0);

  return (
    <div className="space-y-6" data-testid="loans-page">
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Compensation</div>
            <h1 className="font-heading text-3xl font-bold mt-1">{isAdmin ? "Loans & Advances" : "My Loans"}</h1>
            <p className="text-sm text-[#525860] mt-1 max-w-2xl">
              {isAdmin
                ? "Issue salary advances and track repayments. Monthly deductions flow into payroll automatically."
                : "View your active advances, repayment schedule, and history."}
            </p>
          </div>
          {isAdmin && (
            <button data-testid="loan-new" onClick={() => setCreating(true)} className="inline-flex items-center gap-1.5 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-4 py-2.5 rounded-md">
              <Plus className="w-4 h-4" /> Issue loan
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
          <KPI label="Active loans" value={active.length} color="text-[#26547C]" />
          <KPI label="Outstanding" value={fmtSLE(totalOutstanding)} small />
          <KPI label="Monthly deductions" value={fmtSLE(totalMonthly)} small color="text-[#8B6A14]" />
          <KPI label="Paid off" value={paid.length} color="text-[#17A035]" />
        </div>
      </div>

      {active.length === 0 && paid.length === 0 && cancelled.length === 0 && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center" data-testid="loans-empty">
          <Banknote className="w-10 h-10 text-[#A1A5AB] mx-auto mb-3" strokeWidth={1.4} />
          <p className="text-sm text-[#525860]">No loans on record yet.</p>
        </div>
      )}

      {loans.length > 0 && (
        <LoansTable loans={loans} isAdmin={isAdmin} onSchedule={setScheduleFor} onRefresh={refresh} />
      )}

      {creating && (
        <IssueLoanModal employees={employees} onClose={() => setCreating(false)} onSaved={() => { setCreating(false); refresh(); }} />
      )}
      {scheduleFor && (
        <ScheduleModal loan={scheduleFor} onClose={() => setScheduleFor(null)} />
      )}
    </div>
  );
}

function KPI({ label, value, color = "text-[#1A1C1E]", small }) {
  return (
    <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-3">
      <div className="text-[10px] uppercase tracking-wider text-[#525860]">{label}</div>
      <div className={`font-heading ${small ? "text-lg" : "text-2xl"} font-bold mt-1 font-data ${color}`}>{value}</div>
    </div>
  );
}

function LoansTable({ loans, isAdmin, onSchedule, onRefresh }) {
  const headers = useMemo(
    () => [isAdmin && "Employee", "Principal", "Monthly", "Paid / Remaining", "Progress", "Status", "Purpose", ""].filter(Boolean),
    [isAdmin],
  );
  const cancel = async (lid) => {
    if (!window.confirm("Cancel this loan? Any remaining balance will be written off.")) return;
    try {
      await api.patch(`/loans/${lid}`, { status: "cancelled" });
      toast.success("Loan cancelled");
      onRefresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Cancel failed"); }
  };
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="loans-table">
      <table className="w-full text-sm">
        <thead className="bg-[#F7F6F2]">
          <tr>{headers.map((h) => (
            <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-4 font-medium">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {loans.map((l) => {
            const pill = STATUS_PILL[l.status] || STATUS_PILL.active;
            const Icon = pill.icon;
            return (
              <tr key={l.id} className="border-t border-[#E2DFD6]" data-testid={`loan-row-${l.id}`}>
                {isAdmin && <td className="py-2 px-4 font-medium">{l.employee_name}</td>}
                <td className="py-2 px-4 font-data">{fmtSLE(l.principal_sle)}</td>
                <td className="py-2 px-4 font-data">{fmtSLE(l.monthly_deduction_sle)}</td>
                <td className="py-2 px-4 font-data text-xs">
                  <span className="text-[#17A035]">{fmtSLE(l.paid_sle)}</span>
                  <span className="text-[#525860]"> / </span>
                  <span className="font-semibold">{fmtSLE(l.remaining_balance_sle)}</span>
                </td>
                <td className="py-2 px-4 w-32">
                  <div className="w-full bg-[#EBE8E0] rounded-full h-1.5 overflow-hidden">
                    <div className="bg-[#17A035] h-full transition-all" style={{ width: `${Math.round(l.progress * 100)}%` }} />
                  </div>
                  <div className="text-[10px] text-[#525860] mt-0.5 font-data">{Math.round(l.progress * 100)}%</div>
                </td>
                <td className="py-2 px-4">
                  <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${pill.color}`}>
                    <Icon className="w-3 h-3" /> {pill.label}
                  </span>
                </td>
                <td className="py-2 px-4 text-xs text-[#525860] max-w-[200px] truncate">{l.purpose || "—"}</td>
                <td className="py-2 px-4 text-right whitespace-nowrap">
                  <button onClick={() => onSchedule(l)} title="View schedule" className="p-1 hover:bg-[#F1EEE6] rounded">
                    <Calendar className="w-3.5 h-3.5 text-[#26547C]" />
                  </button>
                  {isAdmin && l.status === "active" && (
                    <button data-testid={`loan-cancel-${l.id}`} onClick={() => cancel(l.id)} title="Cancel" className="p-1 hover:bg-[#E9F2FB] rounded">
                      <XCircle className="w-3.5 h-3.5 text-[#3A7CB8]" />
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function IssueLoanModal({ employees, onClose, onSaved }) {
  const [form, setForm] = useState({
    employee_id: "", principal_sle: "", term_months: 12, purpose: "",
  });
  const [busy, setBusy] = useState(false);
  const monthly = form.principal_sle && form.term_months
    ? (Number(form.principal_sle) / Number(form.term_months)).toFixed(2)
    : "0.00";

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = {
        employee_id: form.employee_id,
        principal_sle: Number(form.principal_sle),
        term_months: Number(form.term_months),
        purpose: form.purpose,
      };
      await api.post("/loans", payload);
      toast.success("Loan issued");
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Issue failed");
    } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => !busy && onClose()}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="bg-white rounded-lg w-full max-w-md p-6 space-y-3" data-testid="loan-issue-modal">
        <div className="flex justify-between">
          <h3 className="font-heading text-xl">Issue salary advance</h3>
          <button type="button" onClick={onClose}><X className="w-4 h-4 text-[#525860]" /></button>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wider text-[#525860] block mb-1">Employee*</label>
          <select required data-testid="loan-employee" value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })}
                  className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
            <option value="">Choose…</option>
            {employees.map((e) => (
              <option key={e.id} value={e.id}>
                {`${e.first_name} ${e.last_name} · ${fmtSLE(e.basic_salary_sle)}`}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] uppercase tracking-wider text-[#525860] block mb-1">Principal (SLE)*</label>
            <input required data-testid="loan-principal" type="number" min={1} step="0.01" value={form.principal_sle} onChange={(e) => setForm({ ...form, principal_sle: e.target.value })}
                   className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-wider text-[#525860] block mb-1">Term (months)*</label>
            <input required data-testid="loan-term" type="number" min={1} max={120} value={form.term_months} onChange={(e) => setForm({ ...form, term_months: e.target.value })}
                   className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
          </div>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wider text-[#525860] block mb-1">Purpose</label>
          <input data-testid="loan-purpose" value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })}
                 placeholder="e.g. School fees" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
        </div>
        <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-3 text-xs">
          <div className="text-[#525860]">Monthly deduction</div>
          <div className="font-data font-semibold text-lg text-[#0A4A1E]">{fmtSLE(monthly)}</div>
          <div className="text-[10px] text-[#686D76] mt-1">Auto-deducted from each payroll run until balance is zero.</div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Cancel</button>
          <button data-testid="loan-submit" type="submit" disabled={busy || !form.employee_id} className="text-sm bg-[#0A4A1E] text-white px-4 py-2 rounded-md disabled:opacity-60">
            {busy ? "Issuing…" : "Issue loan"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ScheduleModal({ loan, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get(`/loans/${loan.id}/schedule`).then((r) => setData(r.data));
  }, [loan.id]);
  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-lg w-full max-w-lg p-6 max-h-[80vh] overflow-y-auto" data-testid="loan-schedule-modal">
        <div className="flex justify-between mb-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Repayment projection</div>
            <h3 className="font-heading text-xl">{loan.employee_name || "Loan"}</h3>
            <p className="text-xs text-[#525860] mt-0.5">Principal {fmtSLE(loan.principal_sle)} · Remaining {fmtSLE(loan.remaining_balance_sle)}</p>
          </div>
          <button onClick={onClose}><X className="w-4 h-4 text-[#525860]" /></button>
        </div>
        {!data && <div className="text-sm text-[#525860]">Loading…</div>}
        {data && (
          <table className="w-full text-sm">
            <thead className="text-[10px] uppercase tracking-wider text-[#525860]">
              <tr><th className="text-left py-2">Month</th><th className="text-right py-2">Amount</th><th className="text-right py-2">Remaining after</th></tr>
            </thead>
            <tbody>
              {data.schedule.map((row) => (
                <tr key={row.n} className="border-t border-[#F1EEE6]">
                  <td className="py-2">{row.n}</td>
                  <td className="py-2 text-right font-data">{fmtSLE(row.amount)}</td>
                  <td className="py-2 text-right font-data">{fmtSLE(row.remaining_after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
