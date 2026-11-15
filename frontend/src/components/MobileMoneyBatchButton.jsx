import { useCallback, useEffect, useState } from "react";
import { Download, Wallet, Check, XCircle, AlertCircle } from "lucide-react";
import api, { downloadBlob, fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";

const PROVIDERS = [
  ["orange_money", "Orange Money"],
  ["afrimoney", "Afrimoney"],
];

const BATCH_LABEL = {
  draft: "Draft",
  approved: "Approved",
  exported: "Workpaper exported",
  submitted: "Marked submitted",
  reconciling: "Reconciling",
  reconciled: "Reconciled",
  reconciled_with_failures: "Reconciled with failures",
};

export default function MobileMoneyBatchButton({ run }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [provider, setProvider] = useState("orange_money");
  const [batches, setBatches] = useState([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const { data } = await api.get(`/payroll/runs/${run.id}/mobile-money-batches`);
    setBatches(data.batches || []);
  }, [run.id]);

  useEffect(() => {
    if (open) refresh().catch((error) => toast.error(error?.response?.data?.detail || "Could not load wallet batches"));
  }, [open, refresh]);

  const create = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/payroll/runs/${run.id}/mobile-money-batches`, { provider });
      await refresh();
      toast.success(data.created ? "Wallet batch draft created" : "Existing wallet batch opened");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not create wallet batch");
    } finally {
      setBusy(false);
    }
  };

  const runAction = async (action, successText) => {
    setBusy(true);
    try {
      await action();
      await refresh();
      if (successText) toast.success(successText);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Wallet batch action failed");
    } finally {
      setBusy(false);
    }
  };

  const approve = (batch) => runAction(
    () => api.post(`/payroll/runs/${run.id}/mobile-money-batches/${batch.id}/approve`),
    "Wallet batch approved",
  );

  const cancel = (batch) => {
    if (!window.confirm("Cancel this unapproved wallet batch? Its employee assignments will be released.")) return;
    runAction(
      () => api.delete(`/payroll/runs/${run.id}/mobile-money-batches/${batch.id}`),
      "Wallet batch cancelled",
    );
  };

  const exportBatch = (batch) => runAction(
    () => downloadBlob(
      `/payroll/runs/${run.id}/mobile-money-batches/${batch.id}.csv`,
      `mobile-money-${batch.provider}-${batch.period}.csv`,
    ),
    "Internal workpaper downloaded",
  );

  const markSubmitted = (batch) => {
    if (!window.confirm("Have you uploaded this workpaper through the provider's employer portal? SaloneHCM does not submit it.")) return;
    const reference = window.prompt("Optional provider batch reference (leave blank if none):");
    if (reference === null) return;
    runAction(
      () => api.post(`/payroll/runs/${run.id}/mobile-money-batches/${batch.id}/mark-submitted`, {
        provider_batch_reference: reference,
      }),
      "Provider-portal submission recorded",
    );
  };

  const reconcileLine = (batch, line, status) => {
    const value = status === "paid"
      ? window.prompt(`Provider transaction reference for ${line.employee_name}:`)
      : window.prompt(`Failure reason for ${line.employee_name}:`);
    if (value === null || !value.trim()) return;
    const payload = status === "paid"
      ? { status, provider_transaction_reference: value.trim() }
      : { status, failure_reason: value.trim() };
    runAction(
      () => api.patch(
        `/payroll/runs/${run.id}/mobile-money-batches/${batch.id}/lines/${line.employee_id}`,
        payload,
      ),
      status === "paid" ? "Payment marked paid" : "Payment failure recorded",
    );
  };

  return (
    <>
      <button
        type="button"
        data-testid={`mobile-money-${run.id}`}
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 text-xs bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#0A4A1E] px-2.5 py-1.5 rounded"
      >
        <Wallet className="w-3.5 h-3.5" /> Wallet batches
      </button>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
          <div
            className="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto p-5 sm:p-6 space-y-5"
            onClick={(event) => event.stopPropagation()}
            data-testid="mobile-money-batches-modal"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Payroll disbursement workpaper</div>
                <h2 className="font-heading text-xl font-semibold mt-1">Wallet batches · {run.period}</h2>
                <p className="text-xs text-[#686D76] mt-2 max-w-3xl">
                  SaloneHCM does not call Orange Money or Afrimoney. This SLE workpaper must be reviewed, uploaded manually in the provider portal, and reconciled here. Confirm employer API and upload requirements with the provider before relying on a direct integration. Create wallet batches before exporting the bank file; bank-file exports reserve the remaining employees for the bank channel to prevent duplicate payment files.
                </p>
              </div>
              <button type="button" onClick={() => setOpen(false)} className="p-1 text-[#686D76]" aria-label="Close wallet batches">
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="flex flex-wrap items-end gap-3 border border-[#E2DFD6] rounded-lg p-3">
              <label className="text-xs text-[#525860]">
                Provider assignment
                <select value={provider} onChange={(event) => setProvider(event.target.value)}
                  className="mt-1 block bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                  {PROVIDERS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <button type="button" onClick={create} disabled={busy}
                className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-xs px-3 py-2 rounded-md disabled:opacity-50">
                <Wallet className="w-3.5 h-3.5" /> {busy ? "Working…" : "Create / open draft"}
              </button>
              <span className="text-[11px] text-[#686D76]">
                Employees must have this primary provider and a separate wallet number in their profile.
              </span>
            </div>

            {!batches.length && <p className="text-sm text-[#686D76]">No wallet batches for this payroll run.</p>}

            <div className="space-y-4">
              {batches.map((batch) => (
                <section key={batch.id} className="border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid={`mobile-money-batch-${batch.id}`}>
                  <div className="flex flex-wrap items-center justify-between gap-3 bg-[#F7F6F2] px-4 py-3">
                    <div>
                      <div className="font-medium text-sm">{batch.provider_label} · {batch.period}</div>
                      <div className="text-[11px] text-[#686D76]">
                        {BATCH_LABEL[batch.status] || batch.status} · {batch.lines.length} employees · {fmtSLE(batch.lines.reduce((sum, line) => sum + Number(line.amount_sle || 0), 0))}
                        {batch.export_count ? ` · downloaded ${batch.export_count} time${batch.export_count === 1 ? "" : "s"}` : ""}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {batch.status === "draft" && batch.created_by_email === user?.email && (
                        <button type="button" onClick={() => cancel(batch)} disabled={busy}
                          className="text-xs border border-[#B83A3A] text-[#B83A3A] px-2.5 py-1.5 rounded disabled:opacity-50">Cancel draft</button>
                      )}
                      {batch.status === "draft" && batch.created_by_email !== user?.email && (
                        <button type="button" onClick={() => approve(batch)} disabled={busy || !batch.lines.length}
                          className="inline-flex items-center gap-1 text-xs bg-[#0A4A1E] text-white px-2.5 py-1.5 rounded disabled:opacity-50">
                          <Check className="w-3.5 h-3.5" /> Approve as checker
                        </button>
                      )}
                      {["approved", "exported"].includes(batch.status) && (
                        <button type="button" onClick={() => exportBatch(batch)} disabled={busy}
                          className="inline-flex items-center gap-1 text-xs border border-[#26547C] text-[#26547C] px-2.5 py-1.5 rounded disabled:opacity-50">
                          <Download className="w-3.5 h-3.5" /> Download internal CSV
                        </button>
                      )}
                      {batch.status === "exported" && (
                        <button type="button" onClick={() => markSubmitted(batch)} disabled={busy}
                          className="text-xs bg-[#26547C] text-white px-2.5 py-1.5 rounded disabled:opacity-50">Record portal submission</button>
                      )}
                    </div>
                  </div>

                  {batch.created_by && <div className="px-4 pt-3 text-[11px] text-[#686D76]">Prepared by {batch.created_by}{batch.approved_by ? ` · approved by ${batch.approved_by}` : ""}{batch.submitted_at ? ` · portal submission recorded ${batch.submitted_at.slice(0, 10)}` : ""}</div>}
                  {batch.excluded?.length > 0 && (
                    <div className="mx-4 mt-3 rounded-md bg-[#FBF1DE] px-3 py-2 text-xs text-[#8B6A14]">
                      <AlertCircle className="inline w-3.5 h-3.5 mr-1" /> {batch.excluded.length} employee(s) assigned to this provider have no wallet number and were excluded. Cancel this draft, update their profile, then create it again.
                      <div className="mt-1">{batch.excluded.map((item) => item.employee_name).join(", ")}</div>
                    </div>
                  )}
                  {!batch.lines.length && (
                    <div className="px-4 py-4 text-xs text-[#686D76]">
                      No positive-net employees are configured for this provider yet. Cancel this draft, set a provider and wallet number on employee profiles, then create it again.
                    </div>
                  )}
                  <div className="divide-y divide-[#F1EEE6]">
                    {batch.lines.map((line) => (
                      <div key={line.employee_id} className="px-4 py-3 flex flex-wrap items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-medium">{line.employee_name}</div>
                          <div className="text-[11px] text-[#686D76]">
                            {line.mobile_money_number} · {fmtSLE(line.amount_sle)} · {line.status}
                            {line.provider_transaction_reference ? ` · ref ${line.provider_transaction_reference}` : ""}
                            {line.failure_reason ? ` · ${line.failure_reason}` : ""}
                          </div>
                        </div>
                        {["submitted", "reconciling", "reconciled_with_failures"].includes(batch.status) && line.status !== "paid" && (
                          <div className="flex gap-2">
                            <button type="button" onClick={() => reconcileLine(batch, line, "paid")} disabled={busy}
                              className="text-xs border border-[#0A4A1E] text-[#0A4A1E] px-2 py-1 rounded disabled:opacity-50">Mark paid</button>
                            <button type="button" onClick={() => reconcileLine(batch, line, "failed")} disabled={busy}
                              className="text-xs border border-[#B83A3A] text-[#B83A3A] px-2 py-1 rounded disabled:opacity-50">Mark failed</button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="px-4 py-3 text-[11px] text-[#686D76] border-t border-[#F1EEE6]">
                    A paid line needs a provider transaction reference. A failed line needs a reason. Paid lines are locked; failed lines can be updated after checking the provider portal.
                  </div>
                </section>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
