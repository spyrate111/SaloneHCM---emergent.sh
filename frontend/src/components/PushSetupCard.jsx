import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Bell, BellOff, Send, AlertCircle } from "lucide-react";
import {
  isPushSupported, currentSubscription, subscribePush, unsubscribePush, sendTestPush,
} from "../lib/push";

export default function PushSetupCard() {
  const supported = isPushSupported();
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!supported) return;
    currentSubscription().then((s) => setActive(!!s)).catch(() => setActive(false));
  }, [supported]);

  const enable = async () => {
    setBusy(true);
    try {
      await subscribePush();
      setActive(true);
      toast.success("Push notifications enabled on this device");
    } catch (e) {
      toast.error(e?.message || "Could not enable push notifications");
    } finally { setBusy(false); }
  };
  const disable = async () => {
    setBusy(true);
    try {
      await unsubscribePush();
      setActive(false);
      toast.success("Push notifications disabled");
    } catch (e) {
      toast.error("Could not disable");
    } finally { setBusy(false); }
  };
  const test = async () => {
    setBusy(true);
    try {
      const { data } = await sendTestPush();
      if (data?.sent > 0) toast.success(`Test push sent to ${data.sent} device${data.sent > 1 ? "s" : ""}`);
      else toast.error(data?.skipped || "No active subscription on this device");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not send test");
    } finally { setBusy(false); }
  };

  return (
    <section data-testid="push-setup-card" className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden">
      <div className="px-7 py-6 border-b border-[#F1EEE6] flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Mobile / Browser Notifications</div>
          <h2 className="font-heading text-2xl font-bold mt-1 flex items-center gap-2">
            Push notifications
            {active
              ? <span className="text-[10px] uppercase tracking-wider font-medium px-2 py-1 rounded-full bg-[#E4F7E7] text-[#17A035]">Enabled</span>
              : <span className="text-[10px] uppercase tracking-wider font-medium px-2 py-1 rounded-full bg-[#EBE8E0] text-[#525860]">Off</span>}
          </h2>
          <p className="text-sm text-[#525860] mt-2 max-w-2xl">
            Receive instant notifications when your payslip is published, a leave decision is made, or a performance review is completed — even when SaloneHCM is closed.
          </p>
        </div>
      </div>
      <div className="px-7 py-6 space-y-3">
        {!supported && (
          <div className="text-xs bg-[#FBF1DE] border border-[#E8D5A2] text-[#8B6A14] rounded-md px-3 py-2 inline-flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4" /> Browser does not support push notifications (try Chrome/Edge/Firefox on desktop or Android).
          </div>
        )}
        {supported && (
          <div className="flex items-center gap-2 flex-wrap">
            {!active ? (
              <button data-testid="push-enable" disabled={busy} onClick={enable} className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-4 py-2.5 rounded-md disabled:opacity-60">
                <Bell className="w-4 h-4" /> Enable on this device
              </button>
            ) : (
              <>
                <button data-testid="push-test" disabled={busy} onClick={test} className="inline-flex items-center gap-2 bg-[#26547C] hover:bg-[#1D4363] text-white text-sm px-4 py-2.5 rounded-md disabled:opacity-60">
                  <Send className="w-4 h-4" /> Send test
                </button>
                <button data-testid="push-disable" disabled={busy} onClick={disable} className="inline-flex items-center gap-2 bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#3A7CB8] text-sm px-3 py-2.5 rounded-md disabled:opacity-60">
                  <BellOff className="w-4 h-4" /> Disable
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
