import { useEffect, useState } from "react";
import api, { fmtSLE, fmtNum } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import RoleTour from "../components/RoleTourCard";
import { useFeatures } from "../lib/features";
import ComplianceScoreWidget from "../components/ComplianceScoreWidget";
import DigestPreviewCard from "../components/DigestPreviewCard";
import AnnouncementsCard from "../components/AnnouncementsCard";
import {
  Kpi, HrDashboard, PayrollDashboard, ManagerDashboard,
  EmployeeDashboard, AuditorDashboard, TenantOpsCard,
} from "../components/RoleDashboards";
import { Users, Wallet, Receipt, CalendarClock, ArrowUpRight } from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar,
} from "recharts";
import ChartShell from "../components/ChartShell";
import { TOOLTIP_STYLE } from "../lib/chartStyles";

const BAR_LEFT_MARGIN = { left: 0 };
const BAR_RADIUS = [0, 4, 4, 0];

export default function Dashboard() {
  const { user } = useAuth();
  const role = user?.role;
  let inner;
  if (role === "hr") inner = <HrDashboard user={user} />;
  else if (role === "payroll") inner = <PayrollDashboard user={user} />;
  else if (role === "manager") inner = <ManagerDashboard user={user} />;
  else if (role === "employee") inner = <EmployeeDashboard user={user} />;
  else if (role === "auditor") inner = <AuditorDashboard user={user} />;
  else inner = <AdminDashboard user={user} superadmin={role === "superadmin"} />;
  return (
    <div className="space-y-6">
      <AnnouncementsCard />
      {inner}
    </div>
  );
}

function AdminDashboard({ user, superadmin }) {
  const { isAdmin } = useFeatures();
  const [data, setData] = useState(null);

  useEffect(() => { api.get("/dashboard/overview").then((r) => setData(r.data)); }, []);

  if (!data) return <div className="text-[#525860] text-sm">Loading dashboard…</div>;

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">
          {superadmin ? "System Overview" : "Company Overview"}
        </div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-[#1A1C1E] mt-1">
          Good day, {user?.name?.split(" ")[0] || "there"}.
        </h1>
        <p className="text-[#525860] mt-2 text-sm max-w-2xl">
          Here&rsquo;s what&rsquo;s happening across your organization today &mdash; payroll, headcount, compliance, and pending approvals.
        </p>
      </div>

      {superadmin && <TenantOpsCard />}
      {isAdmin && <ComplianceScoreWidget />}
      {isAdmin && <DigestPreviewCard />}
      <RoleTour user={user} />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Kpi label="Headcount" value={fmtNum(data.headcount)} sub={`${data.total_employees} total records`} icon={Users} accent="bg-[#0A4A1E]" />
        <Kpi label="Monthly Payroll" value={fmtSLE(data.monthly_payroll_sle)} sub="Gross run estimate" icon={Wallet} accent="bg-[#26547C]" />
        <Kpi label="Pending Leaves" value={fmtNum(data.pending_leaves)} sub="Awaiting your approval" icon={CalendarClock} accent="bg-[#D1603D]" />
        <Kpi label="Last Run Net" value={fmtSLE(data.last_run?.totals?.net || 0)} sub={data.last_run?.period || "No runs yet"} icon={Receipt} accent="bg-[#17A035]" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
          <div className="flex items-center justify-between mb-5">
            <div>
              <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Payroll trend</div>
              <h3 className="font-heading text-lg font-semibold text-[#1A1C1E]">Net payroll cost across periods</h3>
            </div>
          </div>
          <ChartShell height={256}>
            {data.runs_history?.length ? (
              <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} debounce={50}>
                <AreaChart data={data.runs_history}>
                  <defs>
                    <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0A4A1E" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#0A4A1E" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#EBE8E0" vertical={false} />
                  <XAxis dataKey="period" stroke="#686D76" fontSize={11} />
                  <YAxis stroke="#686D76" fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => fmtSLE(v)} />
                  <Area type="monotone" dataKey="net" stroke="#0A4A1E" strokeWidth={2} fill="url(#g1)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full grid place-items-center text-sm text-[#686D76]">Run your first payroll to see trends.</div>
            )}
          </ChartShell>
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860] mb-1">Headcount by department</div>
          <h3 className="font-heading text-lg font-semibold mb-4">Departments</h3>
          <ChartShell height={256}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} debounce={50}>
              <BarChart data={data.departments} layout="vertical" margin={BAR_LEFT_MARGIN}>
                <CartesianGrid stroke="#EBE8E0" horizontal={false} />
                <XAxis type="number" stroke="#686D76" fontSize={11} />
                <YAxis type="category" dataKey="name" stroke="#686D76" fontSize={11} width={110} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="count" fill="#26547C" radius={BAR_RADIUS} />
              </BarChart>
            </ResponsiveContainer>
          </ChartShell>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <a href="/payroll" className="group bg-[#0A4A1E] text-white rounded-lg p-6 hover:bg-[#063514] transition" data-testid="quick-payroll">
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/60">Quick action</div>
          <div className="font-heading text-xl font-semibold mt-2">Run this month&rsquo;s payroll</div>
          <div className="text-white/70 text-sm mt-1">Auto-calculates PAYE & NASSIT for active employees.</div>
          <div className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[#D1603D]">
            Open Payroll Engine <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </div>
        </a>
        <a href="/employees" className="group bg-white border border-[#E2DFD6] rounded-lg p-6 hover:shadow-md transition" data-testid="quick-employees">
          <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">People</div>
          <div className="font-heading text-xl font-semibold mt-2 text-[#1A1C1E]">Employee management</div>
          <div className="text-[#686D76] text-sm mt-1">Records, onboarding, grades and documents.</div>
          <div className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[#26547C]">
            Open Employees <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </div>
        </a>
        <a href="/compliance" className="group bg-white border border-[#E2DFD6] rounded-lg p-6 hover:shadow-md transition" data-testid="quick-compliance">
          <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Compliance</div>
          <div className="font-heading text-xl font-semibold mt-2 text-[#1A1C1E]">NRA & NASSIT reports</div>
          <div className="text-[#686D76] text-sm mt-1">Generate filing-ready reports for the National Revenue Authority.</div>
          <div className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[#26547C]">
            View reports <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </div>
        </a>
      </div>
    </div>
  );
}
