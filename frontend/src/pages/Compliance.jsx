import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { useFeatures } from "../lib/features";
import { toast } from "sonner";
import { Download, ShieldCheck, FileCheck, Receipt, AlertCircle } from "lucide-react";

export default function Compliance() {
  const { has } = useFeatures();
  const hasNraExport = has("nra_export");
  const [summary, setSummary] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(() => api.get("/compliance/summary").then((r) => setSummary(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const downloadBlob = async (url, filename) => {
    setBusy(filename);
    try {
      const resp = await api.get(url, { responseType: "blob" });
      const blobUrl = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = blobUrl; a.download = filename; a.click();
      URL.revokeObjectURL(blobUrl);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Download failed");
    } finally { setBusy(null); }
  };

  const downloadLegacy = async (rid, period) => {
    const { data } = await api.get(`/compliance/nra-export/${rid}`);
    const headers = ["employee", "gross_sle", "paye_sle", "nassit_employee_sle", "nassit_employer_sle", "net_sle"];
    const csv = [headers.join(","), ...data.rows.map((r) => headers.map((h) => r[h]).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `NRA-${period}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const markFiled = async (rid) => {
    if (!window.confirm("Mark this run as filed at NRA? This will record an audit-trail entry.")) return;
    try {
      const { data } = await api.post(`/compliance/file-nra/${rid}`);
      toast.success(`Filed — NRA reference ${data.nra_reference}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Mark filed failed");
    }
  };

  if (!summary) return <div className="text-sm text-[#525860]">Loading…</div>;
  const history = summary.history || [];

  return (
    <div className="space-y-6" data-testid="compliance-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Compliance & Tax</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">NRA & NASSIT</h1>
        <p className="text-[#525860] text-sm mt-1 max-w-2xl">Sierra Leone PAYE bands and social security contributions, ready for filing.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <KPI dark icon={ShieldCheck} label="YTD PAYE remitted" value={fmtSLE(summary.ytd_paye_sle)} />
        <KPI icon={Receipt} label="YTD NASSIT" value={fmtSLE(summary.ytd_nassit_sle)} sub="Employee + Employer" />
        <KPI icon={FileCheck} label="Returns filed" value={summary.filed_count || 0} sub={`of ${summary.runs_count} runs`} color="text-[#2D7A5D]" />
        <KPI icon={AlertCircle} label="Outstanding" value={(summary.outstanding || []).length} color={summary.outstanding?.length ? "text-[#B84F2F]" : "text-[#525860]"} sub={summary.next_filing} />
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
          <p className="text-xs text-[#686D76] mt-0.5">
            {hasNraExport
              ? "Download the NRA PAYE Return + NASSIT contribution schedule per period — formats the NRA & NASSIT portals accept directly."
              : "Download per-period CSV for NRA submission."}
          </p>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Period", "Employees", "PAYE", "NASSIT", "Status", ""].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {history.map((r) => (
              <tr key={r.run_id} id={r.run_id} className="border-t border-[#E2DFD6]">
                <td className="py-3 px-4 font-medium font-data">{r.period}</td>
                <td className="py-3 px-4 font-data">{r.employees}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(r.paye)}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(r.nassit_total)}</td>
                <td className="py-3 px-4">
                  {r.nra_filed
                    ? <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#E6F4EC] text-[#2D7A5D]" title={`Filed ${new Date(r.nra_filed_at).toLocaleDateString()} · ${r.nra_reference}`}>
                        <FileCheck className="w-3 h-3" /> Filed
                      </span>
                    : <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#FBF1DE] text-[#8B6A14]">
                        <AlertCircle className="w-3 h-3" /> Outstanding
                      </span>}
                </td>
                <td className="py-3 px-4 text-right">
                  <div className="inline-flex gap-1.5 flex-wrap justify-end">
                    {hasNraExport && (
                      <>
                        <button
                          data-testid={`export-nra-paye-${r.run_id}`}
                          disabled={busy === `NRA-PAYE-Return-${r.period}.csv`}
                          onClick={() => downloadBlob(`/compliance/nra-paye-return.csv/${r.run_id}`, `NRA-PAYE-Return-${r.period}.csv`)}
                          className="inline-flex items-center gap-1 text-xs bg-[#26547C] hover:bg-[#1D4363] text-white px-2.5 py-1.5 rounded"
                        >
                          <Download className="w-3.5 h-3.5" /> NRA PAYE
                        </button>
                        <button
                          data-testid={`export-nassit-${r.run_id}`}
                          disabled={busy === `NASSIT-Schedule-${r.period}.csv`}
                          onClick={() => downloadBlob(`/compliance/nassit-schedule.csv/${r.run_id}`, `NASSIT-Schedule-${r.period}.csv`)}
                          className="inline-flex items-center gap-1 text-xs bg-[#2D7A5D] hover:bg-[#256449] text-white px-2.5 py-1.5 rounded"
                        >
                          <Download className="w-3.5 h-3.5" /> NASSIT
                        </button>
                        {!r.nra_filed && (
                          <button
                            data-testid={`mark-filed-${r.run_id}`}
                            onClick={() => markFiled(r.run_id)}
                            className="inline-flex items-center gap-1 text-xs bg-white border border-[#2D7A5D] text-[#2D7A5D] hover:bg-[#E6F4EC] px-2.5 py-1.5 rounded"
                          >
                            <FileCheck className="w-3.5 h-3.5" /> Mark filed
                          </button>
                        )}
                      </>
                    )}
                    {!hasNraExport && (
                      <button data-testid={`export-${r.run_id}`} onClick={() => downloadLegacy(r.run_id, r.period)} className="inline-flex items-center gap-1.5 text-xs bg-[#26547C] hover:bg-[#1D4363] text-white px-3 py-1.5 rounded">
                        <Download className="w-3.5 h-3.5" /> Export CSV
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!history.length && <tr><td colSpan={6} className="py-10 text-center text-sm text-[#686D76]">No payroll runs yet — generate one to enable exports.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KPI({ icon: Icon, label, value, sub, dark, color }) {
  return (
    <div className={`${dark ? "bg-[#133326] text-white" : "bg-white border border-[#E2DFD6]"} rounded-lg p-4`}>
      <Icon className={`w-5 h-5 ${dark ? "text-white/80" : "text-[#525860]"} mb-2`} strokeWidth={1.5} />
      <div className={`text-[10px] uppercase tracking-[0.16em] ${dark ? "text-white/60" : "text-[#525860]"}`}>{label}</div>
      <div className={`font-heading text-xl font-bold mt-1 font-data ${color || (dark ? "text-white" : "text-[#1A1C1E]")}`}>{value}</div>
      {sub && <div className={`text-[11px] mt-0.5 ${dark ? "text-white/65" : "text-[#686D76]"}`}>{sub}</div>}
    </div>
  );
}
