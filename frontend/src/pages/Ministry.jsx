import { useEffect, useState } from "react";
import api, { fmtSLE } from "../lib/api";
import {
  Landmark, Users, Wallet, Receipt, ArrowDownToLine, AlertCircle, Crown,
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";
import { TOOLTIP_STYLE } from "../lib/chartStyles";

const LEGEND_STYLE = { fontSize: 12 };
const BAR_RADIUS = [4, 4, 0, 0];
const CHART_BOX = { width: "100%", height: 320 };

export default function Ministry() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/ministry/rollup").then((r) => setData(r.data));
  }, []);

  if (!data) return null;
  const { ministries, totals } = data;
  const chartData = ministries.map((m) => ({
    name: m.name.replace(/^Ministry of /, "MoF/"),
    Gross: m.monthly_payroll_gross,
    PAYE: m.monthly_paye,
    NASSIT: m.monthly_nassit,
  }));

  return (
    <div className="space-y-6" data-testid="ministry-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Gov tier · Ministry-level reporting</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1 flex items-center gap-2">
          Ministry rollup <Landmark className="w-6 h-6 text-[#26547C]" />
        </h1>
        <p className="text-[#525860] text-sm mt-1.5 max-w-3xl">
          Cross-ministry consolidation of headcount, gross payroll, PAYE remittance and NASSIT contributions — ready for the Auditor General and the Office of the President.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPI icon={Users} label="Total headcount" value={totals.headcount_active} sub={`across ${totals.ministries} ministries`} accent="bg-[#26547C]" />
        <KPI icon={Wallet} label="Monthly gross" value={fmtSLE(totals.monthly_payroll_gross)} accent="bg-[#133326]" />
        <KPI icon={Receipt} label="Monthly PAYE" value={fmtSLE(totals.monthly_paye)} sub="To NRA" accent="bg-[#D1603D]" />
        <KPI icon={ArrowDownToLine} label="Monthly NASSIT" value={fmtSLE(totals.monthly_nassit)} sub="Emp + Employer" accent="bg-[#2D7A5D]" />
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <h3 className="font-heading text-lg font-semibold mb-4">Gross payroll by ministry</h3>
        <div style={CHART_BOX}>
          <ResponsiveContainer width="99%" height="100%" minWidth={0} minHeight={0} debounce={50}>
            <BarChart data={chartData}>
              <CartesianGrid stroke="#EBE8E0" vertical={false} />
              <XAxis dataKey="name" stroke="#686D76" fontSize={11} interval={0} angle={-25} textAnchor="end" height={70} />
              <YAxis stroke="#686D76" fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => fmtSLE(v)} />
              <Legend wrapperStyle={LEGEND_STYLE} />
              <Bar dataKey="Gross" fill="#133326" radius={BAR_RADIUS} />
              <Bar dataKey="PAYE" fill="#D1603D" radius={BAR_RADIUS} />
              <Bar dataKey="NASSIT" fill="#26547C" radius={BAR_RADIUS} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center justify-between flex-wrap gap-2">
          <h3 className="font-heading text-lg font-semibold">Per-ministry breakdown</h3>
          {totals.leave_pending > 0 && (
            <div className="text-xs bg-[#FBF1DE] text-[#8B6A14] border border-[#E8D5A2] rounded-md px-3 py-1.5 inline-flex items-center gap-1.5">
              <AlertCircle className="w-3.5 h-3.5" />
              {totals.leave_pending} pending leave request{totals.leave_pending > 1 ? "s" : ""} across ministries
            </div>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F7F6F2]">
              <tr>{["Ministry", "Active", "Mgrs", "Avg basic", "Gross", "Net", "PAYE", "NASSIT", "Leave / 30d", "Pending"].map((h) => (
                <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {ministries.map((m) => (
                <tr key={m.name} className="border-t border-[#E2DFD6]">
                  <td className="py-3 px-4 font-medium flex items-center gap-2">
                    <Landmark className="w-4 h-4 text-[#26547C]" /> {m.name}
                  </td>
                  <td className="py-3 px-4 font-data">{m.headcount_active}/{m.headcount_total}</td>
                  <td className="py-3 px-4 font-data text-xs">
                    <span className="inline-flex items-center gap-1 text-[#8B6A14]"><Crown className="w-3 h-3" />{m.headcount_managers}</span>
                  </td>
                  <td className="py-3 px-4 font-data text-xs">{fmtSLE(m.avg_basic_salary)}</td>
                  <td className="py-3 px-4 font-data font-semibold">{fmtSLE(m.monthly_payroll_gross)}</td>
                  <td className="py-3 px-4 font-data">{fmtSLE(m.monthly_payroll_net)}</td>
                  <td className="py-3 px-4 font-data text-xs text-[#B84F2F]">{fmtSLE(m.monthly_paye)}</td>
                  <td className="py-3 px-4 font-data text-xs text-[#26547C]">{fmtSLE(m.monthly_nassit)}</td>
                  <td className="py-3 px-4 font-data text-xs">{m.leave_approved_30d}d</td>
                  <td className="py-3 px-4 font-data">{m.leave_pending > 0 ? <span className="text-[#B84F2F]">{m.leave_pending}</span> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function KPI({ icon: Icon, label, value, sub, accent }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-4 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{label}</div>
        <div className="font-heading text-xl font-bold mt-1 font-data truncate">{value}</div>
        {sub && <div className="text-[10px] text-[#686D76] mt-0.5">{sub}</div>}
      </div>
      <div className={`w-9 h-9 rounded-md ${accent} grid place-items-center shrink-0`}>
        <Icon className="w-[18px] h-[18px] text-white" strokeWidth={1.5} />
      </div>
    </div>
  );
}
