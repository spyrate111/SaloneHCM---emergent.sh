import { useEffect, useState } from "react";
import api, { fmtSLE } from "../lib/api";
import { Download, ShieldCheck } from "lucide-react";

export default function Compliance() {
  const [summary, setSummary] = useState(null);
  const [runs, setRuns] = useState([]);

  useEffect(() => {
    api.get("/compliance/summary").then((r) => setSummary(r.data));
    api.get("/payroll/runs").then((r) => setRuns(r.data));
  }, []);

  const downloadCsv = async (rid, period) => {
    const { data } = await api.get(`/compliance/nra-export/${rid}`);
    const headers = ["employee", "gross_sle", "paye_sle", "nassit_employee_sle", "nassit_employer_sle", "net_sle"];
    const csv = [headers.join(","), ...data.rows.map((r) => headers.map((h) => r[h]).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `NRA-${period}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  if (!summary) return <div className="text-sm text-[#525860]">Loading…</div>;

  return (
    <div className="space-y-6" data-testid="compliance-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Compliance & Tax</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">NRA & NASSIT</h1>
        <p className="text-[#525860] text-sm mt-1 max-w-2xl">Sierra Leone PAYE bands and social security contributions, ready for filing.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-[#133326] text-white rounded-lg p-6">
          <ShieldCheck className="w-6 h-6 mb-3" strokeWidth={1.5} />
          <div className="text-[10px] uppercase tracking-[0.16em] text-white/60">Year-to-date</div>
          <div className="font-heading text-2xl font-bold mt-1 font-data">{fmtSLE(summary.ytd_paye_sle)}</div>
          <div className="text-sm text-white/70 mt-1">PAYE remitted</div>
        </div>
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Year-to-date</div>
          <div className="font-heading text-2xl font-bold mt-1 font-data">{fmtSLE(summary.ytd_nassit_sle)}</div>
          <div className="text-sm text-[#686D76] mt-1">NASSIT (employee + employer)</div>
        </div>
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Next deadline</div>
          <div className="font-heading text-base font-semibold mt-1">{summary.next_filing}</div>
          <div className="text-xs text-[#686D76] mt-1">{summary.runs_count} run(s) on record</div>
        </div>
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Sierra Leone PAYE bands (monthly, SLE)</div>
        <h3 className="font-heading text-lg font-semibold mt-1 mb-4">Tax tables</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm font-data">
          {summary.regs.paye_bands.map(([upper, rate], i) => (
            <div key={`band-${upper}-${rate}`} className="border border-[#E2DFD6] rounded-md p-3">
              <div className="text-[10px] uppercase tracking-wider text-[#525860]">Band {i + 1}</div>
              <div className="font-medium">Up to {fmtSLE(upper)}</div>
              <div className="text-[#26547C]">{(rate * 100).toFixed(0)}% PAYE</div>
            </div>
          ))}
          <div className="border border-[#E2DFD6] rounded-md p-3 bg-[#FBF1DE]">
            <div className="text-[10px] uppercase tracking-wider text-[#525860]">Top band</div>
            <div className="font-medium">Above SLE 7,500.00</div>
            <div className="text-[#8B6A14]">35% PAYE</div>
          </div>
        </div>
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-[#E2DFD6]">
          <h3 className="font-heading text-lg font-semibold">Filing-ready exports</h3>
          <p className="text-xs text-[#686D76] mt-0.5">Download per-period CSV for NRA submission.</p>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Period", "Employees", "PAYE", "NASSIT", ""].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} id={r.id} className="border-t border-[#E2DFD6]">
                <td className="py-3 px-4 font-medium">{r.period}</td>
                <td className="py-3 px-4 font-data">{r.totals.employee_count}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(r.totals.paye)}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(r.totals.nassit_employee + r.totals.nassit_employer)}</td>
                <td className="py-3 px-4 text-right">
                  <button data-testid={`export-${r.id}`} onClick={() => downloadCsv(r.id, r.period)} className="inline-flex items-center gap-1.5 text-xs bg-[#26547C] hover:bg-[#1D4363] text-white px-3 py-1.5 rounded">
                    <Download className="w-3.5 h-3.5" /> Export CSV
                  </button>
                </td>
              </tr>
            ))}
            {!runs.length && <tr><td colSpan={5} className="py-10 text-center text-sm text-[#686D76]">No payroll runs yet — generate one to enable exports.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
