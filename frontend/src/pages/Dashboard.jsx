import { useEffect, useState } from "react";
import api, { fmtSLE, fmtNum } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Users, Wallet, Receipt, CalendarClock, ArrowUpRight } from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar,
} from "recharts";

const KPI = ({ label, value, sub, icon: Icon, accent }) => (
  <div className="bg-white border border-[#E2DFD6] rounded-lg p-5 hover:shadow-sm transition" data-testid={`kpi-${label.toLowerCase().replace(/\s/g, "-")}`}>
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

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);

  useEffect(() => { api.get("/dashboard/overview").then((r) => setData(r.data)); }, []);

  if (!data) return <div className="text-[#525860] text-sm">Loading dashboard…</div>;

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Overview</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-[#1A1C1E] mt-1">
          Good day, {user?.name?.split(" ")[0] || "there"}.
        </h1>
        <p className="text-[#525860] mt-2 text-sm max-w-2xl">
          Here's what's happening across your organization today — payroll, headcount, compliance, and pending approvals.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <KPI label="Headcount" value={fmtNum(data.headcount)} sub={`${data.total_employees} total records`} icon={Users} accent="bg-[#133326]" />
        <KPI label="Monthly Payroll" value={fmtSLE(data.monthly_payroll_sle)} sub="Gross run estimate" icon={Wallet} accent="bg-[#26547C]" />
        <KPI label="Pending Leaves" value={fmtNum(data.pending_leaves)} sub="Awaiting your approval" icon={CalendarClock} accent="bg-[#D1603D]" />
        <KPI label="Last Run Net" value={fmtSLE(data.last_run?.totals?.net || 0)} sub={data.last_run?.period || "No runs yet"} icon={Receipt} accent="bg-[#2D7A5D]" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 bg-white border border-[#E2DFD6] rounded-lg p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Payroll trend</div>
              <h3 className="font-heading text-lg font-semibold text-[#1A1C1E]">Net payroll cost across periods</h3>
            </div>
          </div>
          <div className="h-64 w-full">
            {data.runs_history?.length ? (
              <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={200}>
                <AreaChart data={data.runs_history}>
                  <defs>
                    <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#133326" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#133326" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#EBE8E0" vertical={false} />
                  <XAxis dataKey="period" stroke="#686D76" fontSize={11} />
                  <YAxis stroke="#686D76" fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip contentStyle={{ background: "#fff", border: "1px solid #E2DFD6", borderRadius: 8, fontSize: 12 }} formatter={(v) => fmtSLE(v)} />
                  <Area type="monotone" dataKey="net" stroke="#133326" strokeWidth={2} fill="url(#g1)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full grid place-items-center text-sm text-[#686D76]">Run your first payroll to see trends.</div>
            )}
          </div>
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860] mb-1">Headcount by department</div>
          <h3 className="font-heading text-lg font-semibold mb-4">Departments</h3>
          <div style={{ width: "100%", height: 256 }}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={200}>
              <BarChart data={data.departments} layout="vertical" margin={{ left: 0 }}>
                <CartesianGrid stroke="#EBE8E0" horizontal={false} />
                <XAxis type="number" stroke="#686D76" fontSize={11} />
                <YAxis type="category" dataKey="name" stroke="#686D76" fontSize={11} width={110} />
                <Tooltip contentStyle={{ background: "#fff", border: "1px solid #E2DFD6", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="count" fill="#26547C" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <a href="/payroll" className="group bg-[#133326] text-white rounded-lg p-6 hover:bg-[#0F281E] transition" data-testid="quick-payroll">
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/60">Quick action</div>
          <div className="font-heading text-xl font-semibold mt-2">Run this month's payroll</div>
          <div className="text-white/70 text-sm mt-1">Auto-calculates PAYE & NASSIT for active employees.</div>
          <div className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[#D1603D]">
            Open Payroll Engine <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </div>
        </a>
        <a href="/compliance" className="group bg-white border border-[#E2DFD6] rounded-lg p-6 hover:shadow-md transition" data-testid="quick-compliance">
          <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Compliance</div>
          <div className="font-heading text-xl font-semibold mt-2 text-[#1A1C1E]">NRA & NASSIT exports</div>
          <div className="text-[#686D76] text-sm mt-1">Generate filing-ready reports for the National Revenue Authority.</div>
          <div className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[#26547C]">
            View reports <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </div>
        </a>
        <a href="/assistant" className="group bg-[#D1603D] text-white rounded-lg p-6 hover:bg-[#B84F2F] transition" data-testid="quick-assistant">
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/70">AI</div>
          <div className="font-heading text-xl font-semibold mt-2">Ask the SaloneHCM Assistant</div>
          <div className="text-white/80 text-sm mt-1">PAYE bands, leave entitlements, payroll questions — answered.</div>
          <div className="mt-5 inline-flex items-center gap-2 text-sm font-medium">
            Open chat <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </div>
        </a>
      </div>
    </div>
  );
}
