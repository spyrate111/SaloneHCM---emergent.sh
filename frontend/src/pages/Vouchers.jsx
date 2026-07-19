import { useEffect, useState, useCallback, useMemo } from "react";
import api from "../lib/api";
import { fmtSLE, downloadBlob } from "../lib/api";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { useFeatures } from "../lib/features";
import { FileCheck2, Plus, Zap, Building2, Inbox, FileDown, Mail, CheckCircle2 } from "lucide-react";
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
  const [packHistory, setPackHistory] = useState([]);

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
    if (canManage) {
      api.get("/vouchers/pack-history").then((r) => setPackHistory(r.data || [])).catch(() => {});
    }
  }, [period, branchId, status, canManage]);

  const closedPack = useMemo(() => {
    const sent = packHistory.filter((h) => h.status === "sent");
    if (period) return sent.find((h) => h.period === period) || null;
    const latest = sent[0];
    if (latest && Date.now() - new Date(latest.sent_at).getTime() < 24 * 3600 * 1000) return latest;
    return null;
  }, [packHistory, period]);

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
                className="inline-flex items-center gap-1.5 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-4 py-2.5 rounded-md">
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
            <KPI label="Approved" value={bs.approved || 0} color="text-[#17A035]" />
            <KPI label="Authorized" value={bs.payment_authorized || 0} color="text-[#17A035]" />
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

      {isAdminRole && <PackEmailCard history={packHistory} onRefresh={refresh} />}

      {canManage && closedPack && (
        <div data-testid="period-closed-banner" className="flex flex-wrap items-center gap-3 bg-[#E4F7E7] border border-[#17A035]/50 rounded-lg px-4 py-3">
          <CheckCircle2 className="w-5 h-5 text-[#128A2C] shrink-0" />
          <div className="text-sm text-[#0A4A1E]">
            <b>Period {closedPack.period} closed</b> — every branch voucher is payment-authorized.
            MoF pack emailed to <b>{closedPack.to}</b> · {new Date(closedPack.sent_at).toLocaleString()}.
          </div>
          <button
            data-testid="period-closed-download"
            onClick={() => downloadBlob(`/vouchers/export-batch.pdf?period=${closedPack.period}`, `mof-voucher-pack-${closedPack.period}.pdf`).catch(() => toast.error("Download failed"))}
            className="ml-auto inline-flex items-center gap-1.5 text-xs font-medium border border-[#17A035]/50 text-[#0A4A1E] px-3 py-1.5 rounded-md hover:bg-white"
          >
            <FileDown className="w-3.5 h-3.5" /> Download pack
          </button>
        </div>
      )}

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
                  className={`text-xs px-3 py-1.5 rounded-full border transition ${status === s ? "bg-[#0A4A1E] text-white border-[#0A4A1E]" : "border-[#E2DFD6] text-[#525860] hover:bg-[#F7F6F2]"}`}>
                  {label}
                </button>
              ))}
            </div>
            {canManage && (
              <button
                data-testid="voucher-batch-export"
                disabled={!period}
                title={period ? "Download every payment-authorized voucher for this period as one PDF pack" : "Pick a period first"}
                onClick={async () => {
                  try {
                    await downloadBlob(`/vouchers/export-batch.pdf?period=${period}`, `mof-voucher-pack-${period}.pdf`);
                    toast.success("MoF pack downloaded");
                  } catch (e) {
                    toast.error(e?.response?.status === 404
                      ? "No payment-authorized vouchers for this period"
                      : "Export failed");
                  }
                }}
                className="ml-auto inline-flex items-center gap-1.5 text-sm border border-[#E2DFD6] px-4 py-2 rounded-md hover:bg-[#E4F7E7] text-[#0A4A1E] disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <FileDown className="w-4 h-4" /> MoF pack (PDF)
              </button>
            )}
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

function PackEmailCard({ history = [], onRefresh }) {
  const [email, setEmail] = useState("");
  const [sendPeriod, setSendPeriod] = useState("");
  const [busy, setBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    api.get("/vouchers/pack-config").then((r) => {
      setEmail(r.data.email || "");
    }).catch(() => {});
  }, []);

  const save = async () => {
    setBusy(true);
    try {
      await api.put("/vouchers/pack-config", { email: email.trim() });
      toast.success(email.trim() ? "Auto-email enabled" : "Auto-email disabled");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save");
    } finally {
      setBusy(false);
    }
  };

  const sendNow = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/vouchers/pack-config/send-now?period=${sendPeriod}`);
      if (r.data.ok) toast.success(`Pack sent to ${r.data.to}`);
      else toast.error(`Send failed: ${r.data.error || "email provider rejected"}`);
      onRefresh?.();
    } catch (e) {
      toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not send");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-4" data-testid="pack-email-card">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[220px]">
          <div className="text-[11px] uppercase tracking-wider text-[#525860] flex items-center gap-1.5">
            <Mail className="w-3.5 h-3.5" /> Auto-email MoF pack
          </div>
          <p className="text-xs text-[#686D76] mt-0.5">
            The moment every branch's voucher for a period is payment-authorized, the combined pack is emailed here.
          </p>
        </div>
        <input
          data-testid="pack-email-input"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="ministry.inbox@mof.gov.sl"
          className="flex-1 min-w-[220px] bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
        />
        <button
          data-testid="pack-email-save"
          disabled={busy}
          onClick={save}
          className="text-sm bg-[#0A4A1E] text-white px-4 py-2 rounded-md disabled:opacity-50"
        >
          Save
        </button>
        <div className="flex items-center gap-2">
          <input data-testid="pack-send-period" type="month" value={sendPeriod}
            onChange={(e) => setSendPeriod(e.target.value)}
            className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-2 py-2 text-xs" />
          <button
            data-testid="pack-send-now"
            disabled={busy || !sendPeriod || !email.trim()}
            onClick={sendNow}
            className="text-sm border border-[#E2DFD6] text-[#0A4A1E] px-3 py-2 rounded-md hover:bg-[#E4F7E7] disabled:opacity-40"
          >
            Send now
          </button>
        </div>
      </div>
      {history.length > 0 && (
        <div className="mt-3">
          <button
            data-testid="pack-history-toggle"
            onClick={() => setShowHistory(!showHistory)}
            className="text-[11px] font-medium text-[#26547C] hover:underline"
          >
            {showHistory ? "Hide" : "Show"} pack history ({history.length})
          </button>
          {showHistory && (
            <table className="w-full text-xs mt-2" data-testid="pack-history-table">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-[#525860]">
                  <th className="text-left py-1.5 pr-3 font-medium">Period</th>
                  <th className="text-left py-1.5 pr-3 font-medium">Sent to</th>
                  <th className="text-left py-1.5 pr-3 font-medium">Vouchers</th>
                  <th className="text-left py-1.5 pr-3 font-medium">Status</th>
                  <th className="text-left py-1.5 pr-3 font-medium">When</th>
                  <th className="text-right py-1.5 font-medium">Pack</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id} className="border-t border-[#F1EEE6]">
                    <td className="py-1.5 pr-3 font-data">{h.period}</td>
                    <td className="py-1.5 pr-3">{h.to}</td>
                    <td className="py-1.5 pr-3 font-data">{h.voucher_count}</td>
                    <td className="py-1.5 pr-3">
                      <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${h.status === "sent" ? "bg-[#E4F7E7] text-[#128A2C]" : "bg-[#E9F2FB] text-[#005A9C]"}`}>
                        {h.status}
                      </span>
                    </td>
                    <td className="py-1.5 pr-3 text-[#686D76]">{new Date(h.sent_at).toLocaleString()}</td>
                    <td className="py-1.5 text-right">
                      <button
                        data-testid={`pack-history-download-${h.period}`}
                        onClick={() => downloadBlob(`/vouchers/export-batch.pdf?period=${h.period}`, `mof-voucher-pack-${h.period}.pdf`).catch(() => toast.error("Download failed"))}
                        className="inline-flex items-center gap-1 text-[11px] text-[#0A4A1E] hover:underline"
                      >
                        <FileDown className="w-3 h-3" /> Download
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
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
      className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded transition ${active ? "bg-white text-[#0A4A1E] shadow-sm" : "text-[#686D76]"}`}>
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
