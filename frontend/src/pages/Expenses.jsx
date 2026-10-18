import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Receipt, Plus, Check, X, Paperclip } from "lucide-react";

const CATEGORIES = ["transport", "meals", "accommodation", "supplies", "other"];
const STATUS_CLS = {
  pending: "bg-[#F6EDD8] text-[#8B6A14]",
  approved: "bg-[#E4F7E7] text-[#0A4A1E]",
  rejected: "bg-[#FBE9E9] text-[#B03A2E]",
  reimbursed: "bg-[#E5EEF6] text-[#26547C]",
};

export default function Expenses() {
  const { user } = useAuth();
  const role = user?.role;
  const readOnly = role === "auditor";
  const canDecide = ["manager", "hr", "admin", "superadmin"].includes(role);
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);

  const load = useCallback(() => {
    api.get("/expenses").then((r) => setRows(r.data)).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const decide = async (cid, status) => {
    try {
      await api.put(`/expenses/${cid}/decision`, { status });
      toast.success(`Claim ${status}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Decision failed");
    }
  };

  const mine = rows.filter((r) => r.employee_id === user?.employee_id);
  const others = rows.filter((r) => r.employee_id !== user?.employee_id);
  const viewReceipt = async (cid) => {
    const r = await api.get(`/expenses/${cid}/receipt`, { responseType: "blob" });
    window.open(URL.createObjectURL(r.data), "_blank");
  };

  const Row = ({ r, actions }) => (
    <div className="flex items-center justify-between gap-3 border-b border-[#F0EEE8] py-3 flex-wrap" data-testid={`expense-row-${r.id}`}>
      <div className="min-w-0">
        <div className="text-sm font-medium text-[#1A1C1E]">
          {r.employee_name} · <span className="capitalize text-[#525860]">{r.category}</span>
        </div>
        <div className="text-xs text-[#686D76] truncate max-w-md">{r.description}</div>
        <div className="text-[11px] text-[#8A8F96]">{(r.created_at || "").slice(0, 10)}
          {r.decision_note ? ` · ${r.decision_note}` : ""}</div>
      </div>
      <div className="flex items-center gap-3">
        {r.receipt && (
          <button onClick={() => viewReceipt(r.id)} className="text-[#26547C]" title={r.receipt.filename}
            data-testid={`expense-receipt-${r.id}`}>
            <Paperclip className="w-4 h-4" />
          </button>
        )}
        <span className="font-data font-bold text-sm">{fmtSLE(r.amount_sle)}</span>
        <span className={`text-[10px] uppercase tracking-wide px-2 py-1 rounded-full ${STATUS_CLS[r.status]}`}>{r.status}</span>
        {actions && r.status === "pending" && (
          <div className="flex gap-1.5">
            <button onClick={() => decide(r.id, "approved")} className="p-1.5 rounded bg-[#E4F7E7] text-[#0A4A1E]"
              data-testid={`expense-approve-${r.id}`}><Check className="w-4 h-4" /></button>
            <button onClick={() => decide(r.id, "rejected")} className="p-1.5 rounded bg-[#FBE9E9] text-[#B03A2E]"
              data-testid={`expense-reject-${r.id}`}><X className="w-4 h-4" /></button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-6" data-testid="expenses-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Reimbursements</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Expense claims</h1>
          <p className="text-[#525860] text-sm mt-1">Approved claims are added as a reimbursement line on the next payroll run.</p>
        </div>
        {!readOnly && user?.employee_id && (
          <button onClick={() => setOpen(true)} data-testid="expense-new-button"
            className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm font-medium px-4 py-2.5 rounded-md">
            <Plus className="w-4 h-4" /> New claim
          </button>
        )}
      </div>

      {open && <ClaimForm onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load(); }} />}

      {(canDecide || readOnly) && others.length > 0 && (
        <section className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="expenses-team-section">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860] mb-1">
            {readOnly ? "All claims (read-only)" : "Team claims"}
          </div>
          {others.map((r) => <Row key={r.id} r={r} actions={canDecide && !readOnly} />)}
        </section>
      )}

      <section className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="expenses-mine-section">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860] mb-1">My claims</div>
        {mine.length === 0 ? (
          <div className="text-sm text-[#686D76] py-4 flex items-center gap-2">
            <Receipt className="w-4 h-4" /> No claims yet.
          </div>
        ) : mine.map((r) => <Row key={r.id} r={r} actions={false} />)}
      </section>
    </div>
  );
}

function ClaimForm({ onClose, onSaved }) {
  const [f, setF] = useState({ description: "", amount_sle: "", category: "transport" });
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("description", f.description);
      fd.append("amount_sle", f.amount_sle);
      fd.append("category", f.category);
      if (file) fd.append("receipt", file);
      await api.post("/expenses", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Claim submitted for approval");
      onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Submit failed");
    } finally { setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="bg-white border border-[#E2DFD6] rounded-lg p-6 grid grid-cols-1 sm:grid-cols-2 gap-4" data-testid="expense-form">
      <label className="text-xs text-[#525860] sm:col-span-2">Description
        <input required value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })}
          className="mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" data-testid="expense-form-description" />
      </label>
      <label className="text-xs text-[#525860]">Amount (SLE)
        <input required type="number" min="0.01" step="0.01" value={f.amount_sle}
          onChange={(e) => setF({ ...f, amount_sle: e.target.value })}
          className="mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" data-testid="expense-form-amount" />
      </label>
      <label className="text-xs text-[#525860]">Category
        <select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}
          className="mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2 text-sm capitalize" data-testid="expense-form-category">
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
      <label className="text-xs text-[#525860] sm:col-span-2">Receipt (optional — JPG, PNG or PDF)
        <input type="file" accept=".jpg,.jpeg,.png,.pdf" onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="mt-1 w-full text-sm" data-testid="expense-form-receipt" />
      </label>
      <div className="sm:col-span-2 flex gap-2">
        <button disabled={busy} className="bg-[#0A4A1E] text-white text-sm px-5 py-2.5 rounded-md disabled:opacity-50" data-testid="expense-form-submit">
          {busy ? "Submitting…" : "Submit claim"}
        </button>
        <button type="button" onClick={onClose} className="border border-[#E2DFD6] text-sm px-5 py-2.5 rounded-md">Cancel</button>
      </div>
    </form>
  );
}
