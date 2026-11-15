import { TrendingUp, TrendingDown } from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";
import ChartShell from "../ChartShell";
import { fmtSLE } from "../../lib/api";
import { TOOLTIP_STYLE } from "../../lib/chartStyles";

const LEGEND_STYLE = { fontSize: 12 };
const BAR_RADIUS = [4, 4, 0, 0];
const CHART_BOX = { width: "100%", height: 280 };

const isPositive = (n) => (n ?? 0) >= 0;

export default function SimulationResults({ result }) {
  const positiveCost = isPositive(result.delta.employer_total_cost);
  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5" data-testid="sim-results">
        <Card label="Current monthly" sub={`${result.current.employee_count} active employees`} value={fmtSLE(result.current.employer_total_cost)} accent="bg-[#26547C]" />
        <Card label="Projected monthly" sub={`${result.affected_employees_count} affected`} value={fmtSLE(result.projected.employer_total_cost)} accent="bg-[#0A4A1E]" />
        <Card
          label="Δ Employer cost"
          sub={`Annualized: ${fmtSLE(result.annualized_delta_employer_cost)}`}
          value={fmtSLE(result.delta.employer_total_cost)}
          accent={positiveCost ? "bg-[#D1603D]" : "bg-[#17A035]"}
          icon={positiveCost ? TrendingUp : TrendingDown}
        />
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
        <h3 className="font-heading text-lg font-semibold mb-4">Department impact</h3>
        <ChartShell height={288}>
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} debounce={50}>
            <BarChart data={result.by_department}>
              <CartesianGrid stroke="#EBE8E0" vertical={false} />
              <XAxis dataKey="name" stroke="#686D76" fontSize={11} />
              <YAxis stroke="#686D76" fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => fmtSLE(v)} />
              <Legend wrapperStyle={LEGEND_STYLE} />
              <Bar dataKey="current" fill="#26547C" radius={BAR_RADIUS} name="Current" />
              <Bar dataKey="projected" fill="#D1603D" radius={BAR_RADIUS} name="Projected" />
            </BarChart>
          </ResponsiveContainer>
        </ChartShell>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
        <Mini label="PAYE Δ" value={result.delta.paye} />
        <Mini label="NASSIT employee Δ" value={result.delta.nassit_employee} />
        <Mini label="NASSIT employer Δ" value={result.delta.nassit_employer} />
        <Mini label="Net pay Δ" value={result.delta.net} />
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-[#E2DFD6]">
          <h3 className="font-heading text-lg font-semibold">Affected employees ({result.employees.length})</h3>
          <p className="text-xs text-[#686D76] mt-0.5">Sorted by largest gross increase</p>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Employee", "Department", "Current gross", "Projected gross", "Δ Gross", "Δ Net"].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {result.employees.map((e) => (
              <EmployeeRow key={e.id} e={e} />
            ))}
            {!result.employees.length && <tr><td colSpan={6} className="py-10 text-center text-sm text-[#686D76]">No employees affected by these rules.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}

function EmployeeRow({ e }) {
  const grossPositive = isPositive(e.delta_gross);
  const netPositive = isPositive(e.delta_net);
  return (
    <tr className="border-t border-[#E2DFD6]">
      <td className="py-3 px-4 font-medium">{e.name}<div className="text-xs text-[#686D76]">{e.job_title}</div></td>
      <td className="py-3 px-4 text-[#525860]">{e.department}</td>
      <td className="py-3 px-4 font-data">{fmtSLE(e.current_gross)}</td>
      <td className="py-3 px-4 font-data">{fmtSLE(e.projected_gross)}</td>
      <td className={`py-3 px-4 font-data font-semibold ${grossPositive ? "text-[#17A035]" : "text-[#3A7CB8]"}`}>{grossPositive ? "+" : ""}{fmtSLE(e.delta_gross)}</td>
      <td className={`py-3 px-4 font-data font-semibold ${netPositive ? "text-[#17A035]" : "text-[#3A7CB8]"}`}>{netPositive ? "+" : ""}{fmtSLE(e.delta_net)}</td>
    </tr>
  );
}

function Card({ label, sub, value, accent, icon: Icon }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{label}</div>
          <div className="font-heading text-2xl font-bold mt-2 font-data">{value}</div>
          {sub && <div className="text-xs text-[#686D76] mt-1">{sub}</div>}
        </div>
        <div className={`w-9 h-9 rounded-md ${accent} grid place-items-center`}>
          {Icon ? <Icon className="w-[18px] h-[18px] text-white" strokeWidth={1.5} /> : <span className="text-white text-xs font-bold">SLE</span>}
        </div>
      </div>
    </div>
  );
}

function Mini({ label, value }) {
  const positive = isPositive(value);
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-md p-3">
      <div className="text-[10px] uppercase tracking-wider text-[#525860]">{label}</div>
      <div className={`font-data font-semibold mt-1 ${positive ? "text-[#17A035]" : "text-[#3A7CB8]"}`}>
        {positive ? "+" : ""}{fmtSLE(value)}
      </div>
    </div>
  );
}
