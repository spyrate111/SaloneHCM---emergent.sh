import { X } from "lucide-react";
import { fmtSLE } from "../../lib/api";

const HEADERS = ["#", "Scenario", "Status", "Affected", "Δ Employer/mo", "Annualized", "Δ PAYE", "Δ NASSIT", "Δ Net"];

export default function ComparisonPanel({ comparison, onClose }) {
  const cheapest = comparison.rows.find((r) => r.scenario.id === comparison.cheapest_id);
  const targeted = comparison.rows.find((r) => r.scenario.id === comparison.most_targeted_id);
  return (
    <div className="bg-white border-2 border-[#26547C] rounded-lg p-6" data-testid="comparison-panel">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#26547C]">Scenario comparison</div>
          <h3 className="font-heading text-xl font-semibold mt-1">Ranked by annualized employer cost (cheapest first)</h3>
          <p className="text-xs text-[#686D76] mt-1">Each scenario is freshly re-simulated against the latest employee data.</p>
        </div>
        <button onClick={onClose} className="inline-flex items-center gap-1.5 text-sm border border-[#E2DFD6] hover:bg-[#F7F6F2] px-3 py-2 rounded-md text-[#525860]"><X className="w-3.5 h-3.5" /> Close</button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
        <Callout color="bg-[#E4F7E7] border-[#90D8A0] text-[#17A035]" label="💰 Cheapest" title={cheapest?.scenario.title} />
        <Callout color="bg-[#FBE9DF] border-[#E8B89C] text-[#8B3A1C]" label="🎯 Most targeted" title={targeted?.scenario.title} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{HEADERS.map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {comparison.rows.map((r, i) => (
              <ComparisonRow
                key={r.scenario.id} index={i} r={r}
                isWinner={r.scenario.id === comparison.cheapest_id}
                isTargeted={r.scenario.id === comparison.most_targeted_id}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ComparisonRow({ index, r, isWinner, isTargeted }) {
  const positive = r.totals.delta_employer >= 0;
  const deltaClass = positive ? "text-[#B84F2F]" : "text-[#17A035]";
  const sign = positive ? "+" : "";
  return (
    <tr className={`border-t border-[#E2DFD6] ${isWinner ? "bg-[#F2FBF3]" : ""}`}>
      <td className="py-3 px-4 font-data text-[#686D76]">#{index + 1}</td>
      <td className="py-3 px-4">
        <div className="font-medium flex items-center gap-1.5">
          {r.scenario.title}
          {isWinner && <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#17A035] text-white">Cheapest</span>}
          {isTargeted && !isWinner && <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#D1603D] text-white">Targeted</span>}
        </div>
        <div className="text-xs text-[#686D76]">{r.scenario.rules_count} rule{r.scenario.rules_count !== 1 ? "s" : ""}</div>
      </td>
      <td className="py-3 px-4 text-[10px] uppercase tracking-wider text-[#686D76]">{r.scenario.approval_status}</td>
      <td className="py-3 px-4 font-data">{r.totals.affected}</td>
      <td className={`py-3 px-4 font-data font-semibold ${deltaClass}`}>{sign}{fmtSLE(r.totals.delta_employer)}</td>
      <td className={`py-3 px-4 font-data font-semibold ${deltaClass}`}>{sign}{fmtSLE(r.totals.annualized)}</td>
      <td className="py-3 px-4 font-data text-xs">{fmtSLE(r.totals.paye_delta)}</td>
      <td className="py-3 px-4 font-data text-xs">{fmtSLE(r.totals.nassit_delta)}</td>
      <td className="py-3 px-4 font-data text-xs">{fmtSLE(r.totals.net_delta)}</td>
    </tr>
  );
}

function Callout({ color, label, title }) {
  return (
    <div className={`border rounded-md p-3 ${color}`}>
      <div className="text-[10px] uppercase tracking-wider">{label}</div>
      <div className="font-heading text-base font-semibold mt-0.5 text-[#1A1C1E]">{title}</div>
    </div>
  );
}
