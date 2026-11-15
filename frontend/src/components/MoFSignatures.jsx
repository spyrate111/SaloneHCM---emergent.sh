import { useCallback, useEffect, useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import {
  X, ShieldCheck, CheckCircle2, XCircle, Loader2, PenTool, User,
} from "lucide-react";

/** Multi-signature MoF approval progress + sign action.
 *  Opens as a modal, shows the signature chain (n/k signed), lists all
 *  existing signatures, and lets the current user sign if they haven't yet
 *  and are an mof_approver or superadmin. */
export function MoFSignaturesButton({ runId, mofStatus, onUpdated }) {
  const [open, setOpen] = useState(false);
  if (!["submitted", "partially_signed", "approved", "rejected"].includes(mofStatus)) return null;
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        data-testid={`mof-sig-open-${runId}`}
        className="inline-flex items-center gap-1 text-xs bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#26547C] px-2.5 py-1.5 rounded"
      >
        <PenTool className="w-3.5 h-3.5" /> Signatures
      </button>
      {open && (
        <MoFSignaturesModal
          runId={runId}
          onClose={() => { setOpen(false); if (onUpdated) onUpdated(); }}
        />
      )}
    </>
  );
}

function MoFSignaturesModal({ runId, onClose }) {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(true);
  const [signing, setSigning] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const r = await api.get(`/civil-service/mof/runs/${runId}/signatures`);
      setData(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load signatures");
      onClose();
    } finally { setBusy(false); }
  }, [runId, onClose]);

  useEffect(() => { load(); }, [load]);

  const sign = async (action) => {
    let note = "";
    if (action === "reject") {
      note = window.prompt("Rejection reason? (required)") || "";
      if (!note) return;
    } else {
      note = window.prompt("Approval note (optional)?", "") || "";
    }
    setSigning(true);
    try {
      const r = await api.post(`/civil-service/mof/runs/${runId}/sign`, { action, note });
      toast.success(`Signature recorded — status is now '${r.data.mof_status}'`);
      setData({
        ...data,
        signatures: r.data.signatures,
        mof_status: r.data.mof_status,
      });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Sign failed");
    } finally { setSigning(false); }
  };

  const alreadySigned = data?.signatures?.some((s) => s.signer_email === user?.email);
  const canSign = data && !alreadySigned
    && ["submitted", "partially_signed"].includes(data.mof_status)
    && (user?.mof_approver || user?.role === "superadmin");

  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" data-testid="mof-sig-modal">
      <div className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="px-6 py-5 border-b border-[#E2DFD6] flex items-start justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Anti-fraud rail — Multi-sig approval</div>
            <h2 className="font-heading text-xl font-bold mt-0.5">MoF signature chain</h2>
          </div>
          <button onClick={onClose} className="text-[#525860]" data-testid="mof-sig-close"><X className="w-4 h-4" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {busy && <div className="text-center py-10"><Loader2 className="w-6 h-6 animate-spin mx-auto text-[#0A4A1E]" /></div>}
          {data && (
            <>
              <ProgressBar
                approves={data.signatures.filter((s) => s.action === "approve").length}
                rejects={data.signatures.filter((s) => s.action === "reject").length}
                required={data.signatures_required}
                mofStatus={data.mof_status}
              />
              <SignatureList signatures={data.signatures} mofStatus={data.mof_status} />
              {canSign && (
                <div className="border-t border-[#F1EEE6] pt-4 flex items-center justify-end gap-2" data-testid="mof-sig-actions">
                  <button
                    onClick={() => sign("reject")}
                    disabled={signing}
                    data-testid="mof-sig-reject"
                    className="inline-flex items-center gap-1.5 text-sm bg-white border border-[#C2D9E9] text-[#2F6390] hover:bg-[#E9F2FB] px-4 py-2 rounded-md disabled:opacity-60"
                  >
                    <XCircle className="w-4 h-4" /> Reject
                  </button>
                  <button
                    onClick={() => sign("approve")}
                    disabled={signing}
                    data-testid="mof-sig-approve"
                    className="inline-flex items-center gap-2 text-sm bg-[#17A035] hover:bg-[#127530] disabled:opacity-60 text-white px-4 py-2 rounded-md"
                  >
                    {signing ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />} Sign approval
                  </button>
                </div>
              )}
              {alreadySigned && (
                <div className="text-xs bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2 text-[#525860]" data-testid="mof-sig-already-signed">
                  You have already signed this run.
                </div>
              )}
              {!canSign && !alreadySigned && (user?.mof_approver || user?.role === "superadmin") && (
                <div className="text-xs bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2 text-[#525860]">
                  Signing is only available while status is <code className="font-data">submitted</code> or <code className="font-data">partially_signed</code>.
                </div>
              )}
              {!user?.mof_approver && user?.role !== "superadmin" && (
                <div className="text-xs bg-[#FBF1DE] border border-[#E8D5A2] rounded-md px-3 py-2 text-[#8B6A14]" data-testid="mof-sig-not-approver">
                  You do not have the mof_approver flag — read-only view.
                </div>
              )}
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

function ProgressBar({ approves, rejects, required, mofStatus }) {
  const showRejected = rejects > 0 || mofStatus === "rejected";
  const complete = approves >= required && !showRejected;
  const pct = Math.min(100, (approves / required) * 100);
  let tone = { text: "text-[#8B6A14]", bar: "bg-[#D1603D]", label: `${approves} of ${required}`, width: pct };
  if (showRejected) tone = { text: "text-[#2F6390]", bar: "bg-[#3A7CB8]", label: "Rejected", width: 100 };
  else if (complete) tone = { text: "text-[#17A035]", bar: "bg-[#17A035]", label: "Approved", width: pct };
  return (
    <div data-testid="mof-sig-progress">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[11px] uppercase tracking-wider text-[#525860]">
          {required} signature{required === 1 ? "" : "s"} required
        </div>
        <div className={`text-sm font-semibold ${tone.text}`}>{tone.label}</div>
      </div>
      <div className="h-2.5 bg-[#F1EEE6] rounded-full overflow-hidden">
        <div className={`h-full transition-all ${tone.bar}`} style={{ width: `${tone.width}%` }} />
      </div>
    </div>
  );
}

function SignatureList({ signatures, mofStatus }) {
  if (!signatures || signatures.length === 0) {
    if (mofStatus === "approved") {
      return (
        <div className="text-sm text-[#525860] bg-[#E4F7E7] border border-[#BFEBC8] rounded-md px-3 py-3" data-testid="mof-sig-legacy-approved">
          This run was approved via the legacy single-signature flow. No signature-chain records exist.
        </div>
      );
    }
    if (mofStatus === "rejected") {
      return (
        <div className="text-sm text-[#525860] bg-[#E9F2FB] border border-[#C2D9E9] rounded-md px-3 py-3" data-testid="mof-sig-legacy-rejected">
          This run was rejected via the legacy single-signature flow. No signature-chain records exist.
        </div>
      );
    }
    return (
      <div className="text-sm text-[#525860] bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-3" data-testid="mof-sig-empty">
        No signatures yet. This run is awaiting the first MoF approver.
      </div>
    );
  }
  return (
    <ul className="space-y-1.5" data-testid="mof-sig-list">
      {signatures.map((s) => (
        <li
          key={s.id}
          data-testid={`mof-sig-entry-${s.id}`}
          className={`px-3 py-2.5 rounded-md border flex items-start gap-3 ${
            s.action === "approve"
              ? "bg-[#E4F7E7] border-[#BFEBC8]"
              : "bg-[#E9F2FB] border-[#C2D9E9]"
          }`}
        >
          <div className={s.action === "approve" ? "text-[#17A035]" : "text-[#2F6390]"}>
            {s.action === "approve" ? <CheckCircle2 className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <div className="font-semibold text-sm text-[#1A1C1E]">{s.signer_name || s.signer_email}</div>
              <span className="text-[10px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded-full bg-white border border-[#E2DFD6] text-[#525860]">
                {s.signer_role}
              </span>
              <span className="text-[11px] text-[#525860] font-data">· {new Date(s.signed_at).toLocaleString()}</span>
            </div>
            {s.note && <div className="text-xs mt-1 italic text-[#525860]">&ldquo;{s.note}&rdquo;</div>}
          </div>
          <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full font-semibold ${
            s.action === "approve" ? "bg-[#BFEBC8] text-[#17A035]" : "bg-[#C2D9E9] text-[#2F6390]"
          }`}>
            {s.action}
          </span>
        </li>
      ))}
    </ul>
  );
}
