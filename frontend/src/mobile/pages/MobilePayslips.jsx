/**
 * Mobile payslips — list of my payslips with a native-style download button
 * that saves the PDF via the same authenticated axios instance (cookie + CSRF).
 * Cached to localStorage for offline read-only viewing.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { downloadBlob, fmtSLE } from "../../lib/api";
import { FileText, Download, ChevronRight } from "lucide-react";

const CACHE_KEY = "salonehcm_m_payslips";

export default function MobilePayslips() {
  const [rows, setRows] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY) || "[]"); } catch { return []; }
  });
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    api.get("/payroll/my-payslips").then((r) => {
      const data = r.data || [];
      setRows(data);
      try { localStorage.setItem(CACHE_KEY, JSON.stringify(data)); } catch { /* noop */ }
    }).catch(() => { /* keep cache */ });
  }, []);

  const download = async (row) => {
    setBusy(row.run_id);
    try {
      await downloadBlob(
        `/payroll/runs/${row.run_id}/payslip/${row.slip.employee_id}.pdf`,
        `payslip-${row.period}.pdf`,
      );
      toast.success(`Downloaded ${row.period} payslip`);
    } catch (e) {
      toast.error("Could not download — try again when online");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="p-4 space-y-3" data-testid="mobile-payslips">
      <div>
        <h1 className="text-lg font-bold text-[#0A4A1E]">My payslips</h1>
        <p className="text-[11px] text-[#525860] mt-1">
          {rows.length} run{rows.length === 1 ? "" : "s"} · tap to download PDF
        </p>
      </div>

      {rows.length === 0 && (
        <div className="text-center py-10 text-[#525860]" data-testid="mobile-payslips-empty">
          <FileText className="w-10 h-10 mx-auto text-[#A1A5AB]" />
          <p className="mt-2 text-sm">No payroll runs yet.</p>
        </div>
      )}

      <div className="divide-y divide-[#F1EEE6] bg-white border border-[#E2DFD6] rounded-xl overflow-hidden">
        {rows.map((row) => (
          <div key={row.run_id} className="flex items-center gap-3 p-4" data-testid={`mobile-payslip-row-${row.period}`}>
            <div className="w-10 h-10 rounded-lg bg-[#E4F7E7] flex items-center justify-center flex-shrink-0">
              <FileText className="w-5 h-5 text-[#0A4A1E]" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold">{row.period}</div>
              <div className="text-[11px] text-[#525860] mt-0.5">
                Gross <span className="font-data">{fmtSLE(row.slip.gross)}</span> · PAYE <span className="font-data">{fmtSLE(row.slip.paye)}</span>
              </div>
              <div className="text-[13px] font-bold text-[#0A4A1E] mt-1 font-data">
                Net {fmtSLE(row.slip.net)}
              </div>
            </div>
            <button
              onClick={() => download(row)}
              disabled={busy === row.run_id}
              className="text-[#0072C6] p-2 active:bg-[#F7F6F2] rounded-lg disabled:opacity-50"
              data-testid={`mobile-payslip-download-${row.period}`}
              aria-label={`Download payslip ${row.period}`}
            >
              {busy === row.run_id ? (
                <span className="text-[11px]">…</span>
              ) : (
                <Download className="w-5 h-5" />
              )}
            </button>
          </div>
        ))}
      </div>
      <p className="text-center text-[10px] text-[#A1A5AB]">Recent payslips are cached for offline viewing.</p>
    </div>
  );
}
