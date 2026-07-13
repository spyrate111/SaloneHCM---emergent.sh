import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useFeatures } from "../lib/features";
import { FileCheck2, Plus, Zap, Building2, Inbox } from "lucide-react";
import VoucherDetail, { STATUS_PILL } from "../components/VoucherDetail";
import BranchesPanel from "../components/BranchesPanel";
import { CreateVoucherModal, GenerateFromRunModal } from "../components/VoucherCreateModals";

const STATUS_FILTERS = [
  ["", "All"], ["draft", "Draft"], ["pending_supervisor", "Awaiting supervisor"],
  ["submitted", "Submitted"], ["under_review", "In review"], ["approved", "Approved"],
  ["payment_authorized", "Authorized"], ["returned", "Returned"],
];

export default function Vouchers() {
  const { user } = useAuth();
  const { has } = useFeatures();
  const isAdminRole = ["admin", "superadmin"].includes(user?.role);
  const canManage = isAdminRole || !!user?.finance_officer;
  const [tab, setTab] = useState("repo");
  const [vouchers, setVouchers] = useState([]);
  const [branches, setBranches] = useState([]);
  const [summary, setSummary] = useState(null);
  const [period, setPeriod] = useState("");
  const [branchId, setBranchId] = useState("");
  const [status, setStatus] = useState("");
  const [detailId, setDetailId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [generating, setGenerating] = useState(false);

  const refresh = useCallback(async () => {
    const params = {};
    if (period) params.period = period;
    if (branchId) params.branch_id = branchId;
    if (status) params.status = status;
    const [v, b, s] = await Promise.all([
      api.get("/vouchers", { params }),
      api.get("/branches"),
      api.get("/vouchers/summary", { params: period ? { period } : {} }),
    ]);
    setVouchers(v.data);
    setBranches(b.data);
    setSummary(s.data);
  }, [period, branchId, status]);

  useEffect(() => { if (has("payroll_vouchers")) refresh(); }, [refresh, has]);

  if (!has("payroll_vouchers")) {
    return (
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center" data-testid="vouchers-locked">
        <FileCheck2 className="w-10 h-10 text-[#A1A5AB] mx-auto mb-3" strokeWidth={1.4} />
        <h3 className="font-heading text-xl">Centralized Payroll Vouchers</h3>
        <p className="text-sm text-[#525860] mt-2 max-w-md mx-auto">
          Available on Enterprise and Government tiers. One digital repository for every branch's payroll voucher.
        </p>
      </div>
    );
  }

  const bs = summary?.by_status || {};
  const canCreate = canManage || branches.some((b) => b.supervisor_user_id === user?.id);

  return (
    <div className="space-y-6" data-testid="vouchers-page">
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Central Repository</div>
            <h1 className="font-heading text-3xl font-bold mt-1">Payroll Vouchers</h1>
            <p className="text-sm text-[#525860] mt-1 max-w-2xl">
              Every branch submits its monthly payroll voucher here — no spreadsheets, no paper.
              Vouchers are immutable after submission unless officially returned for correction.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isAdminRole && (
              <button data-testid="voucher-generate" onClick={() => setGenerating(true)}
                className="inline-flex items-center gap-1.5 border border-[#E2DFD6] hover:bg-[#F7F6F2] text-sm px-4 py-2.5 rounded-md">
                <Zap className="w-4 h-4 text-[#8B6A14]" /> Generate from run
              </button>
            )}
            {canCreate && (
              <button data-testid="voucher-new" onClick={() => setCreating(true)}
                className="inline-flex items-center gap-1.5 bg-[#133326] hover:bg-[#0F281E] text-white text-sm px-4 py-2.5 rounded-md">
                <Plus className="w-4 h-4" /> New voucher
              </button>
            )}
          </div>
        </div>
        {summary && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-5" data-testid="vouchers-kpis">
            <KPI label="Branches submitted" value={`${summary.branches_submitted}/${summary.branches_total}`} color="text-[#26547C]" />
            <KPI label="Awaiting supervisor" value={bs.pending_supervisor || 0} color="text-[#8B6A14]" />
            <KPI label="In review" value={(bs.submitted || 0) + (bs.under_review || 0)} color="text-[#26547C]" />
            <KPI label="Approved" value={bs.approved || 0} color="text-[#2D7A5D]" />
            <KPI label="Authorized" value={bs.payment_authorized || 0} color="text-[#2D7A5D]" />
            <KPI label="Total net" value={fmtSLE(summary.total_net)} small />
          </div>
        )}
      </div>

      <div className="flex gap-2 p-1 bg-[#F7F6F2] border border-[#E2DFD6] rounded-md w-fit">
        <TabBtn id="vouchers-tab-repo" active={tab === "repo"} onClick={() => setTab("repo")} icon={Inbox} label="Repository" />
        {isAdminRole && (
          <TabBtn id="vouchers-tab-branches" active={tab === "branches"} onClick={() => setTab("branches")} icon={Building2} label="Branches & Offices" />
        )}
      </div>

      {tab === "branches" && isAdminRole ? (
        <BranchesPanel branches={branches} onChanged={refresh} />
      ) : (
        <>
          <div className="bg-white border border-[#E2DFD6] rounded-lg p-4 flex flex-wrap items-center gap-3">
            <input data-testid="voucher-filter-period" type="month" value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
            <select data-testid="voucher-filter-branch" value={branchId} onChange={(e) => setBranchId(e.target.value)}
              className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
              <option value="">All branches</option>
              {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <div className="flex flex-wrap gap-1.5">
              {STATUS_FILTERS.map(([s, label]) => (
                <button key={s || "all"} data-testid={`voucher-filter-status-${s || "all"}`}
                  onClick={() => setStatus(s)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition ${status === s ? "bg-[#133326] text-white border-[#133326]" : "border-[#E2DFD6] text-[#525860] hover:bg-[#F7F6F2]"}`}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          {vouchers.length === 0 ? (
            <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center" data-testid="vouchers-empty">
              <FileCheck2 className="w-10 h-10 text-[#A1A5AB] mx-auto mb-3" strokeWidth={1.4} />
              <p className="text-sm text-[#525860]">No vouchers match — create one manually or generate from a payroll run.</p>
            </div>
          ) : (
            <VoucherTable vouchers={vouchers} onOpen={setDetailId} />
          )}
        </>
      )}

      {detailId && (
        <VoucherDetail voucherId={detailId} user={user} canManage={canManage} isAdminRole={isAdminRole}
          onClose={() => setDetailId(null)} onChanged={refresh} />
      )}
      {creating && (
        <CreateVoucherModal branches={branches} user={user} canManage={canManage}
          onClose={() => setCreating(false)} onSaved={() => { setCreating(false); refresh(); }} />
      )}
      {generating && (
        <GenerateFromRunModal onClose={() => setGenerating(false)} onDone={refresh} />
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

function TabBtn({ id, active, onClick, icon: Icon, label }) {
  return (
    <button data-testid={id} onClick={onClick}
      className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded transition ${active ? "bg-white text-[#133326] shadow-sm" : "text-[#686D76]"}`}>
      <Icon className="w-3.5 h-3.5" /> {label}
    </button>
  );
}

function VoucherTable({ vouchers, onOpen }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
      <table className="w-full text-sm" data-testid="vouchers-table">
        <thead className="bg-[#F7F6F2]">
          <tr>
            {["Voucher", "Branch", "Period", "Source", "Employees", "Net (SLE)", "Status", "Updated"].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {vouchers.map((v) => {
            const pill = STATUS_PILL[v.status] || STATUS_PILL.draft;
            return (
              <tr key={v.id} data-testid={`voucher-row-${v.id}`} onClick={() => onOpen(v.id)}
                className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB] cursor-pointer">
                <td className="py-3 px-4">
                  <div className="font-medium font-data">{v.voucher_ref}</div>
                  {v.revision > 1 && <div className="text-[10px] text-[#8B6A14]">rev {v.revision}</div>}
                </td>
                <td className="py-3 px-4">{v.branch_name}</td>
                <td className="py-3 px-4 font-data">{v.period}</td>
                <td className="py-3 px-4">
                  <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${v.source === "auto_run" ? "bg-[#E5EEF6] text-[#26547C]" : "bg-[#EBE8E0] text-[#525860]"}`}>
                    {v.source === "auto_run" ? "From run" : "Manual"}
                  </span>
                </td>
                <td className="py-3 px-4 font-data">{v.totals?.employee_count}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(v.totals?.net)}</td>
                <td className="py-3 px-4">
                  <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${pill.color}`}>{pill.label}</span>
                </td>
                <td className="py-3 px-4 text-xs text-[#686D76] font-data">{v.updated_at ? new Date(v.updated_at).toLocaleDateString() : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
