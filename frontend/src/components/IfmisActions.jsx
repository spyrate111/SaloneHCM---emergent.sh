import { useEffect, useState } from "react";
import api, { downloadBlob, fmtSLE } from "../lib/api";
import { toast } from "sonner";
import { Download, ChevronDown, X, ShieldCheck, FileSpreadsheet, Lock } from "lucide-react";

export default function IfmisActions({ run }) {
  const [formats, setFormats] = useState([]);
  const [open, setOpen] = useState(false);
  const [reconOpen, setReconOpen] = useState(false);

  useEffect(() => {
    if (!formats.length) {
      api.get("/ifmis/formats").then((r) => setFormats(r.data.formats || [])).catch(() => {});
    }
  }, [formats.length]);

  const downloadFormat = async (code, label) => {
    try {
      await downloadBlob(`/ifmis/runs/${run.id}/disbursement/${code}`,
        `disbursement-${code}-${run.period}.${code === "slcb" || code === "ecobank" ? "txt" : "csv"}`);
      toast.success(`${label} file downloaded`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Download failed");
    }
    setOpen(false);
  };

  return (
    <>
      {/* Per-bank disbursement dropdown */}
      <div className="relative inline-block" data-testid={`ifmis-disbursement-${run.id}`}>
        <button
          data-testid={`ifmis-disbursement-toggle-${run.id}`}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center gap-1 text-xs bg-white border border-[#26547C] text-[#26547C] hover:bg-[#E5EEF6] px-2.5 py-1.5 rounded"
        >
          <Download className="w-3.5 h-3.5" /> Bank file
          <ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <div className="absolute right-0 top-full mt-1 w-56 bg-white border border-[#E2DFD6] rounded-md shadow-lg z-20 overflow-hidden">
            <div className="px-3 py-2 text-[9px] uppercase tracking-wider text-[#525860] bg-[#F7F6F2] border-b border-[#E2DFD6]">
              Choose clearing bank
            </div>
            {formats.map((f) => (
              <button
                key={f.code}
                data-testid={`ifmis-format-${f.code}-${run.id}`}
                onClick={() => downloadFormat(f.code, f.label)}
                className="w-full text-left px-3 py-2 text-xs hover:bg-[#F7F6F2] flex items-center gap-2"
              >
                <FileSpreadsheet className="w-3.5 h-3.5 text-[#525860]" />
                {f.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Treasury reconciliation button */}
      <button
        data-testid={`ifmis-recon-open-${run.id}`}
        onClick={() => setReconOpen(true)}
        className={`inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded ${
          run.ifmis_reconciled
            ? "bg-[#E6F4EC] text-[#2D7A5D] border border-[#C2E5D2]"
            : "bg-white border border-[#E2DFD6] text-[#525860] hover:bg-[#F7F6F2]"
        }`}
      >
        {run.ifmis_reconciled ? <Lock className="w-3.5 h-3.5" /> : <ShieldCheck className="w-3.5 h-3.5" />}
        {run.ifmis_reconciled ? "Reconciled" : "Treasury"}
      </button>

      {reconOpen && <ReconciliationModal run={run} onClose={() => setReconOpen(false)} />}
    </>
  );
}

function ReconciliationModal({ run, onClose }) {
  const [data, setData] = useState(null);
  const [ref, setRef] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get(`/ifmis/runs/${run.id}/reconciliation`).then((r) => setData(r.data));
  }, [run.id]);

  const downloadCsv = async () => {
    try {
      await downloadBlob(`/ifmis/runs/${run.id}/reconciliation.csv`, `ifmis-recon-${run.period}.csv`);
    } catch (e) {
      toast.error("CSV download failed");
    }
  };

  const mark = async () => {
    if (!ref.trim()) { toast.error("Enter the IFMIS transaction reference"); return; }
    setBusy(true);
    try {
      await api.post(`/ifmis/runs/${run.id}/mark-reconciled`, { ifmis_reference: ref.trim() });
      toast.success("Run reconciled with IFMIS");
      onClose();
      // light page reload so the parent picks up the new reconciled state
      window.location.reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Mark failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => !busy && onClose()}>
      <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-lg w-full max-w-3xl p-6 max-h-[90vh] overflow-y-auto" data-testid="ifmis-recon-modal">
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">IFMIS · Treasury reconciliation</div>
            <h3 className="font-heading text-xl font-semibold mt-1">{run.period}</h3>
            {data?.org_code && (
              <p className="text-xs text-[#525860] mt-1 font-data">Org code: {data.org_code} · {data.org_name}</p>
            )}
          </div>
          <button onClick={onClose} className="text-[#525860]"><X className="w-4 h-4" /></button>
        </div>

        {!data && <div className="text-sm text-[#525860]">Loading…</div>}

        {data && (
          <>
            {data.reconciled && (
              <div className="bg-[#E6F4EC] border border-[#C2E5D2] rounded-md p-3 mb-4 text-xs">
                <div className="font-semibold text-[#2D7A5D] flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5" /> Already reconciled
                </div>
                <div className="text-[#525860] mt-1">
                  IFMIS ref: <span className="font-data">{data.ifmis_reference}</span> · {new Date(data.ifmis_reconciled_at).toLocaleString()}
                </div>
              </div>
            )}

            <div className="border border-[#E2DFD6] rounded-md mb-4 overflow-x-auto">
              <table className="w-full text-xs" data-testid="ifmis-recon-table">
                <thead className="bg-[#F7F6F2]">
                  <tr>{["Budget code", "Ministry", "Headcount", "Gross", "PAYE", "NASSIT (E+R)", "Net"].map((h) => (
                    <th key={h} className="text-left py-2 px-3 text-[9px] uppercase tracking-wider text-[#525860] font-medium">{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={r.budget_code} className="border-t border-[#E2DFD6]">
                      <td className="py-2 px-3 font-data font-medium">{r.budget_code}</td>
                      <td className="py-2 px-3">{r.mda_ministry}</td>
                      <td className="py-2 px-3 font-data">{r.headcount}</td>
                      <td className="py-2 px-3 font-data">{fmtSLE(r.gross)}</td>
                      <td className="py-2 px-3 font-data">{fmtSLE(r.paye)}</td>
                      <td className="py-2 px-3 font-data">{fmtSLE(r.nassit_employee + r.nassit_employer)}</td>
                      <td className="py-2 px-3 font-data font-semibold">{fmtSLE(r.net)}</td>
                    </tr>
                  ))}
                  <tr className="border-t-2 border-[#1A1C1E] bg-[#FBF8F2]">
                    <td colSpan={2} className="py-2 px-3 font-semibold uppercase text-[10px] tracking-wider">Total</td>
                    <td className="py-2 px-3 font-data font-semibold">{data.totals.headcount}</td>
                    <td className="py-2 px-3 font-data font-semibold">{fmtSLE(data.totals.gross)}</td>
                    <td className="py-2 px-3 font-data font-semibold">{fmtSLE(data.totals.paye)}</td>
                    <td className="py-2 px-3 font-data font-semibold">{fmtSLE(data.totals.nassit_employee + data.totals.nassit_employer)}</td>
                    <td className="py-2 px-3 font-data font-semibold">{fmtSLE(data.totals.net)}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap gap-2 items-center justify-between">
              <button data-testid="ifmis-recon-csv" onClick={downloadCsv}
                className="inline-flex items-center gap-1.5 text-sm border border-[#26547C] text-[#26547C] hover:bg-[#E5EEF6] px-4 py-2 rounded-md">
                <Download className="w-3.5 h-3.5" /> Download CSV
              </button>
              {!data.reconciled && (
                <div className="flex gap-2 items-center">
                  <input
                    data-testid="ifmis-recon-ref"
                    value={ref}
                    onChange={(e) => setRef(e.target.value)}
                    placeholder="IFMIS transaction ref (e.g. IFMIS-TX-2026-05-001)"
                    className="bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data w-72"
                  />
                  <button
                    data-testid="ifmis-recon-mark"
                    disabled={busy || !ref.trim()}
                    onClick={mark}
                    className="inline-flex items-center gap-1.5 text-sm bg-[#133326] hover:bg-[#0F281E] text-white px-4 py-2 rounded-md disabled:opacity-60"
                  >
                    <ShieldCheck className="w-3.5 h-3.5" /> Mark reconciled
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
