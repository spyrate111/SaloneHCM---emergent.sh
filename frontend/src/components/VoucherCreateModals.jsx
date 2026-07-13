import { useEffect, useState } from "react";
import api, { fmtSLE } from "../lib/api";
import { toast } from "sonner";
import { X, Plus, Trash2, Zap } from "lucide-react";

const errMsg = (e) => {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : d?.message || "Action failed";
};

export function CreateVoucherModal({ branches, user, canManage, onClose, onSaved }) {
  const myBranches = canManage ? branches : branches.filter((b) => b.supervisor_user_id === user?.id);
  const [branchId, setBranchId] = useState(myBranches[0]?.id || "");
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7));
  const [pool, setPool] = useState([]);
  const [lines, setLines] = useState([]);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!branchId) return;
    api.get(`/branches/${branchId}/employees`).then((r) => setPool(r.data)).catch(() => setPool([]));
    setLines([]);
  }, [branchId]);

  const addLine = () => {
    const emp = pool.find((e) => e.id === pick);
    if (!emp || lines.some((l) => l.employee_id === emp.id)) return;
    const gross = (emp.basic_salary_sle || 0) + (emp.allowances_sle || 0);
    setLines((ls) => [...ls, {
      employee_id: emp.id, employee_name: `${emp.first_name} ${emp.last_name}`,
      gross, paye: 0, nassit_employee: 0, loan_deduction: 0,
    }]);
    setPick("");
  };

  const setLine = (idx, key, val) => setLines((ls) => ls.map((l, i) => (i === idx ? { ...l, [key]: val } : l)));
  const netOf = (l) => Math.round((+l.gross - +l.paye - +l.nassit_employee - +l.loan_deduction) * 100) / 100;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/vouchers", {
        branch_id: branchId, period,
        line_items: lines.map((l) => ({
          employee_id: l.employee_id, gross: +l.gross, paye: +l.paye,
          nassit_employee: +l.nassit_employee, loan_deduction: +l.loan_deduction,
        })),
      });
      toast.success("Draft voucher created");
      onSaved();
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 grid place-items-center p-4 overflow-y-auto" data-testid="voucher-create-modal">
      <form onSubmit={submit} className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-2xl p-6 space-y-4 my-8">
        <div className="flex items-center justify-between">
          <h3 className="font-heading text-lg font-semibold">New payroll voucher</h3>
          <button type="button" onClick={onClose} className="text-[#525860]"><X className="w-4 h-4" /></button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Branch / office">
            <select data-testid="vc-branch" required value={branchId} onChange={(e) => setBranchId(e.target.value)}
              className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
              <option value="">— Select —</option>
              {myBranches.map((b) => <option key={b.id} value={b.id}>{b.name} ({b.code})</option>)}
            </select>
          </Field>
          <Field label="Period">
            <input data-testid="vc-period" required type="month" value={period} onChange={(e) => setPeriod(e.target.value)}
              className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
          </Field>
        </div>
        <Field label="Add employee line">
          <div className="flex gap-2">
            <select data-testid="vc-emp-pick" value={pick} onChange={(e) => setPick(e.target.value)}
              className="flex-1 bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
              <option value="">— Pick employee —</option>
              {pool.filter((e) => !lines.some((l) => l.employee_id === e.id)).map((e) => (
                <option key={e.id} value={e.id}>{e.first_name} {e.last_name} · {e.department}</option>
              ))}
            </select>
            <button type="button" data-testid="vc-add-emp" onClick={addLine} disabled={!pick}
              className="inline-flex items-center gap-1 text-sm border border-[#E2DFD6] px-3 py-2 rounded-md hover:bg-[#F7F6F2] disabled:opacity-40">
              <Plus className="w-4 h-4" /> Add
            </button>
          </div>
        </Field>
        {lines.length > 0 && (
          <div className="border border-[#E2DFD6] rounded-md overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-[#F7F6F2]">
                <tr>
                  {["Employee", "Gross", "PAYE", "NASSIT", "Loan", "Net", ""].map((h) => (
                    <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2 px-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => (
                  <tr key={l.employee_id} className="border-t border-[#E2DFD6]" data-testid={`vc-line-${i}`}>
                    <td className="py-1.5 px-2 font-medium">{l.employee_name}</td>
                    {["gross", "paye", "nassit_employee", "loan_deduction"].map((k) => (
                      <td key={k} className="py-1.5 px-2">
                        <input type="number" min="0" step="0.01" value={l[k]} onChange={(e) => setLine(i, k, e.target.value)}
                          className="w-20 bg-[#F7F6F2] border border-[#E2DFD6] rounded px-1.5 py-1 font-data" />
                      </td>
                    ))}
                    <td className="py-1.5 px-2 font-data font-semibold">{fmtSLE(netOf(l))}</td>
                    <td className="py-1.5 px-2">
                      <button type="button" onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))}
                        className="p-1 rounded hover:bg-[#FBEAEA] text-[#B83A3A]"><Trash2 className="w-3.5 h-3.5" /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-[#686D76] font-data">{lines.length} line item(s)</span>
          <div className="flex gap-2">
            <button type="button" onClick={onClose} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]">Cancel</button>
            <button type="submit" data-testid="vc-submit" disabled={busy || !branchId || !lines.length}
              className="text-sm bg-[#133326] text-white px-4 py-2 rounded-md disabled:opacity-50">Create draft</button>
          </div>
        </div>
      </form>
    </div>
  );
}

export function GenerateFromRunModal({ onClose, onDone }) {
  const [runs, setRuns] = useState([]);
  const [runId, setRunId] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/payroll/runs").then((r) => setRuns(r.data)).catch(() => setRuns([]));
  }, []);

  const generate = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/vouchers/generate-from-run/${runId}`);
      setResult(r.data);
      onDone();
      toast.success(`${r.data.created.length} voucher(s) created`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 grid place-items-center p-4" data-testid="voucher-generate-modal">
      <div className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-lg p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-heading text-lg font-semibold inline-flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#8B6A14]" /> Generate vouchers from payroll run
          </h3>
          <button onClick={onClose} className="text-[#525860]"><X className="w-4 h-4" /></button>
        </div>
        <p className="text-xs text-[#525860]">
          Splits a completed run into one draft voucher per branch, based on each employee's branch assignment.
          Branches that already have a voucher for the period are skipped.
        </p>
        <select data-testid="gen-run-select" value={runId} onChange={(e) => setRunId(e.target.value)}
          className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
          <option value="">— Select payroll run —</option>
          {runs.map((r) => (
            <option key={r.id} value={r.id}>{r.period} · {r.totals?.employee_count} employees · net {fmtSLE(r.totals?.net)}</option>
          ))}
        </select>
        {result && (
          <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-4 text-sm space-y-2" data-testid="gen-result">
            <div><span className="font-semibold text-[#2D7A5D]">{result.created.length} created:</span> {result.created.map((c) => `${c.voucher_ref} (${c.branch})`).join(", ") || "none"}</div>
            {result.skipped_existing.length > 0 && (
              <div><span className="font-semibold text-[#8B6A14]">{result.skipped_existing.length} skipped</span> — voucher already exists: {result.skipped_existing.map((s) => s.branch).join(", ")}</div>
            )}
            {result.unassigned_count > 0 && (
              <div className="text-[#B83A3A]">{result.unassigned_count} employee(s) have no branch — assign them under Branches & Offices: {result.unassigned.join(", ")}</div>
            )}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]">{result ? "Close" : "Cancel"}</button>
          {!result && (
            <button data-testid="gen-submit" disabled={busy || !runId} onClick={generate}
              className="text-sm bg-[#133326] text-white px-4 py-2 rounded-md disabled:opacity-50">Generate</button>
          )}
        </div>
      </div>
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
