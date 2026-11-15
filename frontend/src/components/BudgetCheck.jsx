import { useCallback, useEffect, useState } from "react";
import api, { fmtSLE } from "../lib/api";
import { toast } from "sonner";
import {
  ShieldCheck, AlertTriangle, XCircle, Loader2, X, Wallet, Play,
  UserX, Pencil, Check, Ban,
} from "lucide-react";

/** Anti-fraud pre-payroll budget check.
 *  Blocks Gov payroll runs that exceed IFMIS allocations unless an MoF approver
 *  overrides with a reason. Every override is audit-logged and SMS-notified. */
export function BudgetCheckModal({ period, isMofApprover, onConfirm, onClose, currentUserEmail }) {
  const [check, setCheck] = useState(null);
  const [busy, setBusy] = useState(true);
  const [reason, setReason] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [applying, setApplying] = useState(false);

  const runCheck = useCallback(async () => {
    setBusy(true);
    try {
      const r = await api.post("/payroll-budget/check", { period });
      setCheck(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Budget check failed");
      onClose();
    } finally { setBusy(false); }
  }, [period, onClose]);

  useEffect(() => { runCheck(); }, [runCheck]);

  const applyOverride = async () => {
    if (!check || reason.trim().length < 20 || confirmText !== "OVERRIDE") return;
    setApplying(true);
    try {
      await api.post("/payroll-budget/override", {
        check_id: check.id, reason: reason.trim(),
      });
      toast.success("Override applied — MoF approvers notified via SMS");
      setCheck({ ...check, override: { by: currentUserEmail || "you", at: new Date().toISOString(), reason } });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Override failed");
    } finally { setApplying(false); }
  };

  const verdict = check?.verdict;
  const isSafe = verdict === "safe";
  const isBlocked = ["over", "unallocated_employees"].includes(verdict);
  const isOverridden = !!check?.override;
  const canProceed = isSafe || (isBlocked && isOverridden) || verdict === "warn";
  let proceed = { cls: "bg-[#3A7CB8] hover:bg-[#2F6390]", label: "Blocked" };
  if (isSafe) proceed = { cls: "bg-[#17A035] hover:bg-[#127530]", label: "Confirm & run payroll" };
  else if (isOverridden) proceed = { cls: "bg-[#D1603D] hover:bg-[#B84F2F]", label: "Override & run payroll" };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" data-testid="budget-check-modal">
      <div className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <ModalHeader onClose={onClose} period={period} />

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {busy && <div className="text-center py-10"><Loader2 className="w-6 h-6 animate-spin mx-auto text-[#0A4A1E]" /></div>}
          {check && (
            <>
              <VerdictBanner verdict={verdict} totals={check.totals} isOverridden={isOverridden} />
              <BudgetTable rows={check.by_code} />
              {check.unallocated_employees?.length > 0 && (
                <UnallocatedList list={check.unallocated_employees} />
              )}
              {isBlocked && !isOverridden && isMofApprover && (
                <OverrideForm
                  reason={reason} setReason={setReason}
                  confirmText={confirmText} setConfirmText={setConfirmText}
                  applying={applying} onApply={applyOverride}
                />
              )}
              {isBlocked && !isOverridden && !isMofApprover && (
                <div className="bg-[#E9F2FB] border border-[#C2D9E9] rounded-md px-4 py-3 text-sm text-[#2F6390]" data-testid="budget-check-need-approver">
                  <div className="font-semibold mb-1">Blocked — MoF approver required</div>
                  <div>Your user does not have the <code className="font-data">mof_approver</code> flag. Ask a MoF approver to review this check and apply an override.</div>
                </div>
              )}
              {isOverridden && (
                <div className="bg-[#FBF1DE] border border-[#E8D5A2] rounded-md px-4 py-3 text-sm text-[#8B6A14]" data-testid="budget-check-override-notice">
                  <div className="font-semibold mb-1 flex items-center gap-2"><ShieldCheck className="w-4 h-4" /> Override active</div>
                  <div className="text-xs">Signed by {check.override.by} at {new Date(check.override.at).toLocaleString()}.</div>
                  <div className="text-xs mt-1 italic">&ldquo;{check.override.reason}&rdquo;</div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="border-t border-[#E2DFD6] px-6 py-4 flex items-center justify-end gap-2">
          <button onClick={onClose} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]" data-testid="budget-check-cancel">
            Cancel
          </button>
          <button
            onClick={() => onConfirm(check)}
            disabled={!canProceed || busy}
            data-testid="budget-check-proceed"
            className={`inline-flex items-center gap-2 text-sm px-5 py-2 rounded-md text-white transition ${proceed.cls} disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <Play className="w-4 h-4" /> {proceed.label}
          </button>
        </div>
      </div>
    </div>
  );
}

function ModalHeader({ onClose, period }) {
  return (
    <div className="px-6 py-5 border-b border-[#E2DFD6] flex items-start justify-between">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Anti-fraud guardrail</div>
        <h2 className="font-heading text-xl font-bold mt-0.5">Pre-payroll budget check · {period}</h2>
        <p className="text-xs text-[#525860] mt-1">Projected gross vs. IFMIS allocations. Overrides require MoF signature + notify all approvers via SMS.</p>
      </div>
      <button onClick={onClose} className="text-[#525860]" data-testid="budget-check-close" aria-label="Close">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

function VerdictBanner({ verdict, totals, isOverridden }) {
  const cfg = {
    safe: { icon: ShieldCheck, bg: "bg-[#E4F7E7]", border: "border-[#BFEBC8]", fg: "text-[#17A035]", label: "Safe to run" },
    warn: { icon: AlertTriangle, bg: "bg-[#FBF1DE]", border: "border-[#E8D5A2]", fg: "text-[#8B6A14]", label: "Warning — within 10% of budget" },
    over: { icon: XCircle, bg: "bg-[#E9F2FB]", border: "border-[#C2D9E9]", fg: "text-[#2F6390]", label: "Blocked — over budget" },
    unallocated_employees: { icon: UserX, bg: "bg-[#E9F2FB]", border: "border-[#C2D9E9]", fg: "text-[#2F6390]", label: "Blocked — unallocated employees" },
  }[verdict] || { icon: AlertTriangle, bg: "bg-[#F7F6F2]", border: "border-[#E2DFD6]", fg: "text-[#525860]", label: verdict };
  const Icon = cfg.icon;
  return (
    <div className={`${cfg.bg} ${cfg.border} ${cfg.fg} border rounded-md px-4 py-3`} data-testid={`budget-check-verdict-${verdict}`}>
      <div className="flex items-center gap-2 font-semibold">
        <Icon className="w-4 h-4" /> {cfg.label} {isOverridden && <span className="text-xs font-normal opacity-70">(override applied)</span>}
      </div>
      <div className="mt-1.5 text-xs font-data">
        Projected: {fmtSLE(totals.gross_projected_sle)} · Allocated: {fmtSLE(totals.allocated_sle)}
        {totals.codes_over > 0 && ` · Codes over: ${totals.codes_over}`}
        {totals.codes_warn > 0 && ` · Codes warn: ${totals.codes_warn}`}
        {totals.unallocated_headcount > 0 && ` · Unallocated: ${totals.unallocated_headcount}`}
      </div>
    </div>
  );
}

function BudgetTable({ rows }) {
  return (
    <div className="border border-[#E2DFD6] rounded-md overflow-hidden" data-testid="budget-check-table">
      <table className="w-full text-sm">
        <thead className="bg-[#F7F6F2]">
          <tr>{["Budget code", "Head", "Projected", "Allocated", "Utilisation", ""].map((h) => (
            <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-3 font-medium">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.budget_code} className="border-t border-[#F1EEE6]" data-testid={`budget-row-${r.budget_code}`}>
              <td className="px-3 py-2 font-data text-[13px]">{r.budget_code}</td>
              <td className="px-3 py-2 font-data">{r.headcount}</td>
              <td className="px-3 py-2 font-data">{fmtSLE(r.gross_projected_sle)}</td>
              <td className="px-3 py-2 font-data">{fmtSLE(r.allocated_sle)}</td>
              <td className="px-3 py-2 font-data">{r.utilization_pct != null ? `${r.utilization_pct}%` : "—"}</td>
              <td className="px-3 py-2">
                <VerdictPill v={r.verdict} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VerdictPill({ v }) {
  const c = {
    safe: "bg-[#E4F7E7] text-[#17A035]",
    warn: "bg-[#FBF1DE] text-[#8B6A14]",
    over: "bg-[#E9F2FB] text-[#2F6390]",
  }[v] || "bg-[#EBE8E0] text-[#525860]";
  return <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${c}`}>{v}</span>;
}

function UnallocatedList({ list }) {
  return (
    <div className="bg-[#E9F2FB] border border-[#C2D9E9] rounded-md px-4 py-3" data-testid="budget-check-unallocated-list">
      <div className="text-[13px] font-semibold text-[#2F6390] flex items-center gap-2 mb-2">
        <UserX className="w-4 h-4" /> {list.length} employee(s) without a budget code — a #1 ghost-worker vector
      </div>
      <ul className="text-xs text-[#2F6390] space-y-0.5">
        {list.slice(0, 10).map((e) => (
          <li key={e.employee_id} className="font-data">· {e.name} — {fmtSLE(e.gross)}</li>
        ))}
        {list.length > 10 && <li className="italic">…and {list.length - 10} more</li>}
      </ul>
      <div className="text-[11px] text-[#2F6390] mt-2 opacity-80">Assign a budget_code to each via <code className="font-data">/civil-service</code> before running payroll.</div>
    </div>
  );
}

function OverrideForm({ reason, setReason, confirmText, setConfirmText, applying, onApply }) {
  const reasonOk = reason.trim().length >= 20;
  const confirmOk = confirmText === "OVERRIDE";
  return (
    <div className="bg-[#F7F6F2] border-2 border-[#3A7CB8] rounded-md p-4 space-y-3" data-testid="budget-check-override-form">
      <div className="text-[13px] font-semibold text-[#2F6390] flex items-center gap-2">
        <ShieldCheck className="w-4 h-4" /> MoF approver override
      </div>
      <p className="text-xs text-[#525860]">You are about to override an anti-fraud budget guardrail. This action:</p>
      <ul className="text-xs text-[#525860] pl-4 list-disc space-y-0.5">
        <li>Is logged to the audit trail with your name, timestamp, and reason.</li>
        <li>Fires an SMS to <strong>every</strong> other MoF approver in this tenant.</li>
        <li>Is visible on the payroll run record forever.</li>
      </ul>
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Reason (minimum 20 chars)</label>
        <textarea
          data-testid="budget-check-override-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          maxLength={1000}
          placeholder="e.g., Supplementary appropriation approved by Parliament on 15-Feb; awaiting IFMIS journal update by DG Budget."
          className="w-full px-3 py-2 bg-white border border-[#E2DFD6] rounded-md text-sm"
        />
        <div className="text-[10px] text-[#686D76] mt-0.5 text-right">{reason.length}/1000 {reasonOk ? "✓" : `(${20 - reason.length} more)`}</div>
      </div>
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Type OVERRIDE to confirm</label>
        <input
          data-testid="budget-check-override-confirm"
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          placeholder="OVERRIDE"
          className="w-full px-3 py-2 bg-white border border-[#E2DFD6] rounded-md text-sm font-data uppercase"
        />
      </div>
      <button
        onClick={onApply}
        disabled={!reasonOk || !confirmOk || applying}
        data-testid="budget-check-override-apply"
        className="inline-flex items-center gap-2 bg-[#3A7CB8] hover:bg-[#2F6390] disabled:opacity-50 text-white text-sm px-4 py-2 rounded-md"
      >
        {applying ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
        Apply override & notify all approvers
      </button>
    </div>
  );
}


/** Inline table for CRUD-managing IFMIS budget balances per code/period.
 *  Admin-only. Shown as a collapsible panel on /payroll. */
export function BudgetBalancesPanel({ period }) {
  const [rows, setRows] = useState([]);
  const [codes, setCodes] = useState([]);
  const [busy, setBusy] = useState(true);
  const [editing, setEditing] = useState(null); // { code, allocated_sle }

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [balancesR, codesR] = await Promise.all([
        api.get("/payroll-budget/balances", { params: { period } }),
        api.get("/civil-service/budget-codes"),
      ]);
      setRows(balancesR.data.balances || []);
      setCodes(codesR.data || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load budget balances");
    } finally { setBusy(false); }
  }, [period]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!editing) return;
    try {
      await api.put(`/payroll-budget/balances/${encodeURIComponent(editing.code)}`, {
        allocated_sle: Number(editing.allocated_sle),
        period,
        note: editing.note || null,
      });
      toast.success(`Allocation saved for ${editing.code}`);
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
  };

  const balancesByCode = Object.fromEntries(rows.map((r) => [r.budget_code, r]));
  const merged = codes.map((c) => ({
    code: c.code, name: c.name, ministry: c.ministry,
    allocated_sle: balancesByCode[c.code]?.allocated_sle ?? null,
    updated_at: balancesByCode[c.code]?.updated_at,
  }));

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="budget-balances-panel">
      <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">IFMIS Budget Allocations</div>
          <h3 className="font-heading text-lg font-semibold">Budget balances · {period}</h3>
        </div>
        <span className="text-[11px] text-[#525860] font-data">
          Total allocated: <strong className="text-[#1A1C1E]">{fmtSLE(rows.reduce((s, r) => s + (r.allocated_sle || 0), 0))}</strong>
        </span>
      </div>
      {busy ? (
        <div className="p-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-[#0A4A1E]" /></div>
      ) : (
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Code", "Ministry", "Program", "Allocated (SLE)", "Updated", ""].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {merged.map((r) => (
              <tr key={r.code} className="border-t border-[#F1EEE6]" data-testid={`budget-balance-row-${r.code}`}>
                <td className="px-4 py-2.5 font-data font-semibold">{r.code}</td>
                <td className="px-4 py-2.5 text-[13px] text-[#525860] truncate max-w-[220px]">{r.ministry}</td>
                <td className="px-4 py-2.5 text-[13px] text-[#525860] truncate max-w-[220px]">{r.name}</td>
                <td className="px-4 py-2.5 font-data">
                  {r.allocated_sle == null ? <span className="text-[#3A7CB8]">— none —</span> : fmtSLE(r.allocated_sle)}
                </td>
                <td className="px-4 py-2.5 text-[11px] text-[#686D76] font-data">
                  {r.updated_at ? new Date(r.updated_at).toLocaleDateString() : "—"}
                </td>
                <td className="px-4 py-2.5">
                  <button
                    onClick={() => setEditing({ code: r.code, allocated_sle: r.allocated_sle || 0, note: "" })}
                    className="text-xs text-[#26547C] hover:underline inline-flex items-center gap-1"
                    data-testid={`budget-balance-edit-${r.code}`}
                  >
                    <Pencil className="w-3 h-3" /> Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" data-testid="budget-balance-edit-modal">
          <div className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-md p-6 space-y-4">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-[#525860]">Edit allocation</div>
              <h3 className="font-heading text-lg font-semibold mt-0.5">{editing.code} · {period}</h3>
            </div>
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Allocated (SLE)</label>
              <input
                type="number" min="0" step="0.01"
                data-testid="budget-balance-alloc-input"
                value={editing.allocated_sle}
                onChange={(e) => setEditing({ ...editing, allocated_sle: e.target.value })}
                className="w-full px-3 py-2 bg-white border border-[#E2DFD6] rounded-md text-sm font-data"
              />
            </div>
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Note (optional)</label>
              <input
                data-testid="budget-balance-note-input"
                value={editing.note || ""}
                onChange={(e) => setEditing({ ...editing, note: e.target.value })}
                placeholder="e.g., Q1 supplementary allocation approved 15-Feb"
                className="w-full px-3 py-2 bg-white border border-[#E2DFD6] rounded-md text-sm"
              />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#F1EEE6]">
              <button onClick={() => setEditing(null)} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]" data-testid="budget-balance-cancel">
                <Ban className="w-3.5 h-3.5 inline mr-1" /> Cancel
              </button>
              <button onClick={save} className="text-sm bg-[#0A4A1E] hover:bg-[#063514] text-white px-4 py-2 rounded-md inline-flex items-center gap-1.5" data-testid="budget-balance-save">
                <Check className="w-3.5 h-3.5" /> Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
