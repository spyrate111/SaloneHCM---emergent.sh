import { useCallback, useEffect, useState } from "react";
import { Download, ShieldCheck, Smartphone, X } from "lucide-react";
import { toast } from "sonner";
import api, { downloadBlob, fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const PROVIDERS = [
  ["orange_money", "Orange Money"],
  ["afrimoney", "Afrimoney"],
];
const STATUS_LABELS = {
  pending: "Awaiting provider result",
  paid: "Paid",
  failed: "Failed",
};

export default function MobileMoneyBatchActions({ run }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [provider, setProvider] = useState("orange_money");
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [batches, setBatches] = useState([]);
  const [selectedBatchId, setSelectedBatchId] = useState(null);
  const [batch, setBatch] = useState(null);
  const [edits, setEdits] = useState({});
  const [busy, setBusy] = useState("");

  const loadBatches = useCallback(async () => {
    try {
      const { data } = await api.get("/payroll/runs/" + run.id + "/mobile-money-batches");
      setBatches(data);
      if (selectedBatchId) {
        const detail = await api.get("/payroll/mobile-money/batches/" + selectedBatchId);
        setBatch(detail.data);
        setEdits(Object.fromEntries((detail.data.recipients || []).map((recipient) => [
          recipient.id,
          {
            status: recipient.status === "pending" ? "" : recipient.status,
            provider_reference: recipient.provider_reference || "",
            failure_reason: recipient.failure_reason || "",
          },
        ])));
      } else {
        setBatch(null);
      }
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not load mobile money batches");
    }
  }, [run.id, selectedBatchId]);

  useEffect(() => {
    if (open) loadBatches();
  }, [open, loadBatches]);

  const createBatch = async () => {
    setBusy("create");
    try {
      const { data } = await api.post("/payroll/runs/" + run.id + "/mobile-money-batches", {
        provider,
        payment_date: paymentDate,
      });
      setBatches((current) => [data, ...current.filter((item) => item.id !== data.id)]);
      setSelectedBatchId(data.id);
      toast.success(data.already_exists
        ? "This provider batch already exists for the payroll run"
        : "Batch created and sent for manager approval");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not prepare mobile money batch");
    } finally {
      setBusy("");
    }
  };

  const retryFailed = async () => {
    if (!batch) return;
    setBusy("retry");
    try {
      const { data } = await api.post(
        "/payroll/mobile-money/batches/" + batch.id + "/retry-failed",
        { payment_date: paymentDate },
      );
      setBatches((current) => [data, ...current.filter((item) => item.id !== data.id)]);
      setSelectedBatchId(data.id);
      toast.success(data.already_exists
        ? "A retry batch already exists for these failed payments"
        : "Failed payments copied to a new approval batch");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not prepare failed-payment retry");
    } finally {
      setBusy("");
    }
  };

  const approveBatch = async () => {
    if (!batch) return;
    setBusy("approve");
    try {
      await api.post("/payroll/mobile-money/batches/" + batch.id + "/approve");
      toast.success("Payment batch approved");
      await loadBatches();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not approve batch");
    } finally {
      setBusy("");
    }
  };

  const exportBatch = async () => {
    if (!batch) return;
    setBusy("export");
    try {
      const filename = "SaloneHCM-Mobile-Money-Workpaper-" + batch.provider + "-" + batch.period + ".xlsx";
      await downloadBlob("/payroll/mobile-money/batches/" + batch.id + "/workbook", filename);
      await loadBatches();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not download mobile money workpaper");
    } finally {
      setBusy("");
    }
  };

  const reconcileRecipient = async (recipient) => {
    const edit = edits[recipient.id] || {};
    if (!edit.status) {
      toast.error("Choose Paid or Failed before saving");
      return;
    }
    setBusy(recipient.id);
    try {
      await api.post(
        "/payroll/mobile-money/batches/" + batch.id + "/recipients/" + recipient.id + "/reconcile",
        {
          status: edit.status,
          provider_reference: edit.provider_reference || "",
          failure_reason: edit.failure_reason || "",
        },
      );
      toast.success("Payment result recorded");
      await loadBatches();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not record payment result");
    } finally {
      setBusy("");
    }
  };

  const updateEdit = (recipientId, field, value) => {
    setEdits((current) => ({
      ...current,
      [recipientId]: { ...(current[recipientId] || {}), [field]: value },
    }));
  };

  const canApprove = ["manager", "admin", "superadmin"].includes(user?.role);
  const batchIsExported = batch && ["exported", "partially_reconciled", "reconciled"].includes(batch.status);

  return (
    <>
      <button
        data-testid={"mobile-money-" + run.id}
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 text-xs bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#26547C] px-2.5 py-1.5 rounded"
      >
        <Smartphone className="w-3.5 h-3.5" /> Mobile money
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-3 sm:p-5"
          onClick={() => setOpen(false)}
          data-testid="mobile-money-modal"
        >
          <div
            className="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[92vh] overflow-y-auto p-5 sm:p-6"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">SLE disbursement</div>
                <h2 className="font-heading text-xl font-semibold mt-1">Mobile money · {run.period}</h2>
                <p className="text-xs text-[#686D76] mt-2 max-w-3xl">
                  Prepare an SLE payment workpaper, require a separate manager approval, then record each provider result.
                  No live provider API is connected. Confirm the provider&rsquo;s current upload format before using this workbook.
                </p>
              </div>
              <button onClick={() => setOpen(false)} className="p-1 text-[#686D76]" aria-label="Close mobile money batch">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-5 rounded-lg border border-[#E2DFD6] bg-[#F7F6F2] p-4">
              <h3 className="font-medium text-sm">Prepare a batch for this payroll run</h3>
              <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-3 items-end mt-3">
                <label className="text-xs text-[#525860]">
                  Provider
                  <select
                    data-testid="mobile-money-provider"
                    value={provider}
                    onChange={(event) => setProvider(event.target.value)}
                    className="mt-1 block w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm text-[#1A1C1E]"
                  >
                    {PROVIDERS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                <label className="text-xs text-[#525860]">
                  Intended payment date
                  <input
                    data-testid="mobile-money-payment-date"
                    type="date"
                    value={paymentDate}
                    onChange={(event) => setPaymentDate(event.target.value)}
                    className="mt-1 block w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm text-[#1A1C1E]"
                  />
                </label>
                <button
                  data-testid="mobile-money-create-batch"
                  onClick={createBatch}
                  disabled={busy !== ""}
                  className="inline-flex items-center justify-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white px-4 py-2 rounded-md text-sm disabled:opacity-50"
                >
                  {busy === "create" ? "Preparing…" : "Prepare for approval"}
                </button>
              </div>
            </div>

            {batches.length > 0 && (
              <div className="mt-5">
                <h3 className="font-medium text-sm mb-2">Existing batches</h3>
                <div className="flex flex-wrap gap-2">
                  {batches.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => setSelectedBatchId(item.id)}
                      className={"border rounded-md px-3 py-2 text-left text-xs " + (
                        selectedBatchId === item.id
                          ? "border-[#26547C] bg-[#E5EEF6]"
                          : "border-[#E2DFD6] bg-white"
                      )}
                    >
                      <span className="font-medium">{item.provider_name}</span>
                      <span className="text-[#686D76]"> · {item.status.replaceAll("_", " ")}</span>
                      <span className="block mt-1">{item.recipient_count} staff · {fmtSLE(item.total_amount_sle)}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {batch && (
              <div className="mt-5 border border-[#E2DFD6] rounded-lg overflow-hidden">
                <div className="p-4 bg-white flex flex-wrap items-center justify-between gap-3 border-b border-[#E2DFD6]">
                  <div>
                    <div className="font-medium text-sm">{batch.provider_name} · {batch.status.replaceAll("_", " ")}</div>
                    <div className="text-xs text-[#686D76] mt-1">
                      {batch.recipient_count} staff · {fmtSLE(batch.total_amount_sle)} · payment date {batch.payment_date} · {batch.currency}
                    </div>
                    <div className="text-xs text-[#686D76] mt-1">
                      {batch.paid_count} paid · {batch.failed_count} failed · {batch.pending_count} pending
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {batch.status === "pending_approval" && canApprove && batch.created_by !== user?.email && (
                      <button
                        data-testid={"mobile-money-approve-" + batch.id}
                        onClick={approveBatch}
                        disabled={busy !== ""}
                        className="inline-flex items-center gap-1.5 bg-[#17A035] hover:bg-[#148231] text-white px-3 py-2 rounded-md text-xs disabled:opacity-50"
                      >
                        <ShieldCheck className="w-3.5 h-3.5" /> {busy === "approve" ? "Approving…" : "Approve"}
                      </button>
                    )}
                    {batch.status === "pending_approval" && batch.created_by === user?.email && (
                      <span className="text-xs text-[#8B6A14]">Awaiting approval from another manager.</span>
                    )}
                    {batch.failed_count > 0 && (
                      <button
                        data-testid={"mobile-money-retry-" + batch.id}
                        onClick={retryFailed}
                        disabled={busy !== ""}
                        className="inline-flex items-center gap-1.5 border border-[#B84F2F] text-[#B84F2F] hover:bg-[#FBE9DF] px-3 py-2 rounded-md text-xs disabled:opacity-50"
                      >
                        {busy === "retry" ? "Preparing retry…" : "Prepare failed-payment retry"}
                      </button>
                    )}
                    {batch.status !== "pending_approval" && batch.pending_count > 0 && (
                      <button
                        data-testid={"mobile-money-export-" + batch.id}
                        onClick={exportBatch}
                        disabled={busy !== ""}
                        className="inline-flex items-center gap-1.5 border border-[#26547C] text-[#26547C] hover:bg-[#E5EEF6] px-3 py-2 rounded-md text-xs disabled:opacity-50"
                      >
                        <Download className="w-3.5 h-3.5" /> {busy === "export" ? "Preparing…" : "Download workbook"}
                      </button>
                    )}
                  </div>
                </div>

                {batchIsExported && (
                  <div className="p-4 bg-[#F7F6F2]">
                    <h4 className="font-medium text-xs uppercase tracking-wider text-[#525860] mb-3">Record provider results</h4>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs min-w-[900px]">
                        <thead className="text-[#525860]">
                          <tr>
                            {["Employee", "Wallet", "Amount", "Current result", "New result", "Transaction reference / failure reason", ""].map((label) => (
                              <th key={label} className="text-left font-medium pb-2 pr-3">{label}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {batch.recipients.map((recipient) => {
                            const edit = edits[recipient.id] || {};
                            return (
                              <tr key={recipient.id} className="border-t border-[#E2DFD6] align-top">
                                <td className="py-2 pr-3">{recipient.employee_name}</td>
                                <td className="py-2 pr-3 font-data">{recipient.mobile_number}</td>
                                <td className="py-2 pr-3 font-data">{fmtSLE(recipient.amount_sle)}</td>
                                <td className="py-2 pr-3">{STATUS_LABELS[recipient.status] || recipient.status}</td>
                                <td className="py-2 pr-3">
                                  <select
                                    aria-label={"New result for " + recipient.employee_name}
                                    value={edit.status || ""}
                                    onChange={(event) => updateEdit(recipient.id, "status", event.target.value)}
                                    className="w-32 border border-[#E2DFD6] rounded px-2 py-1"
                                  >
                                    <option value="">Select</option>
                                    <option value="paid">Paid</option>
                                    <option value="failed">Failed</option>
                                  </select>
                                </td>
                                <td className="py-2 pr-3">
                                  {(edit.status || recipient.status) === "paid" ? (
                                    <input
                                      aria-label={"Provider reference for " + recipient.employee_name}
                                      value={edit.provider_reference || ""}
                                      onChange={(event) => updateEdit(recipient.id, "provider_reference", event.target.value)}
                                      placeholder="Provider transaction reference"
                                      className="w-full border border-[#E2DFD6] rounded px-2 py-1"
                                    />
                                  ) : (
                                    <input
                                      aria-label={"Failure reason for " + recipient.employee_name}
                                      value={edit.failure_reason || ""}
                                      onChange={(event) => updateEdit(recipient.id, "failure_reason", event.target.value)}
                                      placeholder="Reason (required for failed)"
                                      className="w-full border border-[#E2DFD6] rounded px-2 py-1"
                                    />
                                  )}
                                </td>
                                <td className="py-2 pr-3">
                                  <button
                                    onClick={() => reconcileRecipient(recipient)}
                                    disabled={busy !== ""}
                                    className="border border-[#E2DFD6] rounded px-2 py-1 hover:bg-white disabled:opacity-50"
                                  >
                                    {busy === recipient.id ? "Saving…" : "Save"}
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
