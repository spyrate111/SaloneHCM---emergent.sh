import { useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { MessageSquare, X, Check, AlertCircle, SkipForward, Send } from "lucide-react";

const STATUS_PILL = {
  sent: { color: "bg-[#E6F4EC] text-[#2D7A5D]", icon: Check, label: "Sent" },
  would_send: { color: "bg-[#E5EEF6] text-[#26547C]", icon: Send, label: "Would send" },
  failed: { color: "bg-[#FBEAEA] text-[#B83A3A]", icon: AlertCircle, label: "Failed" },
  skipped: { color: "bg-[#FBF1DE] text-[#8B6A14]", icon: SkipForward, label: "Skipped" },
};

export default function SmsPayslipButton({ run }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [twilioConfigured, setTwilioConfigured] = useState(null);

  const openModal = async () => {
    setOpen(true);
    setResult(null);
    try {
      const r = await api.get("/payroll/sms/status");
      setTwilioConfigured(r.data.twilio_configured);
    } catch {
      setTwilioConfigured(false);
    }
  };

  const send = async (dry) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/payroll/runs/${run.id}/send-sms`, { dry_run: dry });
      setResult(data);
      if (dry) toast.success(`Dry run completed — ${data.would_send + data.sent} ready, ${data.skipped} skipped`);
      else toast.success(`SMS batch sent — ${data.sent} delivered, ${data.failed} failed`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "SMS send failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        data-testid={`sms-btn-${run.id}`}
        onClick={openModal}
        className="inline-flex items-center gap-1 text-xs bg-[#133326] hover:bg-[#0F281E] text-white px-2.5 py-1.5 rounded"
        title="Send payslip SMS to all employees in this run"
      >
        <MessageSquare className="w-3.5 h-3.5" /> SMS payslips
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => !busy && setOpen(false)}>
          <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-lg w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto" data-testid="sms-modal">
            <SmsModalHeader period={run.period} onClose={() => !busy && setOpen(false)} />
            {twilioConfigured === false && <TwilioConfigBanner />}
            {!result && (
              <SmsActions
                busy={busy}
                twilioConfigured={twilioConfigured}
                employeeCount={run.totals.employee_count}
                onSend={send}
              />
            )}
            {result && (
              <SmsResultPanel
                result={result}
                onReset={() => setResult(null)}
                onClose={() => setOpen(false)}
              />
            )}
          </div>
        </div>
      )}
    </>
  );
}

function SmsModalHeader({ period, onClose }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Bulk SMS · Gov tier</div>
        <h3 className="font-heading text-xl font-semibold mt-1">Payslip SMS — {period}</h3>
        <p className="text-xs text-[#525860] mt-1">
          Each employee with a valid Sierra Leone phone (+232…) will receive their net pay for this period.
        </p>
      </div>
      <button onClick={onClose} className="text-[#525860]"><X className="w-4 h-4" /></button>
    </div>
  );
}

function TwilioConfigBanner() {
  return (
    <div className="text-xs bg-[#FBF1DE] border border-[#E8D5A2] text-[#8B6A14] rounded-md p-3 mb-4">
      ⚠️ <strong>Twilio is not configured.</strong> All sends will run in dry-run mode (no SMS actually delivered) until <code className="bg-white px-1 rounded">TWILIO_ACCOUNT_SID</code>, <code className="bg-white px-1 rounded">TWILIO_AUTH_TOKEN</code>, and <code className="bg-white px-1 rounded">TWILIO_FROM_NUMBER</code> are added to <code className="bg-white px-1 rounded">backend/.env</code>.
    </div>
  );
}

function SmsActions({ busy, twilioConfigured, employeeCount, onSend }) {
  return (
    <div className="flex gap-2 flex-wrap">
      <button
        data-testid="sms-dry-run"
        disabled={busy}
        onClick={() => onSend(true)}
        className="inline-flex items-center gap-1.5 text-sm border border-[#26547C] text-[#26547C] hover:bg-[#E5EEF6] px-4 py-2 rounded-md disabled:opacity-60"
      >
        <Send className="w-3.5 h-3.5" /> {busy ? "Computing…" : "Dry run (preview only)"}
      </button>
      {twilioConfigured && (
        <button
          data-testid="sms-live-send"
          disabled={busy}
          onClick={() => { if (window.confirm(`Send live SMS to ${employeeCount} employees? This will incur Twilio charges.`)) onSend(false); }}
          className="inline-flex items-center gap-1.5 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2 rounded-md disabled:opacity-60"
        >
          <MessageSquare className="w-3.5 h-3.5" /> {busy ? "Sending…" : `Send live to ${employeeCount} employees`}
        </button>
      )}
    </div>
  );
}

function SmsResultPanel({ result, onReset, onClose }) {
  return (
    <div data-testid="sms-result" className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <KPI label={result.dry_run ? "Would send" : "Sent"} value={result.dry_run ? result.would_send : result.sent} color="text-[#2D7A5D]" />
        <KPI label="Failed" value={result.failed} color="text-[#B83A3A]" />
        <KPI label="Skipped" value={result.skipped} color="text-[#8B6A14]" />
        <KPI label="Total" value={result.total} color="text-[#1A1C1E]" />
      </div>
      {result.dry_run && (
        <div className="text-xs text-[#525860] bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-2.5">
          This was a <strong>dry run</strong>. No SMS were actually delivered.
        </div>
      )}
      <SmsResultTable results={result.results} />
      <div className="flex justify-end gap-2 pt-2">
        <button onClick={onReset} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Run again</button>
        <button onClick={onClose} className="text-sm bg-[#133326] text-white px-4 py-2 rounded-md">Close</button>
      </div>
    </div>
  );
}

function SmsResultTable({ results }) {
  return (
    <div className="border border-[#E2DFD6] rounded-md max-h-64 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="bg-[#F7F6F2] sticky top-0">
          <tr>{["Recipient", "Phone", "Status", "Note"].map((h) => (
            <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2 px-3 font-medium">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {results.map((r, i) => {
            const pill = STATUS_PILL[r.status] || STATUS_PILL.skipped;
            const Icon = pill.icon;
            return (
              <tr key={`${r.employee_id}-${i}`} className="border-t border-[#E2DFD6]">
                <td className="py-2 px-3">{r.name || "—"}</td>
                <td className="py-2 px-3 font-data text-xs">{r.phone || "—"}</td>
                <td className="py-2 px-3">
                  <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-full ${pill.color}`}>
                    <Icon className="w-3 h-3" /> {pill.label}
                  </span>
                </td>
                <td className="py-2 px-3 text-xs text-[#686D76]">{r.reason || (r.sid && r.sid.slice(0, 12) + "…") || "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function KPI({ label, value, color }) {
  return (
    <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-3">
      <div className="text-[10px] uppercase tracking-wider text-[#525860]">{label}</div>
      <div className={`font-heading text-2xl font-bold mt-1 font-data ${color}`}>{value ?? 0}</div>
    </div>
  );
}
