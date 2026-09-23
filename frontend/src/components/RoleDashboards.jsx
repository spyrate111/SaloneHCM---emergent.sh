/** Role-scoped dashboards — each role only sees sections it may access. */
import { useEffect, useState } from "react";
import api, { fmtSLE, fmtNum } from "../lib/api";
import RoleTour from "./RoleTourCard";
import ChartShell from "./ChartShell";
import { TOOLTIP_STYLE } from "../lib/chartStyles";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import {
  Users, CalendarClock, Clock, Wallet, Receipt, FileCheck, ScrollText,
  ShieldAlert, ArrowUpRight, MapPin, GraduationCap, Building2, UserCog,
} from "lucide-react";

export const Kpi = ({ label, value, sub, icon: Icon, accent }) => (
  <div className="bg-white border border-[#E2DFD6] rounded-lg p-5 hover:shadow-sm transition"
       data-testid={`kpi-${label.toLowerCase().replace(/\s/g, "-")}`}>
    <div className="flex items-start justify-between">
      <div>
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{label}</div>
        <div className="mt-2 font-heading text-2xl font-bold text-[#1A1C1E] font-data">{value}</div>
        {sub && <div className="text-xs text-[#686D76] mt-1">{sub}</div>}
      </div>
      <div className={`w-9 h-9 rounded-md grid place-items-center ${accent}`}>
        <Icon className="w-[18px] h-[18px] text-white" strokeWidth={1.5} />
      </div>
    </div>
  </div>
);

const Header = ({ kicker, name, sub }) => (
  <div>
    <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">{kicker}</div>
    <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-[#1A1C1E] mt-1">
      Good day, {name?.split(" ")[0] || "there"}.
    </h1>
    <p className="text-[#525860] mt-2 text-sm max-w-2xl">{sub}</p>
  </div>
);

const LinkCard = ({ to, kicker, title, sub, dark, testId }) => (
  <a href={to}
     className={`group rounded-lg p-6 transition ${dark
       ? "bg-[#0A4A1E] text-white hover:bg-[#063514]"
       : "bg-white border border-[#E2DFD6] hover:shadow-md"}`}
     data-testid={testId}>
    <div className={`text-[10px] uppercase tracking-[0.18em] ${dark ? "text-white/60" : "text-[#525860]"}`}>{kicker}</div>
    <div className={`font-heading text-xl font-semibold mt-2 ${dark ? "" : "text-[#1A1C1E]"}`}>{title}</div>
    <div className={`text-sm mt-1 ${dark ? "text-white/70" : "text-[#686D76]"}`}>{sub}</div>
    <div className={`mt-5 inline-flex items-center gap-2 text-sm font-medium ${dark ? "text-[#D1603D]" : "text-[#26547C]"}`}>
      Open <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
    </div>
  </a>
);

export function HrDashboard({ user }) {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/dashboard/role-summary").then((r) => setD(r.data)).catch(() => {}); }, []);
  if (!d) return <div className="text-[#525860] text-sm">Loading dashboard…</div>;
  return (
    <div className="space-y-8" data-testid="dashboard-hr">
      <Header kicker="HR Overview" name={user?.name}
              sub="People at a glance — employee records, leave, attendance and training." />
      <RoleTour user={user} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Kpi label="Headcount" value={fmtNum(d.headcount)} sub={`${d.total_employees} total records`} icon={Users} accent="bg-[#0A4A1E]" />
        <Kpi label="Pending Leaves" value={fmtNum(d.pending_leaves)} sub="Awaiting decision" icon={CalendarClock} accent="bg-[#D1603D]" />
        <Kpi label="On Leave Today" value={fmtNum(d.on_leave_today)} sub="Approved absences" icon={CalendarClock} accent="bg-[#8B6A14]" />
        <Kpi label="Punches Today" value={fmtNum(d.punches_today)} sub="Attendance events" icon={Clock} accent="bg-[#26547C]" />
      </div>
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860] mb-3">Headcount by department</div>
        <div className="flex flex-wrap gap-2" data-testid="hr-departments">
          {(d.departments || []).map((x) => (
            <span key={x.name} className="text-xs bg-[#F7F6F2] border border-[#E2DFD6] rounded-full px-3 py-1.5">
              {x.name} · <b className="font-data">{x.count}</b>
            </span>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        <LinkCard to="/employees" kicker="People" title="Employee records" sub="Profiles, grades, documents & onboarding." dark testId="hr-quick-employees" />
        <LinkCard to="/leave" kicker="Leave" title="Leave management" sub="Approve requests and view the team calendar." testId="hr-quick-leave" />
        <LinkCard to="/attendance" kicker="Time" title="Attendance & punch map" sub="Daily punches with geofence zones." testId="hr-quick-attendance" />
        <LinkCard to="/talent" kicker="Growth" title="Training & talent" sub="Skills, reviews and development." testId="hr-quick-training" />
      </div>
    </div>
  );
}

export function PayrollDashboard({ user }) {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/dashboard/role-summary").then((r) => setD(r.data)).catch(() => {}); }, []);
  if (!d) return <div className="text-[#525860] text-sm">Loading dashboard…</div>;
  return (
    <div className="space-y-8" data-testid="dashboard-payroll">
      <Header kicker="Payroll Overview" name={user?.name}
              sub="Payroll processing, payslips and salary records." />
      <RoleTour user={user} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Kpi label="Monthly Payroll" value={fmtSLE(d.monthly_payroll_sle)} sub="Gross run estimate" icon={Wallet} accent="bg-[#26547C]" />
        <Kpi label="Last Run Net" value={fmtSLE(d.last_run?.totals?.net || 0)} sub={d.last_run?.period || "No runs yet"} icon={Receipt} accent="bg-[#17A035]" />
        <Kpi label="Payroll Runs" value={fmtNum(d.runs_total)} sub="All periods" icon={FileCheck} accent="bg-[#0A4A1E]" />
        <Kpi label="Filings Outstanding" value={fmtNum(d.outstanding_filings)} sub="NRA PAYE returns due" icon={ShieldAlert} accent="bg-[#B03A2E]" />
      </div>
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Payroll trend</div>
        <h3 className="font-heading text-lg font-semibold text-[#1A1C1E] mb-4">Net payroll cost across periods</h3>
        <ChartShell height={230}>
          {d.runs_history?.length ? (
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} debounce={50}>
              <AreaChart data={d.runs_history}>
                <defs>
                  <linearGradient id="gp1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#26547C" stopOpacity={0.45} />
                    <stop offset="100%" stopColor="#26547C" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#EBE8E0" vertical={false} />
                <XAxis dataKey="period" stroke="#686D76" fontSize={11} />
                <YAxis stroke="#686D76" fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => fmtSLE(v)} />
                <Area type="monotone" dataKey="net" stroke="#26547C" strokeWidth={2} fill="url(#gp1)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full grid place-items-center text-sm text-[#686D76]">Run your first payroll to see trends.</div>
          )}
        </ChartShell>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <LinkCard to="/payroll" kicker="Processing" title="Run payroll" sub="Auto-calculates PAYE & NASSIT per employee." dark testId="payroll-quick-run" />
        <LinkCard to="/compliance" kicker="Filings" title="NRA & NASSIT exports" sub="Filing-ready CSVs and return status." testId="payroll-quick-compliance" />
        <LinkCard to="/scan-logs" kicker="Anti-fraud" title="Payslip scan logs" sub="QR verification activity and flags." testId="payroll-quick-scans" />
      </div>
    </div>
  );
}

export function ManagerDashboard({ user }) {
  const [d, setD] = useState(null);
  const [team, setTeam] = useState(null);
  useEffect(() => {
    api.get("/mobile/summary").then((r) => setD(r.data)).catch(() => {});
    api.get("/mobile/punch/team").then((r) => setTeam(r.data)).catch(() => setTeam(null));
  }, []);
  if (!d) return <div className="text-[#525860] text-sm">Loading dashboard…</div>;
  const pending = d.pending_reports_leave || [];
  const lastPunch = (d.todays_punches || []).slice(-1)[0];
  return (
    <div className="space-y-8" data-testid="dashboard-manager">
      <Header kicker="Team Overview" name={user?.name}
              sub="Your team's attendance, punch map and leave approvals." />
      <RoleTour user={user} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Kpi label="Pending Approvals" value={fmtNum(pending.length)} sub="Leave awaiting your decision" icon={CalendarClock} accent="bg-[#D1603D]" />
        <Kpi label="My Clock Status" value={lastPunch ? (lastPunch.kind === "in" ? "IN" : "OUT") : "—"}
             sub={lastPunch ? `since ${(lastPunch.clocked_at || "").slice(11, 16)} UTC` : "No punch today"} icon={Clock} accent="bg-[#0A4A1E]" />
        <Kpi label="Team Punches Today" value={team ? fmtNum(team.stats?.total ?? 0) : "—"}
             sub={team ? `${team.stats?.out_zone ?? 0} out of zone` : "No branch supervision"} icon={MapPin} accent="bg-[#26547C]" />
        <Kpi label="My Leave Balance" value={d.leave_balance_days ?? "—"} sub="Annual days remaining" icon={CalendarClock} accent="bg-[#8B6A14]" />
      </div>
      {pending.length > 0 && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="manager-pending-list">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#8B6A14] mb-3">Waiting on you</div>
          <div className="space-y-2">
            {pending.slice(0, 4).map((lv) => (
              <div key={lv.id} className="flex items-center justify-between text-sm border-b border-[#F0EEE8] pb-2">
                <span>{lv.employee_name} · <span className="capitalize">{lv.leave_type}</span> · {lv.start_date} → {lv.end_date}</span>
                <a href="/leave" className="text-[#26547C] text-xs font-semibold">Decide →</a>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <LinkCard to="/leave" kicker="Approvals" title="Leave approvals" sub="Decide your reports' requests with coverage checks." dark testId="manager-quick-leave" />
        <LinkCard to="/attendance" kicker="Time" title="Team attendance & map" sub="Punches with geofence zones for your branch." testId="manager-quick-attendance" />
        <LinkCard to="/team" kicker="People" title="My team" sub="Direct reports and their profiles." testId="manager-quick-team" />
      </div>
    </div>
  );
}

export function EmployeeDashboard({ user }) {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/mobile/summary").then((r) => setD(r.data)).catch(() => {}); }, []);
  if (!d) return <div className="text-[#525860] text-sm">Loading dashboard…</div>;
  const lastPunch = (d.todays_punches || []).slice(-1)[0];
  const slip = d.payslip_latest;
  const pendingMine = (d.my_leave || []).filter((l) => l.status === "pending").length;
  return (
    <div className="space-y-8" data-testid="dashboard-employee">
      <Header kicker="My Workspace" name={user?.name}
              sub="Your clock, payslips, leave and training — all in one place." />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Kpi label="Clock Status" value={lastPunch ? (lastPunch.kind === "in" ? "IN" : "OUT") : "—"}
             sub={lastPunch ? `since ${(lastPunch.clocked_at || "").slice(11, 16)} UTC` : "No punch today"} icon={Clock} accent="bg-[#0A4A1E]" />
        <Kpi label="Leave Balance" value={d.leave_balance_days ?? "—"} sub="Annual days remaining" icon={CalendarClock} accent="bg-[#8B6A14]" />
        <Kpi label="Latest Payslip" value={slip ? fmtSLE(slip.slip?.net_sle ?? slip.slip?.net ?? 0) : "—"}
             sub={slip?.period || "No payroll run yet"} icon={Receipt} accent="bg-[#17A035]" />
        <Kpi label="My Pending Requests" value={fmtNum(pendingMine)} sub="Leave awaiting approval" icon={CalendarClock} accent="bg-[#D1603D]" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        <LinkCard to="/m/clock" kicker="Time" title="Clock in / out" sub="Geo-tagged punch from your phone or desktop." dark testId="employee-quick-clock" />
        <LinkCard to="/m/payslips" kicker="Pay" title="My payslips" sub="Download or save payslips for offline." testId="employee-quick-payslips" />
        <LinkCard to="/leave" kicker="Leave" title="Request leave" sub="Submit and track your leave requests." testId="employee-quick-leave" />
        <LinkCard to="/m/training" kicker="Learn" title="Training videos" sub="Short lessons in English and Krio." testId="employee-quick-training" />
      </div>
    </div>
  );
}

export function AuditorDashboard({ user }) {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/dashboard/role-summary").then((r) => setD(r.data)).catch(() => {}); }, []);
  if (!d) return <div className="text-[#525860] text-sm">Loading dashboard…</div>;
  return (
    <div className="space-y-8" data-testid="dashboard-auditor">
      <Header kicker="Oversight · Read-only" name={user?.name}
              sub="Audit logs, compliance reports and payslip scan activity." />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Kpi label="Audit Entries 24h" value={fmtNum(d.audit_24h)} sub={`${fmtNum(d.audit_total)} total`} icon={ScrollText} accent="bg-[#0A4A1E]" />
        <Kpi label="Flagged Scans" value={fmtNum(d.flagged_scans)} sub="Suspicious payslip re-scans" icon={ShieldAlert} accent="bg-[#B03A2E]" />
        <Kpi label="NRA Filings" value={fmtNum(d.filings)} sub="Returns recorded" icon={FileCheck} accent="bg-[#26547C]" />
        <Kpi label="Access Level" value="Read-only" sub="No write permissions" icon={UserCog} accent="bg-[#8B6A14]" />
      </div>
      {(d.recent_audit || []).length > 0 && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="auditor-recent-audit">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860] mb-3">Latest audit activity</div>
          <div className="space-y-2">
            {d.recent_audit.map((r, i) => (
              <div key={i} className="flex items-center justify-between text-sm border-b border-[#F0EEE8] pb-2">
                <span className="font-medium">{r.action}</span>
                <span className="text-xs text-[#686D76]">{r.user_email} · {(r.ts || "").slice(0, 16).replace("T", " ")}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <LinkCard to="/audit" kicker="Oversight" title="Audit log" sub="Every mutation with actor & timestamp — export CSV/PDF." dark testId="auditor-quick-audit" />
        <LinkCard to="/compliance" kicker="Reports" title="Compliance reports" sub="NRA & NASSIT filing-ready downloads." testId="auditor-quick-compliance" />
        <LinkCard to="/scan-logs" kicker="Anti-fraud" title="Payslip scan logs" sub="QR verification scans and flags." testId="auditor-quick-scans" />
      </div>
    </div>
  );
}

export function TenantOpsCard() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/dashboard/role-summary").then((r) => setD(r.data)).catch(() => {}); }, []);
  if (!d) return null;
  return (
    <div className="bg-[#1A1C1E] text-white rounded-lg p-6" data-testid="tenant-ops-card">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-6">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-white/50">Platform · Super-admin</div>
            <div className="font-heading text-xl font-semibold mt-1">System overview</div>
          </div>
          <div className="flex gap-6">
            <div><div className="font-data text-2xl font-bold" data-testid="tenant-ops-tenants">{d.tenants}</div><div className="text-[11px] text-white/60">Tenants</div></div>
            <div><div className="font-data text-2xl font-bold" data-testid="tenant-ops-users">{d.platform_users}</div><div className="text-[11px] text-white/60">Users</div></div>
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <a href="/companies" className="inline-flex items-center gap-1.5 text-xs bg-white/10 hover:bg-white/20 px-3 py-2 rounded-lg" data-testid="tenant-ops-companies"><Building2 className="w-3.5 h-3.5" /> Tenants</a>
          <a href="/users" className="inline-flex items-center gap-1.5 text-xs bg-white/10 hover:bg-white/20 px-3 py-2 rounded-lg" data-testid="tenant-ops-users-link"><UserCog className="w-3.5 h-3.5" /> Users & Access</a>
          <a href="/settings" className="inline-flex items-center gap-1.5 text-xs bg-white/10 hover:bg-white/20 px-3 py-2 rounded-lg" data-testid="tenant-ops-settings"><GraduationCap className="w-3.5 h-3.5" /> Settings</a>
        </div>
      </div>
    </div>
  );
}
