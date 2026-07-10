import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE, downloadBlob } from "../lib/api";
import { useFeatures } from "../lib/features";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import SmsPayslipButton from "../components/SmsPayslipButton";
import IfmisActions from "../components/IfmisActions";
import { BudgetCheckModal, BudgetBalancesPanel } from "../components/BudgetCheck";
import { VarianceButton } from "../components/Variance";
import { MoFSignaturesButton } from "../components/MoFSignatures";
import { Calculator, Play, Check, FileText, Download, Send, ShieldCheck, AlertTriangle } from "lucide-react";

const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

const MOF_PILL = {
  draft: { label: "Draft", color: "bg-[#EBE8E0] text-[#525860]" },
  submitted: { label: "Awaiting MoF", color: "bg-[#FBF1DE] text-[#8B6A14]" },
  partially_signed: { label: "Partially signed", color: "bg-[#FBE9DF] text-[#B84F2F]" },
  approved: { label: "MoF approved", color: "bg-[#E6F4EC] text-[#2D7A5D]" },
  released: { label: "Released", color: "bg-[#E5EEF6] text-[#26547C]" },
  rejected: { label: "Rejected", color: "bg-[#FBEAEA] text-[#B83A3A]" },
};

export default function Payroll() {
  const { has } = useFeatures();
  const { user } = useAuth();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [step, setStep] = useState(1);
  const [preview, setPreview] = useState(null);
  const [runs, setRuns] = useState([]);
  const [running, setRunning] = useState(false);

  const loadRuns = useCallback(() => api.get("/payroll/runs").then((r) => setRuns(r.data)), []);
  useEffect(() => { loadRuns(); }, [loadRuns]);

  const downloadPdf = async (rid, eid, name) => {
    await downloadBlob(`/payroll/runs/${rid}/payslip/${eid}.pdf`, `payslip-${name.replace(/\s/g, "_")}.pdf`);
  };

  const downloadBank = async (rid, period) => {
    await downloadBlob(`/payroll/runs/${rid}/bank-file`, `bank-file-${period}.csv`);
  };

  const submitMoF = async (rid) => {
    if (!window.confirm("Submit this payroll run to MoF for approval?")) return;
    try {
      await api.post(`/civil-service/runs/${rid}/submit-for-approval`, { note: "" });
      toast.success("Submitted for MoF approval");
      loadRuns();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Submit failed");
    }
  };

  const approveMoF = async (rid) => {
    try {
      await api.post(`/civil-service/runs/${rid}/mof-approve`, { note: "Approved" });
      toast.success("Approved");
      loadRuns();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Approve failed");
    }
  };

  const rejectMoF = async (rid) => {
    const note = window.prompt("Reason for rejection?");
    if (!note) return;
    try {
      await api.post(`/civil-service/runs/${rid}/mof-reject`, { note });
      toast.success("Rejected");
      loadRuns();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Reject failed");
    }
  };

  const doPreview = async () => {
    const { data } = await api.post("/payroll/preview");
    setPreview(data); setStep(2);
  };

  const isGov = has("gov_payroll");
  const period = `${year}-${String(month).padStart(2, "0")}`;
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [showBalances, setShowBalances] = useState(false);

  const doRun = async () => {
    if (isGov) {
      setShowBudgetModal(true);
      return;
    }
    await executeRun();
  };

  const executeRun = async () => {
    setRunning(true);
    try {
      await api.post("/payroll/run", { period_year: Number(year), period_month: Number(month) });
      setStep(3); loadRuns();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === "object" ? detail?.message : (detail || "Payroll run failed");
      toast.error(msg);
    } finally { setRunning(false); }
  };

  const onBudgetConfirmed = async () => {
    setShowBudgetModal(false);
    await executeRun();
  };

  return (
    <div className="space-y-6" data-testid="payroll-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Payroll Engine</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Run payroll</h1>
        <p className="text-[#525860] text-sm mt-1 max-w-2xl">Auto-calculates gross-to-net for active employees including NRA PAYE bands and NASSIT contributions.</p>
      </div>

      {/* Wizard */}
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <div className="flex items-center gap-2 mb-6">
          {[1, 2, 3].map((n) => (
            <div key={n} className={`flex items-center gap-2 ${step >= n ? "text-[#133326]" : "text-[#A1A5AB]"}`}>
              <div className={`w-7 h-7 rounded-full grid place-items-center text-xs font-semibold ${step >= n ? "bg-[#133326] text-white" : "bg-[#EBE8E0]"}`}>{n}</div>
              <span className="text-xs uppercase tracking-wider">{["Period", "Review", "Confirm"][n - 1]}</span>
              {n < 3 && <div className="w-8 h-px bg-[#E2DFD6] mx-2" />}
            </div>
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-5 max-w-md">
            <div>
              <label className="block text-xs uppercase tracking-wider text-[#525860] mb-1.5">Pay period month</label>
              <select data-testid="payroll-month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                {months.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs uppercase tracking-wider text-[#525860] mb-1.5">Year</label>
              <input data-testid="payroll-year" type="number" value={year} onChange={(e) => setYear(e.target.value)} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
            </div>
            <button data-testid="payroll-preview-button" onClick={doPreview} className="inline-flex items-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white px-4 py-2.5 rounded-md text-sm font-medium">
              <Calculator className="w-4 h-4" strokeWidth={1.5} /> Preview calculations
            </button>
          </div>
        )}

        {step === 2 && preview && (
          <div className="space-y-5">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {[
                ["Employees", preview.totals.employee_count],
                ["Gross", fmtSLE(preview.totals.gross)],
                ["NASSIT (10%+5%)", fmtSLE(preview.totals.nassit_employer + preview.totals.nassit_employee)],
                ["PAYE", fmtSLE(preview.totals.paye)],
                ["Net pay", fmtSLE(preview.totals.net)],
              ].map(([k, v]) => (
                <div key={k} className="border border-[#E2DFD6] rounded-md p-3">
                  <div className="text-[10px] uppercase tracking-wider text-[#525860]">{k}</div>
                  <div className="font-data text-base font-semibold mt-1">{v}</div>
                </div>
              ))}
            </div>
            <div className="overflow-x-auto border border-[#E2DFD6] rounded-md">
              <table className="w-full text-sm" data-testid="payroll-preview-table">
                <thead className="bg-[#F7F6F2]">
                  <tr>{["Employee", "Gross", "NASSIT 5%", "PAYE", "Net"].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {preview.slips.map((s) => (
                    <tr key={s.employee_id} className="border-t border-[#E2DFD6]">
                      <td className="py-2.5 px-4 text-[#1A1C1E]">{s.employee_name}</td>
                      <td className="py-2.5 px-4 font-data">{fmtSLE(s.gross)}</td>
                      <td className="py-2.5 px-4 font-data text-[#B83A3A]">− {fmtSLE(s.nassit_employee)}</td>
                      <td className="py-2.5 px-4 font-data text-[#B83A3A]">− {fmtSLE(s.paye)}</td>
                      <td className="py-2.5 px-4 font-data font-semibold">{fmtSLE(s.net)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setStep(1)} className="px-4 py-2.5 text-sm border border-[#E2DFD6] rounded-md">Back</button>
              <button data-testid="payroll-run-button" onClick={doRun} disabled={running} className="inline-flex items-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2.5 rounded-md text-sm font-medium disabled:opacity-60">
                <Play className="w-4 h-4" strokeWidth={1.5} /> {running ? "Running…" : `Run for ${months[month - 1]} ${year}`}
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="text-center py-10" data-testid="payroll-success">
            <div className="w-14 h-14 rounded-full bg-[#E6F4EC] grid place-items-center mx-auto mb-4">
              <Check className="w-6 h-6 text-[#2D7A5D]" strokeWidth={2} />
            </div>
            <h3 className="font-heading text-2xl font-bold">Payroll completed</h3>
            <p className="text-[#525860] text-sm mt-2">Run for {months[month - 1]} {year} has been recorded.</p>
            <button onClick={() => { setStep(1); setPreview(null); }} className="mt-5 px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Run another</button>
          </div>
        )}
      </div>

      {/* Gov-only: IFMIS budget balances panel (collapsible) */}
      {isGov && (
        <div className="space-y-2">
          <button
            onClick={() => setShowBalances((s) => !s)}
            data-testid="toggle-budget-balances"
            className="inline-flex items-center gap-2 text-sm text-[#26547C] hover:underline"
          >
            <ShieldCheck className="w-4 h-4" strokeWidth={1.5} />
            {showBalances ? "Hide" : "Show"} IFMIS budget balances for {period}
          </button>
          {showBalances && <BudgetBalancesPanel period={period} />}
        </div>
      )}

      {showBudgetModal && (
        <BudgetCheckModal
          period={period}
          isMofApprover={!!user?.mof_approver || user?.role === "superadmin"}
          currentUserEmail={user?.email}
          onConfirm={onBudgetConfirmed}
          onClose={() => setShowBudgetModal(false)}
        />
      )}

      {/* Runs history */}
      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">History</div>
            <h3 className="font-heading text-lg font-semibold">Recent payroll runs</h3>
          </div>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Period", "Employees", "Gross", "PAYE", "NASSIT", "Net", "MoF", ""].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {runs.map((r) => {
              const pill = MOF_PILL[r.mof_status || "draft"];
              return (
              <tr key={r.id} className="border-t border-[#E2DFD6]" data-testid={`payroll-run-row-${r.id}`}>
                <td className="py-3 px-4 font-medium">{r.period}</td>
                <td className="py-3 px-4 font-data">{r.totals.employee_count}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(r.totals.gross)}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(r.totals.paye)}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(r.totals.nassit_employee + r.totals.nassit_employer)}</td>
                <td className="py-3 px-4 font-data font-semibold">{fmtSLE(r.totals.net)}</td>
                <td className="py-3 px-4">
                  {has("mof_approval") && (
                    <span data-testid={`mof-status-${r.id}`} className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${pill.color}`}>{pill.label}</span>
                  )}
                </td>
                <td className="py-3 px-4 text-right">
                  <div className="inline-flex gap-1.5 flex-wrap justify-end">
                    {has("mof_approval") && (r.mof_status || "draft") === "draft" && (
                      <button data-testid={`mof-submit-${r.id}`} onClick={() => submitMoF(r.id)} className="inline-flex items-center gap-1 text-xs bg-[#26547C] hover:bg-[#1D4363] text-white px-2.5 py-1.5 rounded">
                        <Send className="w-3.5 h-3.5" /> Submit to MoF
                      </button>
                    )}
                    {has("mof_approval") && r.mof_status === "submitted" && user?.mof_approver && (
                      <>
                        <button data-testid={`mof-approve-${r.id}`} onClick={() => approveMoF(r.id)} className="inline-flex items-center gap-1 text-xs bg-[#2D7A5D] hover:bg-[#256449] text-white px-2.5 py-1.5 rounded">
                          <ShieldCheck className="w-3.5 h-3.5" /> Approve
                        </button>
                        <button data-testid={`mof-reject-${r.id}`} onClick={() => rejectMoF(r.id)} className="inline-flex items-center gap-1 text-xs bg-white border border-[#B83A3A] text-[#B83A3A] hover:bg-[#FBEAEA] px-2.5 py-1.5 rounded">
                          <AlertTriangle className="w-3.5 h-3.5" /> Reject
                        </button>
                      </>
                    )}
                    <button data-testid={`bank-${r.id}`} onClick={() => downloadBank(r.id, r.period)} className={`inline-flex items-center gap-1 text-xs bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#26547C] px-2.5 py-1.5 rounded ${has("ifmis_integration") ? "hidden" : ""}`}>
                      <Download className="w-3.5 h-3.5" /> Bank file
                    </button>
                    {has("ifmis_integration") && <IfmisActions run={r} />}
                    <a href={`/compliance#${r.id}`} className="inline-flex items-center gap-1 text-xs bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#525860] px-2.5 py-1.5 rounded"><FileText className="w-3.5 h-3.5" /> NRA</a>
                    <VarianceButton runId={r.id} period={r.period} />
                    {has("mof_approval") && (
                      <MoFSignaturesButton runId={r.id} mofStatus={r.mof_status} onUpdated={loadRuns} />
                    )}
                    {has("bulk_sms_payslips") && <SmsPayslipButton run={r} />}
                  </div>
                </td>
              </tr>
              );
            })}
            {!runs.length && <tr><td colSpan={8} className="py-10 text-center text-sm text-[#686D76]">No payroll runs yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
