/**
 * Mobile vouchers — role-filtered queue of vouchers waiting on my sign-off
 * (supervisor / finance / MoF). Tapping expands to show line-item summary
 * and a big "Approve" button. All actions call the existing voucher API.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { fmtSLE } from "../../lib/api";
import { ClipboardCheck, ChevronDown, ChevronUp } from "lucide-react";

const NEXT_ACTION_BY_STATUS = {
  submitted: { path: "supervisor-approve", label: "Supervisor approve",
               requires: ["supervisor", "admin", "superadmin"] },
  supervisor_approved: { path: "start-review", label: "Start review (Finance)",
                         requires: ["finance_officer", "admin", "superadmin"] },
  under_review: { path: "approve", label: "Approve (Finance)",
                  requires: ["finance_officer", "admin", "superadmin"] },
  approved: { path: "authorize", label: "Authorize (MoF)",
              requires: ["mof_approver", "admin", "superadmin"] },
};

export default function MobileVouchers() {
  const [rows, setRows] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [me, setMe] = useState(null);
  const [busy, setBusy] = useState(null);

  const refresh = () => {
    api.get("/vouchers?limit=50").then((r) => setRows(r.data || [])).catch(() => {});
    api.get("/auth/me").then((r) => setMe(r.data)).catch(() => {});
  };
  useEffect(refresh, []);

  const forMe = rows.filter((v) => {
    const nxt = NEXT_ACTION_BY_STATUS[v.status];
    if (!nxt) return false;
    return nxt.requires.includes(me?.role);
  });

  const act = async (v) => {
    const nxt = NEXT_ACTION_BY_STATUS[v.status];
    if (!nxt) return;
    setBusy(v.id);
    try {
      await api.post(`/vouchers/${v.id}/${nxt.path}`, { note: "" });
      toast.success(`${nxt.label} ✓`);
      refresh();
      setExpanded(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="p-4 space-y-4" data-testid="mobile-vouchers">
      <div>
        <h1 className="text-lg font-bold text-[#0A4A1E]">Vouchers</h1>
        <p className="text-[11px] text-[#525860]">
          {forMe.length} waiting on your role · {rows.length} total in view
        </p>
      </div>

      {forMe.length === 0 ? (
        <div className="text-center py-10 text-[#525860]" data-testid="mobile-vouchers-empty">
          <ClipboardCheck className="w-10 h-10 mx-auto text-[#A1A5AB]" />
          <p className="mt-2 text-sm">Clear queue — no vouchers need your sign-off right now.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {forMe.map((v) => {
            const nxt = NEXT_ACTION_BY_STATUS[v.status];
            const open = expanded === v.id;
            return (
              <div key={v.id} className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden"
                   data-testid={`mobile-voucher-row-${v.voucher_ref}`}>
                <button
                  onClick={() => setExpanded(open ? null : v.id)}
                  className="w-full flex items-center gap-3 p-3 active:bg-[#F7F6F2] text-left"
                  data-testid={`mobile-voucher-expand-${v.voucher_ref}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold">{v.voucher_ref}</div>
                    <div className="text-[11px] text-[#525860] mt-0.5 truncate">
                      {v.branch_name} · {v.period}
                    </div>
                    <div className="text-[10px] uppercase tracking-wider text-[#8B6A14] mt-1">
                      {v.status.replace(/_/g, " ")}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[13px] font-bold font-data">{fmtSLE(v.totals?.net || 0)}</div>
                    <div className="text-[10px] text-[#525860]">{v.totals?.employee_count || 0} employees</div>
                  </div>
                  {open ? <ChevronUp className="w-4 h-4 text-[#525860]" /> : <ChevronDown className="w-4 h-4 text-[#525860]" />}
                </button>

                {open && (
                  <div className="border-t border-[#F1EEE6] p-4 space-y-3 bg-[#FAFAF7]">
                    <dl className="grid grid-cols-2 gap-y-2 gap-x-3 text-[11px]">
                      <dt className="text-[#525860]">Gross</dt>
                      <dd className="font-data text-right">{fmtSLE(v.totals?.gross || 0)}</dd>
                      <dt className="text-[#525860]">PAYE</dt>
                      <dd className="font-data text-right">{fmtSLE(v.totals?.paye || 0)}</dd>
                      <dt className="text-[#525860]">NASSIT</dt>
                      <dd className="font-data text-right">{fmtSLE(v.totals?.nassit_employee || 0)}</dd>
                      <dt className="text-[#525860]">Loan deductions</dt>
                      <dd className="font-data text-right">{fmtSLE(v.totals?.loan_deduction || 0)}</dd>
                      <dt className="text-[#0A4A1E] font-semibold">Net (pay this)</dt>
                      <dd className="font-data text-right font-bold">{fmtSLE(v.totals?.net || 0)}</dd>
                    </dl>
                    <button
                      onClick={() => act(v)}
                      disabled={busy === v.id}
                      className="w-full bg-[#0A4A1E] text-white text-sm py-3 rounded-lg disabled:opacity-50 active:bg-[#083A17]"
                      data-testid={`mobile-voucher-act-${v.voucher_ref}`}
                    >
                      {busy === v.id ? "Signing…" : nxt.label}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
