/**
 * Payslip QR scan log — admins see how often each payslip was verified.
 * Rows flagged when 5+ scans land within any 24-hour window. Click a row
 * for the full scan history. Hides itself on 403/error.
 */
import { useEffect, useState } from "react";
import api from "../lib/api";
import { ScanLine, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";

const ts = (t) => (t ? new Date(t).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "—");

export default function PayslipScanPanel() {
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(null); // verification_id
  const [history, setHistory] = useState({});

  useEffect(() => {
    api.get("/payroll/verification-scans").then((r) => {
      setRows(r.data);
      // deep link from the fraud-alert push: /payroll?flag={vid}
      const flag = new URLSearchParams(window.location.search).get("flag");
      if (flag && r.data.some((x) => x.verification_id === flag)) {
        setOpen(flag);
        api.get(`/payroll/verification-scans/${flag}`)
          .then((h) => setHistory((prev) => ({ ...prev, [flag]: h.data.scans })))
          .catch(() => {});
        setTimeout(() => {
          document.querySelector(`[data-testid="payslip-scan-row-${flag}"]`)
            ?.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 400);
      }
    }).catch(() => setRows(null));
  }, []);

  const toggle = async (vid) => {
    if (open === vid) { setOpen(null); return; }
    setOpen(vid);
    if (!history[vid]) {
      try {
        const r = await api.get(`/payroll/verification-scans/${vid}`);
        setHistory((h) => ({ ...h, [vid]: r.data.scans }));
      } catch { /* leave loading */ }
    }
  };

  if (!rows) return null;
  const flaggedCount = rows.filter((r) => r.flagged).length;

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="payslip-scan-panel">
      <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center gap-3 flex-wrap">
        <h3 className="font-heading text-lg font-semibold flex items-center gap-2">
          <ScanLine className="w-4 h-4 text-[#0A4A1E]" /> Payslip QR scan log
        </h3>
        <span className="text-[11px] text-[#525860]">Every bank verification scan, logged. Flag = 5+ scans within 24h.</span>
        {flaggedCount > 0 && (
          <span className="ml-auto inline-flex items-center gap-1 text-[11px] font-bold text-[#B03A2E] bg-[#FBE9E9] px-2.5 py-1 rounded-full"
                data-testid="payslip-scan-flagged-count">
            <AlertTriangle className="w-3.5 h-3.5" /> {flaggedCount} flagged
          </span>
        )}
      </div>
      <table className="w-full text-sm" data-testid="payslip-scan-table">
        <thead className="bg-[#F7F6F2]">
          <tr>{["Employee", "Period", "Scans", "First scan", "Last scan", "Status", ""].map((h, i) => (
            <th key={i} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-4 font-medium">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <FragmentRow key={r.verification_id} r={r} open={open === r.verification_id}
                         scans={history[r.verification_id]} onToggle={() => toggle(r.verification_id)} />
          ))}
          {!rows.length && (
            <tr><td colSpan={7} className="py-8 text-center text-sm text-[#686D76]" data-testid="payslip-scan-empty">
              No payslip verifications yet — QR codes appear on every downloaded payslip PDF.
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function FragmentRow({ r, open, scans, onToggle }) {
  return (
    <>
      <tr onClick={onToggle}
          className={`border-t border-[#E2DFD6] cursor-pointer hover:bg-[#F7F6F2] ${r.flagged ? "bg-[#FBE9E9]/40" : ""}`}
          data-testid={`payslip-scan-row-${r.verification_id}`}>
        <td className="py-2.5 px-4 font-medium">{r.employee_name}</td>
        <td className="py-2.5 px-4 font-data text-xs">{r.period}</td>
        <td className="py-2.5 px-4 font-data">{r.scan_count}</td>
        <td className="py-2.5 px-4 text-xs text-[#525860]">{ts(r.first_scanned_at)}</td>
        <td className="py-2.5 px-4 text-xs text-[#525860]">{ts(r.last_scanned_at)}</td>
        <td className="py-2.5 px-4">
          {r.flagged ? (
            <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-[#B03A2E] text-white"
                  data-testid={`payslip-scan-flag-${r.verification_id}`}>
              <AlertTriangle className="w-3 h-3" /> Unusual
            </span>
          ) : (
            <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-[#E4F7E7] text-[#0A4A1E]">Normal</span>
          )}
        </td>
        <td className="py-2.5 px-4 text-right">
          {open ? <ChevronUp className="w-4 h-4 text-[#8A8F96] inline" /> : <ChevronDown className="w-4 h-4 text-[#8A8F96] inline" />}
        </td>
      </tr>
      {open && (
        <tr className="border-t border-[#F1EEE6] bg-[#FBFAF7]">
          <td colSpan={7} className="px-6 py-3" data-testid={`payslip-scan-history-${r.verification_id}`}>
            {!scans ? (
              <span className="text-xs text-[#686D76]">Loading scan history…</span>
            ) : !scans.length ? (
              <span className="text-xs text-[#686D76]">Never scanned.</span>
            ) : (
              <div className="space-y-1 max-h-56 overflow-y-auto">
                {scans.map((s) => (
                  <div key={s.id} className="flex items-center gap-3 text-[11px] text-[#525860]">
                    <span className="font-data text-[#1A1C1E] w-44 flex-shrink-0">{ts(s.scanned_at)}</span>
                    <span className="font-data w-32 flex-shrink-0">{s.ip || "unknown IP"}</span>
                    <span className="truncate">{s.user_agent || ""}</span>
                  </div>
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
