/**
 * Mobile payslips — account-scoped summaries and encrypted PDF copies for offline use.
 * Offline copies are tied to the active session token and cleared on sign-out.
 */
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import api, { fmtSLE, getToken } from "../../lib/api";
import { useAuth } from "../../context/AuthContext";
import {
  CheckCircle2,
  FileText,
  WifiOff,
  X,
} from "lucide-react";
import {
  clearOfflinePayslips,
  getOfflinePayslipPdf,
  getOfflinePayslipSummaries,
  listOfflinePayslipPdfRunIds,
  saveOfflinePayslipPdf,
  saveOfflinePayslipSummaries,
} from "../../lib/offlinePayslips";

export default function MobilePayslips() {
  const { user } = useAuth();
  const accountId = user?.id ? String(user.id) : null;
  const activeAccountId = useRef(accountId);
  activeAccountId.current = accountId;
  const [rowsForAccount, setRowsForAccount] = useState({ accountId: null, rows: [] });
  const rows = rowsForAccount.accountId === accountId ? rowsForAccount.rows : [];
  const [offlineRunsForAccount, setOfflineRunsForAccount] = useState({ accountId: null, ids: [] });
  const offlineRuns = offlineRunsForAccount.accountId === accountId ? offlineRunsForAccount.ids : [];
  const [summaryForAccount, setSummaryForAccount] = useState({ accountId: null, saved: false });
  const summaryOffline = summaryForAccount.accountId === accountId && summaryForAccount.saved;
  const [busy, setBusy] = useState(null);
  const [preview, setPreview] = useState(null);
  const [online, setOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const token = getToken();
    setRowsForAccount({ accountId, rows: [] });
    setOfflineRunsForAccount({ accountId, ids: [] });
    setSummaryForAccount({ accountId, saved: false });
    setPreview(null);
    if (!accountId || !token) return () => { cancelled = true; };

    const load = async () => {
      try {
        const [cachedRows, cachedPdfRuns] = await Promise.all([
          getOfflinePayslipSummaries(accountId, token),
          listOfflinePayslipPdfRunIds(accountId, token),
        ]);
        if (cancelled) return;
        setRowsForAccount({ accountId, rows: cachedRows });
        setOfflineRunsForAccount({ accountId, ids: cachedPdfRuns });
        setSummaryForAccount({ accountId, saved: cachedRows.length > 0 });
      } catch {
        // A storage failure should not prevent online payslip access.
      }

      if (!navigator.onLine) return;
      try {
        const response = await api.get("/payroll/my-payslips");
        if (cancelled) return;
        const data = Array.isArray(response.data) ? response.data : [];
        setRowsForAccount({ accountId, rows: data });
        try {
          const saved = await saveOfflinePayslipSummaries(accountId, data, token);
          if (!cancelled && getToken() === token && activeAccountId.current === accountId) {
            setSummaryForAccount({ accountId, saved: Boolean(saved) });
          } else {
            await clearOfflinePayslips(accountId).catch(() => {});
          }
        } catch {
          // Online viewing remains available when device storage is unavailable.
        }
      } catch (error) {
        if ([401, 403].includes(error?.response?.status)) {
          try { await clearOfflinePayslips(accountId); } catch { /* keep the current screen usable */ }
          if (!cancelled) {
            setRowsForAccount({ accountId, rows: [] });
            setOfflineRunsForAccount({ accountId, ids: [] });
            setSummaryForAccount({ accountId, saved: false });
          }
        }
        // Keep the account-scoped encrypted cache for network and server failures.
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [accountId]);

  useEffect(() => {
    if (!preview?.url) return undefined;
    const objectUrl = preview.url;
    return () => URL.revokeObjectURL(objectUrl);
  }, [preview?.url]);

  const openPayslip = async (row) => {
    const token = getToken();
    if (!accountId || !token) {
      toast.error("Sign in again to open this payslip.");
      return;
    }
    setBusy(row.run_id);
    try {
      let blob = null;
      if (online) {
        try {
          const response = await api.get(
            `/payroll/runs/${row.run_id}/payslip/${row.slip.employee_id}.pdf`,
            { responseType: "blob" },
          );
          blob = response.data;
          try {
            if (getToken() !== token || activeAccountId.current !== accountId) return;
            await saveOfflinePayslipPdf(accountId, row.run_id, row.period, blob, token);
            if (getToken() !== token || activeAccountId.current !== accountId) {
              await clearOfflinePayslips(accountId).catch(() => {});
              return;
            }
            setOfflineRunsForAccount((current) => {
              const ids = current.accountId === accountId ? current.ids : [];
              return { accountId, ids: ids.includes(row.run_id) ? ids : [...ids, row.run_id] };
            });
          } catch {
            // Keep the current online view usable if encrypted local storage is unavailable.
          }
        } catch (error) {
          if (error?.response && error.response.status < 500) throw error;
          blob = await getOfflinePayslipPdf(accountId, row.run_id, token);
        }
      } else {
        blob = await getOfflinePayslipPdf(accountId, row.run_id, token);
      }

      if (!blob) {
        toast.error(online
          ? "Could not open this payslip. Try again when connected."
          : "This payslip has not been saved on this device. Open it while online first.");
        return;
      }
      if (getToken() !== token || activeAccountId.current !== accountId) return;
      setPreview({
        accountId,
        period: row.period,
        filename: `payslip-${row.period}.pdf`,
        url: URL.createObjectURL(blob),
      });
    } catch {
      toast.error("Could not open the saved payslip on this device.");
    } finally {
      setBusy(null);
    }
  };

  const clearSavedCopies = async () => {
    if (!accountId) return;
    try {
      await clearOfflinePayslips(accountId);
      setOfflineRunsForAccount({ accountId, ids: [] });
      setSummaryForAccount({ accountId, saved: false });
      setRowsForAccount((current) => ({
        accountId,
        rows: current.accountId === accountId ? current.rows : [],
      }));
      toast.success("Offline payslip copies removed from this device.");
    } catch {
      toast.error("Could not clear offline payslip copies.");
    }
  };

  return (
    <div className="p-4 space-y-3" data-testid="mobile-payslips">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold text-[#0A4A1E]">My payslips</h1>
          <p className="text-[11px] text-[#525860] mt-1">
            {rows.length} run{rows.length === 1 ? "" : "s"} · {summaryOffline ? "amounts saved offline" : online ? "open a payslip to save it offline" : "no saved payslip summary"}
          </p>
        </div>
        {(offlineRuns.length > 0 || summaryOffline) && (
          <button
            type="button"
            onClick={clearSavedCopies}
            className="text-[10px] text-[#525860] underline"
            data-testid="mobile-payslips-clear-offline"
          >
            Clear offline copies
          </button>
        )}
      </div>

      {!online && (
        <div className="bg-[#F6EDD8] text-[#8B6A14] rounded-lg px-3 py-2 text-[11px] flex items-center gap-2" data-testid="mobile-payslips-offline-banner">
          <WifiOff className="w-3.5 h-3.5" />
          Offline mode · saved PDFs open from this device; unsaved PDFs need a connection.
        </div>
      )}

      {rows.length === 0 && (
        <div className="text-center py-10 text-[#525860]" data-testid="mobile-payslips-empty">
          <FileText className="w-10 h-10 mx-auto text-[#A1A5AB]" />
          <p className="mt-2 text-sm">No payslips are saved for this account yet.</p>
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
                Gross <span className="font-data">{fmtSLE(row.slip?.gross)}</span> · PAYE <span className="font-data">{fmtSLE(row.slip?.paye)}</span>
              </div>
              <div className="text-[13px] font-bold text-[#0A4A1E] mt-1 font-data">
                Net {fmtSLE(row.slip?.net)}
              </div>
              {offlineRuns.includes(row.run_id) && (
                <div className="text-[10px] text-[#0A4A1E] mt-1 flex items-center gap-1" data-testid={`mobile-payslip-offline-${row.period}`}>
                  <CheckCircle2 className="w-3 h-3" /> PDF saved on this device
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => openPayslip(row)}
              disabled={busy === row.run_id}
              className="text-[#0072C6] text-xs px-2 py-2 active:bg-[#F7F6F2] rounded-lg disabled:opacity-50"
              data-testid={`mobile-payslip-open-${row.period}`}
              aria-label={`Open payslip ${row.period}`}
            >
              {busy === row.run_id ? "Opening…" : "Open"}
            </button>
          </div>
        ))}
      </div>
      <p className="text-center text-[10px] text-[#686D76]">
        Open a payslip while online to save an encrypted PDF for offline viewing. Signing out removes saved payslips.
      </p>

      {preview?.accountId === accountId && (
        <div
          className="fixed inset-0 z-[70] bg-black/60 p-3 sm:p-6 grid place-items-center"
          onClick={() => setPreview(null)}
          data-testid="mobile-payslip-preview"
        >
          <div
            className="bg-white rounded-xl w-full max-w-4xl h-[92vh] flex flex-col overflow-hidden"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-3 border-b border-[#E2DFD6] px-4 py-3">
              <div>
                <h2 className="font-semibold text-sm">Payslip · {preview.period}</h2>
                <p className="text-[10px] text-[#686D76]">Private to your signed-in account on this device.</p>
              </div>
              <button
                type="button"
                onClick={() => setPreview(null)}
                aria-label="Close payslip"
                className="p-2 text-[#525860]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <iframe
              title={`Payslip ${preview.period}`}
              src={preview.url}
              className="flex-1 w-full border-0"
              data-testid="mobile-payslip-pdf-frame"
            />
            <div className="border-t border-[#E2DFD6] px-4 py-2 text-right">
              <a
                href={preview.url}
                download={preview.filename}
                className="text-xs text-[#0072C6] underline"
              >
                Download PDF
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
