import { Check, X, Sparkles } from "lucide-react";

export default function ApprovalBanner({ scenario, onDecide, onApply, onClose }) {
  const bgClass = scenario.approval_status === "approved" ? "bg-[#E6F4EC] border-[#2D7A5D]"
    : scenario.approval_status === "rejected" ? "bg-[#FBEAEA] border-[#B83A3A]"
    : scenario.approval_status === "pending" ? "bg-[#FBF1DE] border-[#8B6A14]"
    : "bg-[#F7F6F2] border-[#525860]";
  return (
    <div className={`rounded-lg p-5 border-l-4 ${bgClass}`} data-testid="approval-banner">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">
            Saved scenario · {scenario.approval_status}{scenario.applied ? " · APPLIED" : ""}
          </div>
          <h2 className="font-heading text-xl font-semibold mt-1">{scenario.title}</h2>
          {scenario.description && <p className="text-sm text-[#525860] mt-1">{scenario.description}</p>}
          <div className="text-xs text-[#686D76] mt-2 space-x-3 font-data">
            <span>Created by {scenario.created_by}</span>
            <span>·</span>
            <span>{new Date(scenario.created_at).toLocaleString()}</span>
            {scenario.approver_email && <><span>·</span><span>Approver: {scenario.approver_email}</span></>}
            {scenario.approved_by && <><span>·</span><span>{scenario.approval_status} by {scenario.approved_by}</span></>}
          </div>
          {scenario.approval_notes && <p className="text-sm italic text-[#525860] mt-2">&ldquo;{scenario.approval_notes}&rdquo;</p>}
        </div>
        <div className="flex gap-2 flex-wrap">
          {scenario.approval_status === "pending" && (
            <>
              <button data-testid="reject-scenario" onClick={() => onDecide("rejected")} className="inline-flex items-center gap-1.5 text-sm border border-[#B83A3A] text-[#B83A3A] hover:bg-[#FBEAEA] px-3 py-2 rounded-md"><X className="w-3.5 h-3.5" /> Reject</button>
              <button data-testid="approve-scenario" onClick={() => onDecide("approved")} className="inline-flex items-center gap-1.5 text-sm bg-[#2D7A5D] hover:bg-[#256449] text-white px-4 py-2 rounded-md"><Check className="w-3.5 h-3.5" /> Approve</button>
            </>
          )}
          {scenario.approval_status === "approved" && !scenario.applied && (
            <button data-testid="apply-scenario" onClick={onApply} className="inline-flex items-center gap-1.5 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2 rounded-md font-medium">
              <Sparkles className="w-3.5 h-3.5" /> Apply changes to employees
            </button>
          )}
          {scenario.applied && (
            <span className="inline-flex items-center gap-1.5 text-sm bg-[#2D7A5D] text-white px-3 py-2 rounded-md">
              <Check className="w-3.5 h-3.5" /> Applied {scenario.applied_at ? new Date(scenario.applied_at).toLocaleDateString() : ""}
            </span>
          )}
          <button onClick={onClose} className="inline-flex items-center gap-1.5 text-sm border border-[#E2DFD6] hover:bg-[#F7F6F2] px-3 py-2 rounded-md text-[#525860]"><X className="w-3.5 h-3.5" /> Close</button>
        </div>
      </div>
    </div>
  );
}
