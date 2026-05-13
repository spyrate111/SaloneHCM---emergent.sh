import { useEffect, useState } from "react";
import api, { fmtSLE } from "../lib/api";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, Legend,
} from "recharts";
import { TOOLTIP_STYLE } from "../lib/chartStyles";

const PIE_COLORS = ["#133326", "#26547C", "#D1603D", "#8B6A14", "#2D7A5D", "#9A2A52"];
const LEGEND_STYLE = { fontSize: 12 };

export default function Analytics() {
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
          <div style={{ width: "100%", height: 280 }}>
            <ResponsiveContainer width="99%" height="100%" minWidth={0} minHeight={0} debounce={50}>
              <LineChart data={trend}>
                <CartesianGrid stroke="#EBE8E0" vertical={false} />
                <XAxis dataKey="period" stroke="#686D76" fontSize={11} />
                <YAxis stroke="#686D76" fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => fmtSLE(v)} />
                <Legend wrapperStyle={LEGEND_STYLE} />
                <Line type="monotone" dataKey="gross" stroke="#26547C" strokeWidth={2} dot={false} name="Gross" />
                <Line type="monotone" dataKey="net" stroke="#133326" strokeWidth={2} dot={false} name="Net" />
                <Line type="monotone" dataKey="paye" stroke="#D1603D" strokeWidth={2} dot={false} name="PAYE" />
                <Line type="monotone" dataKey="nassit" stroke="#8B6A14" strokeWidth={2} dot={false} name="NASSIT" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Leave</div>
          <h3 className="font-heading text-lg font-semibold mb-4">Leave days approved by department</h3>
          <div style={{ width: "100%", height: 280 }}>
            <ResponsiveContainer width="99%" height="100%" minWidth={0} minHeight={0} debounce={50}>
              <BarChart data={usage.by_department}>
                <CartesianGrid stroke="#EBE8E0" vertical={false} />
                <XAxis dataKey="name" stroke="#686D76" fontSize={11} />
                <YAxis stroke="#686D76" fontSize={11} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="days" fill="#D1603D" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Distribution</div>
          <h3 className="font-heading text-lg font-semibold mb-4">Leave by type</h3>
          <div style={{ width: "100%", height: 280 }}>
            <ResponsiveContainer width="99%" height="100%" minWidth={0} minHeight={0} debounce={50}>
              <PieChart>
                <Pie data={usage.by_type} dataKey="days" nameKey="type" cx="50%" cy="50%" outerRadius={90} label={(e) => `${e.type} (${e.days}d)`}>
                  {usage.by_type.map((entry, i) => <Cell key={entry.type} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Activity</div>
          <h3 className="font-heading text-lg font-semibold mb-4">Audit events — last 30 days</h3>
          <div style={{ width: "100%", height: 280 }}>
            <ResponsiveContainer width="99%" height="100%" minWidth={0} minHeight={0} debounce={50}>
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
          </div>
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
    </div>
  );
}
