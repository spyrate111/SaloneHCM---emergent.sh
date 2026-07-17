import { useCallback, useEffect, useState } from "react";
import { MessageSquare, Send, X, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";

/** Super-admin quick-action: send a single test SMS through the live Twilio integration
 *  to verify credentials, region permissions, and delivery pipeline are healthy.
 *  Uses POST /api/integrations/sms/test — global (Twilio config is app-wide, not per-tenant). */
export default function TwilioTestButton() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState(null);   // /integrations/status payload
  const [to, setTo] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);   // {ok, sid, status, to} | {ok:false, error}

  const loadStatus = useCallback(async () => {
    try {
      const r = await api.get("/integrations/status");
      setStatus(r.data);
    } catch (e) {
      // Non-critical — just means we don't show the configured indicator up front.
      if (typeof console !== "undefined") console.warn("integrations status fetch failed", e);
    }
  }, []);

  useEffect(() => { if (open) loadStatus(); }, [open, loadStatus]);

  const close = () => {
    if (busy) return;
    setOpen(false);
    setResult(null);
    setTo("");
    setBody("");
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!to.trim()) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await api.post("/integrations/sms/test", {
        to: to.trim(),
        body: body.trim() || undefined,
      });
      setResult({ ok: true, ...r.data });
      toast.success(`SMS sent — SID ${r.data.sid?.slice(0, 8)}…`);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Send failed";
      const message = typeof detail === "string" ? detail : JSON.stringify(detail);
      setResult({ ok: false, error: message, code: err?.response?.status });
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  const twilioConfigured = status?.twilio?.configured;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="sms-test-open"
        className="inline-flex items-center gap-2 bg-white hover:bg-[#F1EEE6] text-[#0A4A1E] text-sm px-4 py-2.5 rounded-md border border-[#E2DFD6] transition"
      >
        <MessageSquare className="w-4 h-4" strokeWidth={1.5} /> Test Twilio SMS
      </button>

      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4"
          data-testid="sms-test-modal"
          onClick={close}
        >
          <form
            onSubmit={submit}
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-lg p-6 space-y-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Integration diagnostics</div>
                <h3 className="font-heading text-lg font-semibold mt-0.5">Send test SMS via Twilio</h3>
              </div>
              <button type="button" onClick={close} className="text-[#525860]" aria-label="Close" data-testid="sms-test-cancel">
                <X className="w-4 h-4" />
              </button>
            </div>

            {status && (
              <div
                data-testid="sms-test-status"
                className={`text-xs px-3 py-2 rounded-md inline-flex items-center gap-1.5 ${
                  twilioConfigured
                    ? "bg-[#EDF8EE] text-[#17A035] border border-[#BFEBC8]"
                    : "bg-[#FBEBDF] text-[#8C4A2F] border border-[#F1C3A1]"
                }`}
              >
                {twilioConfigured
                  ? <><CheckCircle2 className="w-3.5 h-3.5" /> Twilio is configured</>
                  : <><AlertTriangle className="w-3.5 h-3.5" /> Twilio credentials not detected in backend .env</>
                }
              </div>
            )}

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Recipient (E.164)</label>
              <input
                data-testid="sms-test-phone"
                required
                value={to}
                onChange={(e) => setTo(e.target.value)}
                placeholder="+23276123456"
                className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data"
              />
              <p className="text-[11px] text-[#686D76] mt-1">
                Must start with country code, e.g. <code className="font-data">+232</code> for Sierra Leone.
                For sandbox testing use Twilio&rsquo;s virtual number <code className="font-data">+18777804236</code>.
              </p>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">
                Message (optional, max 320 chars)
              </label>
              <textarea
                data-testid="sms-test-body"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                maxLength={320}
                rows={3}
                placeholder="Defaults to: SaloneHCM: Test SMS from <you> — Twilio integration is working."
                className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
              />
              <div className="text-[11px] text-[#686D76] mt-0.5 text-right">{body.length}/320</div>
            </div>

            {result && (
              <div
                data-testid="sms-test-result"
                className={`text-xs px-3 py-2.5 rounded-md border ${
                  result.ok
                    ? "bg-[#EDF8EE] text-[#17A035] border-[#BFEBC8]"
                    : "bg-[#FBEBDF] text-[#8C4A2F] border-[#F1C3A1]"
                }`}
              >
                {result.ok ? (
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5 font-semibold">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Sent — status <code className="font-data">{result.status}</code>
                    </div>
                    <div className="font-data text-[11px] text-[#525860]">
                      SID: {result.sid} · to {result.to}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5 font-semibold">
                      <XCircle className="w-3.5 h-3.5" /> Failed{result.code ? ` (HTTP ${result.code})` : ""}
                    </div>
                    <div className="text-[11px]">{result.error}</div>
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#F1EEE6]">
              <button
                type="button"
                onClick={close}
                className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]"
              >
                Close
              </button>
              <button
                type="submit"
                disabled={busy || !to.trim()}
                data-testid="sms-test-submit"
                className="inline-flex items-center gap-2 text-sm bg-[#0A4A1E] hover:bg-[#063514] disabled:opacity-60 text-white px-4 py-2 rounded-md"
              >
                <Send className="w-4 h-4" strokeWidth={1.7} /> {busy ? "Sending…" : "Send test SMS"}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
