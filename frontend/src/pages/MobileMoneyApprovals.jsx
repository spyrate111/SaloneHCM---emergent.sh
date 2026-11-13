import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, Smartphone } from "lucide-react";
import { toast } from "sonner";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function MobileMoneyApprovals() {
  const { user } = useAuth();
  const [batches, setBatches] = useState([]);
  const [batch, setBatch] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/payroll/mobile-money/pending-approvals");
      setBatches(data);
      if (batch?.id) {
        const detail = await api.get("/payroll/mobile-money/batches/" + batch.id);
        setBatch(detail.data);
      }
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not load payment approvals");
    }
  }, [batch?.id]);

  useEffect(() => { load(); }, [load]);

  const selectBatch = async (id) => {
    try {
      const { data } = await api.get("/payroll/mobile-money/batches/" + id);
      setBatch(data);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not open payment batch");
    }
  };

  const approve = async () => {
    if (!batch) return;
    setBusy(true);
    try {
      const { data } = await api.post("/payroll/mobile-money/batches/" + batch.id + "/approve");
      setBatch(data);
      toast.success("Payment batch approved");
      await load();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not approve payment batch");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5" data-testid="mobile-money-approvals-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Payroll controls</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Mobile money approvals</h1>
        <p className="text-sm text-[#686D76] mt-2 max-w-3xl">
          Review provider, payment date, recipient wallets and total SLE before approving. The person who prepared a batch cannot approve it.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-4">
        <section className="bg-white border border-[#E2DFD6] rounded-lg p-4">
          <h2 className="font-heading text-lg font-semibold mb-3">Awaiting approval</h2>
          <div className="space-y-2">
            {batches.map((item) => (
              <button
                key={item.id}
                onClick={() => selectBatch(item.id)}
                className={"w-full text-left border rounded-md p-3 " + (
                  batch?.id === item.id ? "border-[#26547C] bg-[#E5EEF6]" : "border-[#E2DFD6] hover:bg-[#F7F6F2]"
                )}
              >
                <div className="flex justify-between gap-2 text-sm font-medium">
                  <span>{item.provider_name}</span>
                  <span>{item.period}</span>
                </div>
                <div className="text-xs text-[#686D76] mt-1">{item.recipient_count} employees · {fmtSLE(item.total_amount_sle)}</div>
                <div className="text-xs text-[#686D76] mt-1">Payment date {item.payment_date} · prepared by {item.created_by}</div>
              </button>
            ))}
            {!batches.length && (
              <div className="text-sm text-[#686D76] border border-dashed border-[#E2DFD6] rounded-md p-5 text-center">
                No mobile money batches are waiting for approval.
              </div>
            )}
          </div>
        </section>

        <section className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
          {!batch ? (
            <div className="p-8 text-center text-sm text-[#686D76]">
              <Smartphone className="w-6 h-6 mx-auto mb-2 text-[#A1A5AB]" />
              Select a batch to review its recipients.
            </div>
          ) : (
            <>
              <div className="p-4 border-b border-[#E2DFD6] flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="font-heading text-lg font-semibold">{batch.provider_name} · {batch.period}</h2>
                  <p className="text-xs text-[#686D76] mt-1">
                    {batch.recipient_count} recipients · {fmtSLE(batch.total_amount_sle)} · {batch.payment_date} · {batch.currency}
                  </p>
                  <p className="text-xs text-[#686D76] mt-1">Prepared by {batch.created_by}</p>
                </div>
                {batch.status === "pending_approval" && batch.created_by !== user?.email && (
                  <button
                    data-testid="approve-mobile-money-batch"
                    onClick={approve}
                    disabled={busy}
                    className="inline-flex items-center gap-2 bg-[#17A035] hover:bg-[#148231] text-white px-4 py-2 rounded-md text-sm disabled:opacity-50"
                  >
                    <ShieldCheck className="w-4 h-4" /> {busy ? "Approving…" : "Approve batch"}
                  </button>
                )}
                {batch.created_by === user?.email && batch.status === "pending_approval" && (
                  <span className="text-xs text-[#8B6A14]">A different manager must approve this batch.</span>
                )}
                {batch.status !== "pending_approval" && (
                  <span className="text-xs uppercase tracking-wider text-[#17A035]">{batch.status.replaceAll("_", " ")}</span>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#F7F6F2]">
                    <tr>{["Employee", "Wallet number", "Amount (SLE)"].map((label) => (
                      <th key={label} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{label}</th>
                    ))}</tr>
                  </thead>
                  <tbody>
                    {(batch.recipients || []).map((recipient) => (
                      <tr key={recipient.id} className="border-t border-[#E2DFD6]">
                        <td className="py-2.5 px-4">{recipient.employee_name}</td>
                        <td className="py-2.5 px-4 font-data">{recipient.mobile_number}</td>
                        <td className="py-2.5 px-4 font-data">{fmtSLE(recipient.amount_sle)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
