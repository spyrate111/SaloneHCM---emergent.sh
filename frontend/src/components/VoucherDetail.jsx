import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { toast } from "sonner";
import {
  X, Send, CheckCircle2, Undo2, Search, BadgeCheck, Banknote, Trash2, Pencil, Lock,
} from "lucide-react";

export const STATUS_PILL = {
  draft: { label: "Draft", color: "bg-[#EBE8E0] text-[#525860]" },
  pending_supervisor: { label: "Awaiting supervisor", color: "bg-[#FBF3D9] text-[#8B6A14]" },
  submitted: { label: "Submitted", color: "bg-[#E5EEF6] text-[#26547C]" },
  under_review: { label: "Under review", color: "bg-[#E5EEF6] text-[#26547C]" },
  approved: { label: "Approved", color: "bg-[#E4F7E7] text-[#17A035]" },
  payment_authorized: { label: "Payment authorized", color: "bg-[#0A4A1E] text-white" },
  returned: { label: "Returned", color: "bg-[#E9F2FB] text-[#3A7CB8]" },
};

const errMsg = (e) => {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : d?.message || "Action failed";
};

export default function VoucherDetail({ voucherId, user, canManage, isAdminRole, onClose, onChanged }) {
  const [v, setV] = useState(null);
  const [returning, setReturning] = useState(false);
  const [reason, setReason] = useState("");
  const [editing, setEditing] = useState(false);
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const r = await api.get(`/vouchers/${voucherId}`);
    setV(r.data);
    setItems(r.data.line_items);
  }, [voucherId]);

  useEffect(() => { load(); }, [load]);

  if (!v) return null;

  const me = user?.email;
  const isSupervisor = v.branch?.supervisor_user_id && v.branch.supervisor_user_id === user?.id;
  const isCreator = v.created_by === me;
  const editable = ["draft", "returned"].includes(v.status) && (isCreator || canManage || isSupervisor);
  const pill = STATUS_PILL[v.status] || STATUS_PILL.draft;

  const act = async (path, body = {}, ok = "Done") => {
    setBusy(true);
    try {
      await api.post(`/vouchers/${voucherId}/${path}`, body);
      toast.success(ok);
      setReturning(false);
      setReason("");
      await load();
      onChanged();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const saveEdits = async () => {
    setBusy(true);
    try {
      await api.patch(`/vouchers/${voucherId}`, {
        line_items: items.map((i) => ({
          employee_id: i.employee_id, gross: +i.gross, paye: +i.paye,
          nassit_employee: +i.nassit_employee, loan_deduction: +i.loan_deduction,
        })),
      });
      toast.success("Voucher updated");
      setEditing(false);
      await load();
      onChanged();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const del = async () => {
    if (!window.confirm("Delete this draft voucher?")) return;
    try {
      await api.delete(`/vouchers/${voucherId}`);
      toast.success("Draft deleted");
      onClose();
      onChanged();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const setItem = (idx, key, val) => {
    setItems((prev) => prev.map((it, i) => {
      if (i !== idx) return it;
      const next = { ...it, [key]: val };
      next.net = Math.round((+next.gross - +next.paye - +next.nassit_employee - +next.loan_deduction) * 100) / 100;
      return next;
    }));
  };

  return (
    <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4 overflow-y-auto" data-testid="voucher-detail-modal">
      <div className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-4xl my-8">
        <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h3 className="font-heading text-xl font-semibold font-data">{v.voucher_ref}</h3>
              <span data-testid="voucher-status-pill" className={`text-[10px] uppercase tracking-wider px-2.5 py-1 rounded-full ${pill.color}`}>{pill.label}</span>
              {v.revision > 1 && <span className="text-[10px] uppercase px-2 py-0.5 rounded-full bg-[#FBF3D9] text-[#8B6A14]">Revision {v.revision}</span>}
            </div>
            <div className="text-xs text-[#525860] mt-1.5">
              {v.branch_name} ({v.branch_code}) · Period <span className="font-data">{v.period}</span> ·
              {v.source === "auto_run" ? " Generated from payroll run" : " Manual submission"} · Created by {v.created_by_name || v.created_by}
            </div>
          </div>
          <button data-testid="voucher-detail-close" onClick={onClose} className="text-[#525860] hover:text-[#1A1C1E]"><X className="w-5 h-5" /></button>
        </div>

        {v.status === "returned" && v.returned_reason && (
          <div className="mx-6 mt-4 bg-[#E9F2FB] border border-[#3A7CB8]/30 rounded-md px-4 py-3 text-sm text-[#3A7CB8]" data-testid="voucher-returned-banner">
            <span className="font-semibold">Returned for correction:</span> {v.returned_reason}
          </div>
        )}
        {v.status === "payment_authorized" && (
          <div className="mx-6 mt-4 bg-[#E4F7E7] border border-[#17A035]/30 rounded-md px-4 py-3 text-sm text-[#17A035] flex items-center gap-2" data-testid="voucher-authorized-banner">
            <Lock className="w-4 h-4" /> Payment authorized by {v.authorized_by} — this voucher is now a permanent, immutable record.
          </div>
        )}

        <div className="px-6 py-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-[11px] uppercase tracking-wider text-[#525860]">Line items · {items.length}</h4>
            {editable && !editing && (
              <button data-testid="voucher-edit-toggle" onClick={() => setEditing(true)}
                className="inline-flex items-center gap-1 text-xs text-[#26547C] hover:underline">
                <Pencil className="w-3.5 h-3.5" /> Edit amounts
              </button>
            )}
          </div>
          <div className="border border-[#E2DFD6] rounded-md overflow-x-auto">
            <table className="w-full text-sm" data-testid="voucher-lines-table">
              <thead className="bg-[#F7F6F2]">
                <tr>
                  {["Employee", "Gross", "PAYE", "NASSIT", "Loan", "Net"].map((h) => (
                    <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2 px-3 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((li, i) => (
                  <tr key={li.employee_id} className="border-t border-[#E2DFD6]">
                    <td className="py-2 px-3 font-medium">{li.employee_name}</td>
                    {["gross", "paye", "nassit_employee", "loan_deduction"].map((k) => (
                      <td key={k} className="py-2 px-3 font-data">
                        {editing ? (
                          <input type="number" min="0" step="0.01" value={li[k]}
                            onChange={(e) => setItem(i, k, e.target.value)}
                            className="w-24 bg-[#F7F6F2] border border-[#E2DFD6] rounded px-2 py-1 text-xs font-data" />
                        ) : fmtSLE(li[k])}
                      </td>
                    ))}
                    <td className="py-2 px-3 font-data font-semibold">{fmtSLE(li.net)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-[#0A4A1E]/30 bg-[#F7F6F2] font-semibold">
                  <td className="py-2 px-3">TOTAL · {v.totals.employee_count} employees</td>
                  <td className="py-2 px-3 font-data">{fmtSLE(v.totals.gross)}</td>
                  <td className="py-2 px-3 font-data">{fmtSLE(v.totals.paye)}</td>
                  <td className="py-2 px-3 font-data">{fmtSLE(v.totals.nassit_employee)}</td>
                  <td className="py-2 px-3 font-data">{fmtSLE(v.totals.loan_deductions)}</td>
                  <td className="py-2 px-3 font-data">{fmtSLE(v.totals.net)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          {editing && (
            <div className="flex justify-end gap-2 mt-3">
              <button onClick={() => { setEditing(false); setItems(v.line_items); }} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]">Cancel</button>
              <button data-testid="voucher-edit-save" disabled={busy} onClick={saveEdits}
                className="text-sm bg-[#0A4A1E] text-white px-4 py-2 rounded-md disabled:opacity-50">Save corrections</button>
            </div>
          )}
        </div>

        <div className="px-6 pb-4">
          <h4 className="text-[11px] uppercase tracking-wider text-[#525860] mb-2">Audit trail</h4>
          <ol className="space-y-2" data-testid="voucher-timeline">
            {(v.status_history || []).map((h, i) => (
              <li key={`${h.at}-${h.action}-${i}`} className="flex items-start gap-3 text-xs">
                <span className="mt-1 w-2 h-2 rounded-full bg-[#26547C] shrink-0" />
                <div>
                  <span className="font-medium capitalize">{h.action.replace(/_/g, " ")}</span>
                  {h.from && h.from !== h.to && <span className="text-[#686D76]"> ({h.from} → {h.to})</span>}
                  <span className="text-[#686D76]"> · {h.by_name || h.by_email} ({h.by_role}) · {new Date(h.at).toLocaleString()}</span>
                  {h.note && <div className="text-[#525860] italic mt-0.5">"{h.note}"</div>}
                </div>
              </li>
            ))}
          </ol>
        </div>

        {returning ? (
          <div className="px-6 pb-6 border-t border-[#E2DFD6] pt-4" data-testid="voucher-return-form">
            <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Reason for return (min 10 characters)</label>
            <textarea data-testid="voucher-return-reason" value={reason} onChange={(e) => setReason(e.target.value)}
              rows={2} placeholder="Explain what must be corrected…"
              className="w-full bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
            <div className="flex justify-end gap-2 mt-2">
              <button onClick={() => setReturning(false)} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]">Cancel</button>
              <button data-testid="voucher-return-confirm" disabled={busy || reason.trim().length < 10}
                onClick={() => act("return", { reason: reason.trim() }, "Voucher returned for correction")}
                className="text-sm bg-[#3A7CB8] text-white px-4 py-2 rounded-md disabled:opacity-50">Return for correction</button>
            </div>
          </div>
        ) : (
          <div className="px-6 pb-6 border-t border-[#E2DFD6] pt-4 flex flex-wrap items-center justify-end gap-2" data-testid="voucher-actions">
            {v.status === "draft" && (isCreator || canManage) && (
              <button data-testid="voucher-action-delete" onClick={del}
                className="inline-flex items-center gap-1.5 text-sm text-[#3A7CB8] border border-[#E2DFD6] px-4 py-2 rounded-md hover:bg-[#E9F2FB]">
                <Trash2 className="w-4 h-4" /> Delete draft
              </button>
            )}
            {editable && !editing && (
              <button data-testid="voucher-action-submit" disabled={busy} onClick={() => act("submit", {}, "Voucher submitted")}
                className="inline-flex items-center gap-1.5 text-sm bg-[#0A4A1E] text-white px-4 py-2 rounded-md disabled:opacity-50">
                <Send className="w-4 h-4" /> {v.status === "returned" ? "Resubmit" : "Submit"}
              </button>
            )}
            {v.status === "pending_supervisor" && (isSupervisor || isAdminRole) && (
              <button data-testid="voucher-action-supervisor-approve" disabled={busy}
                onClick={() => act("supervisor-approve", {}, "Supervisor approval recorded")}
                className="inline-flex items-center gap-1.5 text-sm bg-[#0A4A1E] text-white px-4 py-2 rounded-md disabled:opacity-50">
                <BadgeCheck className="w-4 h-4" /> Supervisor approve
              </button>
            )}
            {v.status === "submitted" && canManage && (
              <button data-testid="voucher-action-start-review" disabled={busy}
                onClick={() => act("start-review", {}, "Review started")}
                className="inline-flex items-center gap-1.5 text-sm bg-[#26547C] text-white px-4 py-2 rounded-md disabled:opacity-50">
                <Search className="w-4 h-4" /> Start review
              </button>
            )}
            {v.status === "under_review" && canManage && (
              isCreator ? (
                <span className="text-xs text-[#8B6A14]" data-testid="voucher-approve-blocked">Segregation of duties — you created this voucher, another finance officer must approve it.</span>
              ) : (
                <button data-testid="voucher-action-approve" disabled={busy}
                  onClick={() => act("approve", {}, "Voucher approved")}
                  className="inline-flex items-center gap-1.5 text-sm bg-[#17A035] text-white px-4 py-2 rounded-md disabled:opacity-50">
                  <CheckCircle2 className="w-4 h-4" /> Approve
                </button>
              )
            )}
            {v.status === "approved" && (isAdminRole || user?.mof_approver) && (
              isCreator || v.approved_by === me ? (
                <span className="text-xs text-[#8B6A14]" data-testid="voucher-authorize-blocked">Dual control — a different officer must authorize payment.</span>
              ) : (
                <button data-testid="voucher-action-authorize" disabled={busy}
                  onClick={() => act("authorize", {}, "Payment authorized")}
                  className="inline-flex items-center gap-1.5 text-sm bg-[#0A4A1E] text-white px-4 py-2 rounded-md disabled:opacity-50">
                  <Banknote className="w-4 h-4" /> Authorize payment
                </button>
              )
            )}
            {["pending_supervisor", "submitted", "under_review", "approved"].includes(v.status) &&
              (canManage || (isSupervisor && v.status === "pending_supervisor")) && (
              <button data-testid="voucher-action-return" onClick={() => setReturning(true)}
                className="inline-flex items-center gap-1.5 text-sm text-[#3A7CB8] border border-[#E2DFD6] px-4 py-2 rounded-md hover:bg-[#E9F2FB]">
                <Undo2 className="w-4 h-4" /> Return for correction
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
