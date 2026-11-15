import { useEffect, useState } from "react";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Download, UserMinus } from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, Legend,
} from "recharts";
import ChartShell from "../components/ChartShell";
import { TOOLTIP_STYLE } from "../lib/chartStyles";

const PIE_COLORS = ["#0A4A1E", "#26547C", "#D1603D", "#8B6A14", "#17A035", "#2A5C9C"];
const LEGEND_STYLE = { fontSize: 12 };

export default function Analytics() {
  const { user } = useAuth();
  const showLeavers = ["hr", "admin", "superadmin"].includes(user?.role);
  const [trend, setTrend] = useState([]);
  const [usage, setUsage] = useState({ by_department: [], by_type: [] });
  const [earners, setEarners] = useState([]);
  const [audit, setAudit] = useState({ by_day: [], by_action: [] });

  useEffect(() => {
    Promise.all([
      api.get("/analytics/payroll-trend"),
      api.get("/analytics/leave-usage"),
      api.get("/analytics/top-earners"),
      api.get("/analytics/audit-activity"),
    ]).then(([t, u, e, a]) => {
      setTrend(t.data); setUsage(u.data); setEarners(e.data); setAudit(a.data);
    });
  }, []);

  return (
    <div className="space-y-6" data-testid="analytics-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Analytics & Reporting</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Analytics</h1>
        <p className="text-[#525860] text-sm mt-1">Deep cuts across payroll trend, leave usage, top earners, and audit activity.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Multi-line</div>
          <h3 className="font-heading text-lg font-semibold mb-4">Payroll components over time</h3>
          <ChartShell height={280}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} debounce={50}>
              <LineChart data={trend}>
                <CartesianGrid stroke="#EBE8E0" vertical={false} />
                <XAxis dataKey="period" stroke="#686D76" fontSize={11} />
                <YAxis stroke="#686D76" fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => fmtSLE(v)} />
                <Legend wrapperStyle={LEGEND_STYLE} />
                <Line type="monotone" dataKey="gross" stroke="#26547C" strokeWidth={2} dot={false} name="Gross" />
                <Line type="monotone" dataKey="net" stroke="#0A4A1E" strokeWidth={2} dot={false} name="Net" />
                <Line type="monotone" dataKey="paye" stroke="#D1603D" strokeWidth={2} dot={false} name="PAYE" />
                <Line type="monotone" dataKey="nassit" stroke="#8B6A14" strokeWidth={2} dot={false} name="NASSIT" />
              </LineChart>
            </ResponsiveContainer>
          </ChartShell>
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Leave</div>
          <h3 className="font-heading text-lg font-semibold mb-4">Leave days approved by department</h3>
          <ChartShell height={280}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} debounce={50}>
              <BarChart data={usage.by_department}>
                <CartesianGrid stroke="#EBE8E0" vertical={false} />
                <XAxis dataKey="name" stroke="#686D76" fontSize={11} />
                <YAxis stroke="#686D76" fontSize={11} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="days" fill="#D1603D" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartShell>
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Distribution</div>
          <h3 className="font-heading text-lg font-semibold mb-4">Leave by type</h3>
          <ChartShell height={280}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} debounce={50}>
              <PieChart>
                <Pie data={usage.by_type} dataKey="days" nameKey="type" cx="50%" cy="50%" outerRadius={90} label={(e) => `${e.type} (${e.days}d)`}>
                  {usage.by_type.map((entry, i) => <Cell key={entry.type} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
          </ChartShell>
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Activity</div>
          <h3 className="font-heading text-lg font-semibold mb-4">Audit events — last 30 days</h3>
          <ChartShell height={280}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} debounce={50}>
              <AreaChart data={audit.by_day}>
                <defs>
                  <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#26547C" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#26547C" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#EBE8E0" vertical={false} />
                <XAxis dataKey="date" stroke="#686D76" fontSize={10} />
                <YAxis stroke="#686D76" fontSize={11} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Area type="monotone" dataKey="count" stroke="#26547C" strokeWidth={2} fill="url(#g2)" />
              </AreaChart>
            </ResponsiveContainer>
          </ChartShell>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-[#E2DFD6]">
            <h3 className="font-heading text-lg font-semibold">Top earners</h3>
            <p className="text-xs text-[#686D76] mt-0.5">By gross monthly compensation</p>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[#F7F6F2]">
              <tr>{["Rank", "Employee", "Department", "Gross"].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {earners.map((e, i) => (
                <tr key={e.id} className="border-t border-[#E2DFD6]">
                  <td className="py-3 px-4 font-data text-[#686D76]">#{i + 1}</td>
                  <td className="py-3 px-4 font-medium">{e.name}<div className="text-xs text-[#686D76]">{e.job_title}</div></td>
                  <td className="py-3 px-4 text-[#525860]">{e.department}</td>
                  <td className="py-3 px-4 font-data font-semibold">{fmtSLE(e.gross)}</td>
                </tr>
              ))}
              {!earners.length && <tr><td colSpan={4} className="py-10 text-center text-sm text-[#686D76]">No data.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-[#E2DFD6]">
            <h3 className="font-heading text-lg font-semibold">Top audit actions</h3>
            <p className="text-xs text-[#686D76] mt-0.5">Last 30 days</p>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[#F7F6F2]">
              <tr>{["Action", "Count"].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {audit.by_action.map((a) => (
                <tr key={a.action} className="border-t border-[#E2DFD6]">
                  <td className="py-3 px-4">{a.action.replace(/_/g, " ")}</td>
                  <td className="py-3 px-4 font-data font-semibold">{a.count}</td>
                </tr>
              ))}
              {!audit.by_action.length && <tr><td colSpan={2} className="py-10 text-center text-sm text-[#686D76]">No audit data.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {showLeavers && <LeaversReport />}
    </div>
  );
}

const REASON_LABEL = {
  resignation: "Resignation", retirement: "Retirement", redundancy: "Redundancy",
  contract_end: "Contract End", dismissal: "Dismissal", other: "Other",
};

function LeaversReport() {
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/offboarding/report", { params: { month } })
      .then((r) => setData(r.data)).catch(() => setData(null));
  }, [month]);

  const exportCsv = async () => {
    const r = await api.get("/offboarding/report.csv", { params: { month }, responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = `leavers-${month}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="leavers-report-section">
      <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-end justify-between flex-wrap gap-3">
        <div>
          <h3 className="font-heading text-lg font-semibold inline-flex items-center gap-2">
            <UserMinus className="w-5 h-5 text-[#B03A2E]" strokeWidth={1.5} /> Leavers report
          </h3>
          <p className="text-xs text-[#686D76] mt-0.5">
            Employees whose offboarding completed in the selected month{data ? ` — ${data.count} leaver${data.count === 1 ? "" : "s"}` : ""}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)}
            className="border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data"
            data-testid="leavers-month-input" />
          <button onClick={exportCsv} data-testid="leavers-export-csv"
            className="inline-flex items-center gap-1.5 text-xs border border-[#26547C] text-[#26547C] hover:bg-[#E9F2FB] px-3 py-2 rounded-md">
            <Download className="w-3.5 h-3.5" /> Export CSV
          </button>
        </div>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-[#F7F6F2]">
          <tr>{["Name", "Role", "Department", "Leaving date", "Leaving reason"].map((h) => (
            <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {(data?.rows || []).map((r) => (
            <tr key={r.employee_id} className="border-t border-[#E2DFD6]" data-testid={`leavers-row-${r.employee_id}`}>
              <td className="py-3 px-4 font-medium">{r.name}</td>
              <td className="py-3 px-4">{r.job_title || "—"}</td>
              <td className="py-3 px-4">{r.department || "—"}</td>
              <td className="py-3 px-4 font-data">{r.leaving_date}</td>
              <td className="py-3 px-4">{REASON_LABEL[r.leaving_reason] || (r.leaving_reason || "Not recorded")}</td>
            </tr>
          ))}
          {!(data?.rows || []).length && (
            <tr><td colSpan={5} className="py-10 text-center text-sm text-[#686D76]" data-testid="leavers-empty">
              No leavers in {month}.
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
