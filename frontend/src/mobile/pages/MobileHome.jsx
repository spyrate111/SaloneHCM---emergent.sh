/**
 * Mobile home — one API call to /api/mobile/summary, cached in localStorage
 * so a cold offline start still renders. Tiles route to feature screens.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../../lib/api";
import { fmtSLE } from "../../lib/api";
import { CalendarDays, FileText, Timer, ClipboardCheck, ChevronRight, MapPin, BellRing, GraduationCap } from "lucide-react";

const CACHE_KEY = "salonehcm_m_summary";

export default function MobileHome() {
  const [data, setData] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY) || "null"); } catch { return null; }
  });
  const [loading, setLoading] = useState(!data);

  useEffect(() => {
    let cancelled = false;
    api.get("/mobile/summary").then((r) => {
      if (cancelled) return;
      setData(r.data);
      try { localStorage.setItem(CACHE_KEY, JSON.stringify(r.data)); } catch { /* quota */ }
    }).catch(() => { /* keep cache */ })
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, []);

  const u = data?.user || {};
  const isSupervisor = ["admin", "superadmin", "mof_approver", "finance_officer", "supervisor"].includes(u.role);

  return (
    <div className="p-4 space-y-4" data-testid="mobile-home">
      {/* greeting */}
      <div>
        <h1 className="text-xl font-bold text-[#0A4A1E]" data-testid="mobile-home-greeting">
          Sɛn u kɔmɔt, {u.name?.split(" ")[0] || "there"}
        </h1>
        <p className="text-[11px] text-[#525860] mt-1">
          Role: <span className="uppercase tracking-wider">{u.role || "employee"}</span>
        </p>
      </div>

      {/* current payslip card */}
      {data?.payslip_current && (
        <Link
          to="/m/payslips"
          className="block bg-gradient-to-br from-[#0A4A1E] to-[#0F6C2A] text-white rounded-2xl p-5 shadow-sm active:opacity-90"
          data-testid="mobile-home-payslip-card"
        >
          <div className="text-[11px] uppercase tracking-widest text-white/70">This month's net</div>
          <div className="text-3xl font-bold mt-1 font-data">{fmtSLE(data.payslip_current.net)}</div>
          <div className="flex items-center gap-4 mt-3 text-[11px] text-white/80">
            <div>PAYE <span className="font-data text-white">{fmtSLE(data.payslip_current.paye)}</span></div>
            <div>NASSIT <span className="font-data text-white">{fmtSLE(data.payslip_current.nassit_employee)}</span></div>
          </div>
          <div className="flex justify-end mt-2">
            <span className="text-[11px] flex items-center gap-1">View payslips <ChevronRight className="w-3.5 h-3.5" /></span>
          </div>
        </Link>
      )}

      {/* quick tiles */}
      <div className="grid grid-cols-2 gap-3">
        <Tile to="/m/leave" icon={CalendarDays} label="Leave" value={`${data?.leave_balance_days ?? 0} days`}
              hint="annual balance" testid="mobile-home-tile-leave" />
        <Tile to="/m/clock" icon={Timer} label="Clock" value={data?.todays_punches?.length ? `${data.todays_punches.length} punches` : "not clocked in"}
              hint="today" testid="mobile-home-tile-clock" />
        <Tile to="/m/payslips" icon={FileText} label="Payslips" value={data?.payslip_latest ? data.payslip_latest.period : "—"}
              hint="latest run" testid="mobile-home-tile-payslips" />
        <Tile to="/m/training" icon={GraduationCap} label="Learn" value="Training"
              hint="videos in 4 languages" testid="mobile-home-tile-training" />
        {isSupervisor && (
          <Tile to="/m/vouchers" icon={ClipboardCheck} label="Vouchers"
                value={data?.voucher_queue?.length ? `${data.voucher_queue.length} to sign` : "clear"}
                hint="in your queue" testid="mobile-home-tile-vouchers" />
        )}
      </div>

      {/* pending reports leave */}
      {data?.pending_reports_leave?.length > 0 && (
        <section className="bg-white border border-[#E2DFD6] rounded-xl p-4" data-testid="mobile-home-pending-leave">
          <div className="text-[11px] uppercase tracking-widest text-[#8B6A14] flex items-center gap-1">
            <BellRing className="w-3.5 h-3.5" /> Leave requests waiting on you
          </div>
          <div className="mt-2 divide-y divide-[#F1EEE6]">
            {data.pending_reports_leave.slice(0, 4).map((lv) => (
              <Link
                key={lv.id}
                to="/m/leave"
                className="flex items-center justify-between py-2.5 text-sm active:bg-[#F7F6F2] -mx-2 px-2 rounded"
                data-testid={`mobile-home-pending-leave-item-${lv.id}`}
              >
                <div>
                  <div className="font-medium">{lv.employee_name}</div>
                  <div className="text-[11px] text-[#525860] mt-0.5">
                    {lv.leave_type} · {lv.days}d · {lv.start_date} → {lv.end_date}
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-[#A1A5AB]" />
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* voucher queue */}
      {isSupervisor && data?.voucher_queue?.length > 0 && (
        <section className="bg-white border border-[#E2DFD6] rounded-xl p-4" data-testid="mobile-home-voucher-queue">
          <div className="text-[11px] uppercase tracking-widest text-[#8B6A14] flex items-center gap-1">
            <ClipboardCheck className="w-3.5 h-3.5" /> Vouchers waiting on your role
          </div>
          <div className="mt-2 divide-y divide-[#F1EEE6]">
            {data.voucher_queue.slice(0, 4).map((v) => (
              <Link key={v.id} to="/m/vouchers" className="flex items-center justify-between py-2.5 text-sm active:bg-[#F7F6F2] -mx-2 px-2 rounded">
                <div>
                  <div className="font-medium">{v.voucher_ref}</div>
                  <div className="text-[11px] text-[#525860] mt-0.5">{v.branch_name} · {v.period}</div>
                </div>
                <div className="text-right">
                  <div className="font-data text-[13px]">{fmtSLE(v.totals?.net || 0)}</div>
                  <div className="text-[10px] uppercase tracking-wider text-[#525860]">{v.status.replace(/_/g, " ")}</div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* footer note */}
      <p className="text-center text-[10px] text-[#A1A5AB] pt-2">
        {loading ? "Refreshing…" : "Data cached for offline use"}
      </p>
    </div>
  );
}

function Tile({ to, icon: Icon, label, value, hint, testid }) {
  return (
    <Link
      to={to}
      className="bg-white border border-[#E2DFD6] rounded-xl p-4 active:bg-[#F7F6F2] transition-colors"
      data-testid={testid}
    >
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-[#E4F7E7] flex items-center justify-center">
          <Icon className="w-4 h-4 text-[#0A4A1E]" />
        </div>
        <div className="text-[10px] uppercase tracking-widest text-[#525860]">{label}</div>
      </div>
      <div className="text-lg font-bold text-[#1A1C1E] mt-2 truncate">{value}</div>
      <div className="text-[11px] text-[#686D76]">{hint}</div>
    </Link>
  );
}
