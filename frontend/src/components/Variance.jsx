import { useEffect, useState } from "react";
import { X, TrendingUp, TrendingDown, AlertTriangle, ShieldCheck, Loader2, BarChart3 } from "lucide-react";
import api, { fmtSLE } from "../lib/api";
import { toast } from "sonner";

/** Variance analysis modal — opens on click of the Variance button on a payroll run row.
 *  Shows headline totals delta, per-ministry ranking, and anomaly flags. */
export function VarianceButton({ runId, period }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        data-testid={`variance-open-${runId}`}
        className="inline-flex items-center gap-1 text-xs bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#26547C] px-2.5 py-1.5 rounded"
      >
        <BarChart3 className="w-3.5 h-3.5" /> Variance
      </button>
      {open && <VarianceModal runId={runId} period={period} onClose={() => setOpen(false)} />}
    </>
  );
}

function VarianceModal({ runId, period, onClose }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get(`/payroll/runs/${runId}/variance`);
        setData(r.data);
      } catch (e) {
        toast.error(e?.response?.data?.detail || "Variance failed");
        onClose();
      } finally { setBusy(false); }
    })();
  }, [runId, onClose]);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" data-testid="variance-modal">
      <div className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="px-6 py-5 border-b border-[#E2DFD6] flex items-start justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Anti-fraud MoF review</div>
            <h2 className="font-heading text-xl font-bold mt-0.5">Payroll variance · {period}</h2>
            {data?.prior_exists && <p className="text-xs text-[#525860] mt-1">Compared to prior period <span className="font-data font-medium">{data.prior_period}</span></p>}
            {data && !data.prior_exists && <p className="text-xs text-[#8B6A14] mt-1">No prior period run — this is a baseline; anomaly detection is limited.</p>}
          </div>
          <button onClick={onClose} className="text-[#525860]" data-testid="variance-close" aria-label="Close"><X className="w-4 h-4" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {busy && <div className="text-center py-10"><Loader2 className="w-6 h-6 animate-spin mx-auto text-[#133326]" /></div>}
          {data && (
            <>
              <HeadlineTotals totals={data.totals} />
              <AnomaliesList anomalies={data.anomalies} summary={data.anomaly_summary} />
              {data.by_ministry.length > 0 && <MinistryTable rows={data.by_ministry} />}
            </>
          )}
        </div>

        <div className="border-t border-[#E2DFD6] px-6 py-4 flex justify-end">
          <button onClick={onClose} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]">Close</button>
        </div>
      </div>
    </div>
  );
}

function HeadlineTotals({ totals }) {
  const cur = totals.current, delta = totals.delta, pct = totals.delta_pct;
  const cells = [
    { label: "Employees", value: cur.headcount, deltaAbs: delta.headcount, deltaPct: pct.headcount, isMoney: false },
    { label: "Gross", value: cur.gross, deltaAbs: delta.gross, deltaPct: pct.gross, isMoney: true },
    { label: "PAYE", value: cur.paye, deltaAbs: delta.paye, deltaPct: pct.paye, isMoney: true },
    { label: "Net", value: cur.net, deltaAbs: delta.net, deltaPct: pct.net, isMoney: true },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="variance-headline-totals">
      {cells.map((c) => <MetricCell key={c.label} {...c} />)}
    </div>
  );
}

function MetricCell({ label, value, deltaAbs, deltaPct, isMoney }) {
  const positive = (deltaAbs ?? 0) > 0;
  const negative = (deltaAbs ?? 0) < 0;
  const arrow = positive ? TrendingUp : (negative ? TrendingDown : null);
  const Arrow = arrow;
  const color = positive ? "text-[#B84F2F]" : negative ? "text-[#2D7A5D]" : "text-[#525860]";
  return (
    <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-3">
      <div className="text-[10px] uppercase tracking-wider text-[#525860]">{label}</div>
      <div className="font-heading text-2xl font-bold mt-1 font-data">{isMoney ? fmtSLE(value) : value}</div>
      <div className={`text-xs mt-1 font-data flex items-center gap-1 ${color}`}>
        {Arrow && <Arrow className="w-3.5 h-3.5" />}
        {deltaAbs > 0 && "+"}{isMoney ? fmtSLE(deltaAbs) : deltaAbs}
        {deltaPct !== null && deltaPct !== undefined && (
          <span className="opacity-70">({deltaPct > 0 && "+"}{deltaPct}%)</span>
        )}
      </div>
    </div>
  );
}

function AnomaliesList({ anomalies, summary }) {
  if (!anomalies || anomalies.length === 0) {
    return (
      <div className="bg-[#E6F4EC] border border-[#C9E2D2] rounded-md px-4 py-3 flex items-center gap-2" data-testid="variance-no-anomalies">
        <ShieldCheck className="w-4 h-4 text-[#2D7A5D]" />
        <span className="text-sm text-[#2D7A5D]">No anomalies detected — variance falls within normal thresholds.</span>
      </div>
    );
  }
  return (
    <div className="space-y-2" data-testid="variance-anomalies">
      <div className="flex items-center gap-2 text-sm">
        <AlertTriangle className="w-4 h-4 text-[#8B6A14]" />
        <span className="font-semibold text-[#8B6A14]">
          {summary.count} anomal{summary.count === 1 ? "y" : "ies"} detected
        </span>
        <span className="text-xs text-[#525860]">
          ({summary.high} high · {summary.warn} warn)
        </span>
      </div>
      <ul className="space-y-1.5">
        {anomalies.map((a, i) => (
          <li
            key={`${a.kind}-${a.employee_id || a.label || ""}-${i}`}
            data-testid={`variance-anomaly-${a.kind}-${i}`}
            className={`text-xs rounded-md border px-3 py-2.5 ${
              a.severity === "high"
                ? "bg-[#FBEAEA] border-[#E9C2C2] text-[#8C2F2F]"
                : "bg-[#FBF1DE] border-[#E8D5A2] text-[#8B6A14]"
            }`}
          >
            <div className="font-semibold">{a.subject}</div>
            <div className="mt-0.5">{a.message}</div>
            {(a.before !== undefined || a.after !== undefined) && (
              <div className="mt-0.5 font-data opacity-80">
                {typeof a.before === "number" && !isNaN(a.before) ? fmtSLE(a.before) : a.before}
                {" → "}
                {typeof a.after === "number" && !isNaN(a.after) ? fmtSLE(a.after) : a.after}
                {a.delta_pct !== null && a.delta_pct !== undefined && (
                  <span className="ml-2">({a.delta_pct > 0 && "+"}{a.delta_pct}%)</span>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function MinistryTable({ rows }) {
  return (
    <div className="border border-[#E2DFD6] rounded-md overflow-hidden" data-testid="variance-ministry-table">
      <table className="w-full text-sm">
        <thead className="bg-[#F7F6F2]">
          <tr>{["Ministry", "Prior", "Current", "Δ Gross", "Δ %"].map((h) => (
            <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-3 font-medium">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const dp = r.delta_gross_pct;
            const flag = dp !== null && Math.abs(dp) >= 15;
            return (
              <tr key={r.ministry} className="border-t border-[#F1EEE6]">
                <td className="px-3 py-2 truncate max-w-[220px]" title={r.ministry}>{r.ministry}</td>
                <td className="px-3 py-2 font-data text-[13px]">{r.headcount_prev} · {fmtSLE(r.gross_prev)}</td>
                <td className="px-3 py-2 font-data text-[13px]">{r.headcount} · {fmtSLE(r.gross)}</td>
                <td className={`px-3 py-2 font-data ${r.delta_gross > 0 ? "text-[#B84F2F]" : r.delta_gross < 0 ? "text-[#2D7A5D]" : ""}`}>
                  {r.delta_gross > 0 && "+"}{fmtSLE(r.delta_gross)}
                </td>
                <td className={`px-3 py-2 font-data ${flag ? "text-[#8C2F2F] font-semibold" : ""}`}>
                  {dp === null ? "—" : (dp > 0 ? "+" : "") + dp + "%"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
