import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { LogOut, CheckCircle2, Circle, FileText, Download } from "lucide-react";

const ROLE_LABEL = { payroll: "Payroll Officer", hr: "HR Admin", admin: "Admin" };
const LEAVING_REASONS = [
  ["resignation", "Resignation"],
  ["retirement", "Retirement"],
  ["redundancy", "Redundancy"],
  ["contract_end", "Contract End"],
  ["dismissal", "Dismissal"],
  ["other", "Other"],
];
const REASON_LABEL = Object.fromEntries(LEAVING_REASONS);
const STATUS_CLS = {
  in_progress: "bg-[#F6EDD8] text-[#8B6A14]",
  completed: "bg-[#E4F7E7] text-[#0A4A1E]",
};
const EMPTY_SETTLEMENT = {
  payroll_period: "",
  taxable_final_pay_sle: "0",
  termination_payment_sle: "0",
  termination_payment_basis: "",
  paye_withheld_sle: "0",
  nassit_employee_sle: "0",
  nassit_employer_sle: "0",
  other_deductions_sle: "0",
  payment_method: "",
  notes: "",
  revision_reason: "",
};

/** Employee-profile offboarding panel: start exit, role-gated checklist sign-offs. */
export default function OffboardingPanel({ employee, onChanged }) {
  const { user } = useAuth();
  const role = user?.role;
  const isAdmin = ["admin", "superadmin"].includes(role);
  const isHr = isAdmin || role === "hr";
  const [ob, setOb] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [settlementBusy, setSettlementBusy] = useState(false);
  const [settlementForm, setSettlementForm] = useState(EMPTY_SETTLEMENT);
  const [paymentForm, setPaymentForm] = useState({ payment_date: "", payment_reference: "" });
  const isPayroll = isAdmin || role === "payroll";

  const load = useCallback(() => {
    api.get(`/offboarding/employee/${employee.id}`)
      .then((r) => {
        const next = r.data;
        setOb(next);
        const settlement = next.final_settlement;
        setSettlementForm(settlement ? {
          payroll_period: settlement.payroll_period || "",
          taxable_final_pay_sle: String(settlement.taxable_final_pay_sle ?? 0),
          termination_payment_sle: String(settlement.termination_payment_sle ?? 0),
          termination_payment_basis: settlement.termination_payment_basis || "",
          paye_withheld_sle: String(settlement.paye_withheld_sle ?? 0),
          nassit_employee_sle: String(settlement.nassit_employee_sle ?? 0),
          nassit_employer_sle: String(settlement.nassit_employer_sle ?? 0),
          other_deductions_sle: String(settlement.other_deductions_sle ?? 0),
          payment_method: settlement.payment_method || "",
          notes: settlement.notes || "",
          revision_reason: "",
        } : EMPTY_SETTLEMENT);
        setPaymentForm({ payment_date: "", payment_reference: "" });
      })
      .catch(() => setOb(null))
      .finally(() => setLoaded(true));
  }, [employee.id]);
  useEffect(load, [load]);

  const start = async () => {
    if (!window.confirm(`Start offboarding for ${employee.first_name} ${employee.last_name}? This marks them as exiting and opens the exit checklist.`)) return;
    setBusy(true);
    try {
      await api.post(`/offboarding/${employee.id}/start`);
      toast.success("Offboarding started");
      load(); onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not start offboarding");
    } finally { setBusy(false); }
  };

  const complete = async (item) => {
    setBusy(true);
    try {
      const r = await api.put(`/offboarding/${ob.id}/items/${item.key}/complete`);
      if (r.data.all_complete) {
        toast.success("Offboarding complete — employee account deactivated");
      } else {
        toast.success(`${item.label} marked complete`);
      }
      load(); onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not complete item");
    } finally { setBusy(false); }
  };

  const saveSettlement = async (event) => {
    event.preventDefault();
    setSettlementBusy(true);
    try {
      await api.put(`/offboarding/${ob.id}/settlement`, settlementForm);
      toast.success("Final settlement draft saved");
      load();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not save final settlement");
    } finally {
      setSettlementBusy(false);
    }
  };

  const approveSettlement = async () => {
    setSettlementBusy(true);
    try {
      await api.post(`/offboarding/${ob.id}/settlement/approve`);
      toast.success("Final settlement approved");
      load();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not approve final settlement");
    } finally {
      setSettlementBusy(false);
    }
  };

  const markSettlementPaid = async (event) => {
    event.preventDefault();
    setSettlementBusy(true);
    try {
      await api.post(`/offboarding/${ob.id}/settlement/mark-paid`, paymentForm);
      toast.success("Final settlement payment recorded");
      load();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not record settlement payment");
    } finally {
      setSettlementBusy(false);
    }
  };

  const downloadSettlement = async () => {
    setSettlementBusy(true);
    try {
      const response = await api.get(`/offboarding/${ob.id}/settlement.csv`, { responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `Final-Settlement-${ob.final_settlement.payroll_period}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not download final settlement");
    } finally {
      setSettlementBusy(false);
    }
  };

  const cancel = async () => {
    if (!window.confirm("Cancel this offboarding and restore the employee to active?")) return;
    setBusy(true);
    try {
      await api.delete(`/offboarding/${ob.id}`);
      toast.success("Offboarding cancelled");
      load(); onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not cancel");
    } finally { setBusy(false); }
  };

  if (!loaded) return null;

  if (!ob) {
    if (!isHr) return null;
    return (
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 flex items-center justify-between flex-wrap gap-3"
        data-testid="offboarding-panel">
        <div>
          <h3 className="font-heading text-lg font-semibold inline-flex items-center gap-2">
            <LogOut className="w-5 h-5 text-[#B03A2E]" strokeWidth={1.5} /> Offboarding
          </h3>
          <p className="text-sm text-[#525860] mt-1">
            Mark this employee as exiting to open the exit checklist: final settlement, document handover, equipment return and access revocation.
          </p>
        </div>
        <button onClick={start} disabled={busy} data-testid="offboarding-start-btn"
          className="inline-flex items-center gap-2 border border-[#B03A2E] text-[#B03A2E] hover:bg-[#FBE9E9] text-sm font-medium px-4 py-2.5 rounded-md disabled:opacity-50">
          <LogOut className="w-4 h-4" /> Start offboarding
        </button>
      </div>
    );
  }

  const done = ob.items.filter((i) => i.completed).length;
  const mayComplete = (item) => !item.completed && ob.status === "in_progress" &&
    (isAdmin || (item.responsible_role !== "admin" && role === item.responsible_role));

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 space-y-4" data-testid="offboarding-panel">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-heading text-lg font-semibold inline-flex items-center gap-2">
          <LogOut className="w-5 h-5 text-[#B03A2E]" strokeWidth={1.5} /> Offboarding
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#525860] font-data">{done} / {ob.items.length} complete</span>
          <span className={`text-[10px] uppercase tracking-wide px-2 py-1 rounded-full ${STATUS_CLS[ob.status] || "bg-[#F1EEE6] text-[#525860]"}`}
            data-testid="offboarding-status-badge">
            {ob.status.replace("_", " ")}
          </span>
        </div>
      </div>

      <div className="space-y-1">
        {ob.items.map((item) => (
          <div key={item.key} className="flex items-center justify-between gap-3 border-b border-[#F0EEE8] last:border-0 py-2.5"
            data-testid={`offboarding-item-${item.key}`}>
            <div className="flex items-center gap-3 min-w-0">
              {item.completed
                ? <CheckCircle2 className="w-5 h-5 text-[#17A035] shrink-0" strokeWidth={1.7} />
                : <Circle className="w-5 h-5 text-[#C9CCD1] shrink-0" strokeWidth={1.7} />}
              <div className="min-w-0">
                <div className={`text-sm font-medium ${item.completed ? "text-[#686D76] line-through" : "text-[#1A1C1E]"}`}>{item.label}</div>
                <div className="text-[11px] text-[#8A8F96]">
                  {item.completed
                    ? `Signed off by ${item.completed_by} · ${(item.completed_at || "").slice(0, 10)}`
                    : `Responsible: ${ROLE_LABEL[item.responsible_role] || item.responsible_role}`}
                </div>
              </div>
            </div>
            {mayComplete(item) && (
              <button onClick={() => complete(item)} disabled={busy} data-testid={`offboarding-complete-${item.key}`}
                className="text-xs bg-[#0A4A1E] hover:bg-[#063514] text-white px-3 py-1.5 rounded-md disabled:opacity-50 shrink-0">
                Mark complete
              </button>
            )}
          </div>
        ))}
      </div>

      {ob.status === "completed" && (
        <div className="text-sm text-[#0A4A1E] bg-[#E4F7E7] rounded-md px-3 py-2" data-testid="offboarding-completed-note">
          All checklist items signed off on {(ob.completed_at || "").slice(0, 10)} — the employee&rsquo;s account has been deactivated.
        </div>
      )}

      {isPayroll && ob.status === "in_progress" && (
        <FinalSettlementSection
          ob={ob}
          form={settlementForm}
          setForm={setSettlementForm}
          paymentForm={paymentForm}
          setPaymentForm={setPaymentForm}
          busy={settlementBusy}
          save={saveSettlement}
          approve={approveSettlement}
          markPaid={markSettlementPaid}
          download={downloadSettlement}
          userEmail={user?.email}
        />
      )}

      {ob.status === "completed" && ob.final_settlement && isPayroll && (
        <FinalSettlementSummary settlement={ob.final_settlement} download={downloadSettlement} busy={settlementBusy} />
      )}

      <ExitInterviewSection ob={ob} canEdit={isHr} onSaved={load} />

      {ob.status === "in_progress" && isHr && (
        <button onClick={cancel} disabled={busy} data-testid="offboarding-cancel-btn"
          className="text-xs border border-[#E2DFD6] text-[#525860] hover:bg-[#F7F6F2] px-3 py-1.5 rounded-md disabled:opacity-50">
          Cancel offboarding
        </button>
      )}
    </div>
  );
}

function FinalSettlementSection({
  ob, form, setForm, paymentForm, setPaymentForm, busy, save, approve, markPaid, download, userEmail,
}) {
  const settlement = ob.final_settlement;
  const amount = (key) => Number(form[key] || 0);
  const gross = amount("taxable_final_pay_sle") + amount("termination_payment_sle");
  const net = gross - amount("paye_withheld_sle") - amount("nassit_employee_sle") - amount("other_deductions_sle");
  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const canApprove = settlement?.status === "draft" && settlement.prepared_by_email !== userEmail;

  return (
    <section className="border-t border-[#E2DFD6] pt-4 space-y-4" data-testid="final-settlement-workpaper">
      <div>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h4 className="font-heading text-base font-semibold">Final settlement workpaper</h4>
          {settlement && <span className="text-[10px] uppercase tracking-wide px-2 py-1 rounded-full bg-[#F1EEE6] text-[#525860]">
            Revision {settlement.revision} · {settlement.status}
          </span>}
        </div>
        <p className="text-xs text-[#686D76] mt-1 max-w-4xl">
          Keep ordinary final employment pay separate from a qualifying redundancy, termination, loss-of-office, or similar payment. Section 23(3)(h) of the{" "}
          <a href="https://webtestcms.nra.gov.sl/uploads/The_Finance_Act_2026_121df05d9b.pdf" target="_blank" rel="noreferrer" className="text-[#26547C] underline">Finance Act 2026</a>{" "}
          excludes qualifying payments from income. This workpaper does not calculate PAYE or NASSIT; enter payroll-confirmed values and confirm NASSIT treatment with the authority.
        </p>
      </div>

      {settlement && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs" data-testid="final-settlement-saved-summary">
          <Metric label="Gross settlement" value={fmtSLE(settlement.gross_settlement_sle)} />
          <Metric label="PAYE recorded" value={fmtSLE(settlement.paye_withheld_sle)} />
          <Metric label="Employee NASSIT" value={fmtSLE(settlement.nassit_employee_sle)} />
          <Metric label="Net settlement" value={fmtSLE(settlement.net_settlement_sle)} />
          <div className="col-span-full text-[#686D76]">
            Prepared by {settlement.prepared_by} · {settlement.approved_by ? `approved by ${settlement.approved_by}` : "awaiting a different payroll approver"}
            {settlement.paid_at ? ` · paid ${settlement.payment_date} · ref ${settlement.payment_reference}` : ""}
          </div>
          {settlement.status === "approved" || settlement.status === "paid" ? (
            <button type="button" onClick={download} disabled={busy}
              className="inline-flex items-center gap-1 text-xs text-[#26547C] underline disabled:opacity-50">
              <Download className="w-3.5 h-3.5" /> Download approved CSV
            </button>
          ) : null}
        </div>
      )}

      {settlement?.status !== "paid" && (
        <form onSubmit={save} className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3" data-testid="final-settlement-form">
          <label className="text-[10px] uppercase tracking-wider text-[#686D76]">
            Payroll period
            <input required type="month" value={form.payroll_period} onChange={(event) => set("payroll_period", event.target.value)}
              className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-3 py-2 text-sm normal-case tracking-normal" />
          </label>
          <MoneyField label="Taxable final pay (SLE)" value={form.taxable_final_pay_sle} onChange={(value) => set("taxable_final_pay_sle", value)} required />
          <MoneyField label="Termination / loss-of-office payment (SLE)" value={form.termination_payment_sle} onChange={(value) => set("termination_payment_sle", value)} />
          <label className="text-[10px] uppercase tracking-wider text-[#686D76]">
            Termination-payment basis
            <select required={amount("termination_payment_sle") > 0} value={form.termination_payment_basis}
              onChange={(event) => set("termination_payment_basis", event.target.value)}
              className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-3 py-2 text-sm normal-case tracking-normal">
              <option value="">Select basis</option>
              <option value="redundancy">Redundancy</option>
              <option value="termination">Termination</option>
              <option value="loss_of_office">Loss of office</option>
              <option value="similar_type">Similar payment</option>
            </select>
          </label>
          <MoneyField label="PAYE withheld (SLE)" value={form.paye_withheld_sle} onChange={(value) => set("paye_withheld_sle", value)} />
          <MoneyField label="Employee NASSIT (SLE)" value={form.nassit_employee_sle} onChange={(value) => set("nassit_employee_sle", value)} />
          <MoneyField label="Employer NASSIT (SLE)" value={form.nassit_employer_sle} onChange={(value) => set("nassit_employer_sle", value)} />
          <MoneyField label="Other deductions (SLE)" value={form.other_deductions_sle} onChange={(value) => set("other_deductions_sle", value)} />
          <label className="text-[10px] uppercase tracking-wider text-[#686D76]">
            Payment method
            <select required value={form.payment_method} onChange={(event) => set("payment_method", event.target.value)}
              className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-3 py-2 text-sm normal-case tracking-normal">
              <option value="">Select method</option>
              <option value="Bank transfer">Bank transfer</option>
              <option value="Orange Money">Orange Money</option>
              <option value="Afrimoney">Afrimoney</option>
              <option value="Cheque">Cheque</option>
              <option value="Cash">Cash</option>
              <option value="Not applicable">Not applicable</option>
            </select>
          </label>
          {settlement?.status === "approved" && settlement.net_settlement_sle > 0 && (
            <>
              <label className="text-[10px] uppercase tracking-wider text-[#686D76]">
                Actual payment date
                <input type="date" value={paymentForm.payment_date}
                  onChange={(event) => setPaymentForm({ ...paymentForm, payment_date: event.target.value })}
                  className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-3 py-2 text-sm normal-case tracking-normal" />
              </label>
              <label className="text-[10px] uppercase tracking-wider text-[#686D76]">
                Receipt / payment reference
                <input maxLength={120} value={paymentForm.payment_reference}
                  onChange={(event) => setPaymentForm({ ...paymentForm, payment_reference: event.target.value })}
                  className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-3 py-2 text-sm normal-case tracking-normal" />
              </label>
            </>
          )}
          <label className="text-[10px] uppercase tracking-wider text-[#686D76] md:col-span-2 xl:col-span-3">
            Payroll notes
            <textarea rows={2} maxLength={3000} value={form.notes} onChange={(event) => set("notes", event.target.value)}
              className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-3 py-2 text-sm normal-case tracking-normal" />
          </label>
          {settlement?.status === "approved" && (
            <label className="text-[10px] uppercase tracking-wider text-[#686D76] md:col-span-2 xl:col-span-3">
              Reason for revising approved settlement
              <textarea rows={2} maxLength={1000} required value={form.revision_reason}
                onChange={(event) => set("revision_reason", event.target.value)}
                className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-3 py-2 text-sm normal-case tracking-normal" />
            </label>
          )}
          <div className="md:col-span-2 xl:col-span-3 flex flex-wrap items-center gap-2">
            <Metric label="Net to employee" value={fmtSLE(net)} />
            <button disabled={busy || (settlement?.status === "approved" && !form.revision_reason.trim())}
              className="inline-flex items-center gap-2 bg-[#0A4A1E] text-white text-xs px-3 py-2 rounded-md disabled:opacity-50">
              {settlement?.status === "approved" ? "Save revised draft" : "Save draft"}
            </button>
            {canApprove && (
              <button type="button" onClick={approve} disabled={busy}
                className="inline-flex items-center gap-2 border border-[#17A035] text-[#0A4A1E] text-xs px-3 py-2 rounded-md disabled:opacity-50">
                Approve as checker
              </button>
            )}
            {settlement?.status === "approved" && settlement.net_settlement_sle > 0 && (
              <button type="button" onClick={markPaid} disabled={busy || !paymentForm.payment_date || !paymentForm.payment_reference.trim()}
                className="inline-flex items-center gap-2 border border-[#26547C] text-[#26547C] text-xs px-3 py-2 rounded-md disabled:opacity-50">
                Record payment made
              </button>
            )}
            {settlement?.status === "approved" && settlement.net_settlement_sle === 0 && (
              <span className="text-xs text-[#686D76]">No payment is due; the approved zero-net settlement can be signed off.</span>
            )}
          </div>
        </form>
      )}
    </section>
  );
}

function FinalSettlementSummary({ settlement, download, busy }) {
  const paid = settlement.status === "paid";
  return (
    <section className="border-t border-[#E2DFD6] pt-4 space-y-2" data-testid="final-settlement-completed-summary">
      <h4 className="font-heading text-base font-semibold">Final settlement</h4>
      <p className="text-xs text-[#525860]">
        {paid
          ? `Paid ${settlement.payment_date} · ${fmtSLE(settlement.net_settlement_sle)} · ref ${settlement.payment_reference}`
          : `Approved zero-net settlement · ${fmtSLE(settlement.net_settlement_sle)}`}
      </p>
      <button type="button" onClick={download} disabled={busy}
        className="inline-flex items-center gap-1 text-xs text-[#26547C] underline disabled:opacity-50">
        <Download className="w-3.5 h-3.5" /> Download final settlement CSV
      </button>
    </section>
  );
}

function MoneyField({ label, value, onChange, required = false }) {
  return (
    <label className="text-[10px] uppercase tracking-wider text-[#686D76]">
      {label}
      <input required={required} type="number" min="0" step="0.01" value={value} onChange={(event) => onChange(event.target.value)}
        className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-3 py-2 text-sm normal-case tracking-normal" />
    </label>
  );
}

function Metric({ label, value }) {
  return <div className="rounded-md border border-[#E2DFD6] bg-[#F8F7F2] px-3 py-2">
    <div className="text-[10px] uppercase tracking-wide text-[#686D76]">{label}</div>
    <div className="mt-1 text-sm font-data font-medium text-[#1A1C1E]">{value}</div>
  </div>;
}

function ExitInterviewSection({ ob, canEdit, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [f, setF] = useState({
    leaving_reason: ob.exit_interview?.leaving_reason || "resignation",
    notes: ob.exit_interview?.notes || "",
  });
  const [busy, setBusy] = useState(false);
  const rec = ob.exit_interview;

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.put(`/offboarding/${ob.id}/exit-interview`, f);
      toast.success("Exit interview recorded");
      setEditing(false);
      onSaved?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save exit interview");
    } finally { setBusy(false); }
  };

  if (!rec && !canEdit) return null;
  return (
    <div className="border-t border-[#F0EEE8] pt-4" data-testid="exit-interview-section">
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860] inline-flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5" /> Exit interview
        </div>
        {canEdit && !editing && (
          <button onClick={() => setEditing(true)} data-testid="exit-interview-edit-btn"
            className="text-xs text-[#26547C] hover:underline">
            {rec ? "Edit" : "Record exit interview"}
          </button>
        )}
      </div>

      {!editing && rec && (
        <div className="mt-2" data-testid="exit-interview-display">
          <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full bg-[#F1EEE6] text-[#525860]"
            data-testid="exit-interview-reason-badge">
            {REASON_LABEL[rec.leaving_reason] || rec.leaving_reason}
          </span>
          {rec.notes && <p className="text-sm text-[#525860] mt-2 whitespace-pre-wrap">{rec.notes}</p>}
          <div className="text-[11px] text-[#8A8F96] mt-1.5">
            Recorded by {rec.recorded_by} · {(rec.recorded_at || "").slice(0, 10)}
          </div>
        </div>
      )}
      {!editing && !rec && (
        <p className="text-xs text-[#686D76] mt-2">No exit interview recorded yet.</p>
      )}

      {editing && (
        <form onSubmit={save} className="mt-3 space-y-3">
          <label className="block text-xs text-[#525860]">Leaving reason
            <select value={f.leaving_reason} onChange={(e) => setF({ ...f, leaving_reason: e.target.value })}
              className="mt-1 w-full sm:w-64 border border-[#E2DFD6] rounded-md px-3 py-2 text-sm bg-white"
              data-testid="exit-interview-reason-select">
              {LEAVING_REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="block text-xs text-[#525860]">Interview notes
            <textarea rows={4} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })}
              placeholder="Key points from the exit interview…"
              className="mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
              data-testid="exit-interview-notes-input" />
          </label>
          <div className="flex gap-2">
            <button disabled={busy} data-testid="exit-interview-save-btn"
              className="bg-[#0A4A1E] text-white text-xs px-4 py-2 rounded-md disabled:opacity-50">
              {busy ? "Saving…" : "Save exit interview"}
            </button>
            <button type="button" onClick={() => setEditing(false)}
              className="border border-[#E2DFD6] text-xs px-4 py-2 rounded-md">Cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}
