import { useEffect, useState } from "react";
import api from "../lib/api";
import { Lock } from "lucide-react";

/** Top-of-page banner shown when the tenant is in a payroll cutoff lock window.
 *  Renders nothing when unlocked or cutoff disabled. Anti-fraud: warns admins
 *  that no employee mutations are being accepted right now. */
export default function CutoffBanner() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get("/payroll/cutoff/status");
        setStatus(r.data);
      } catch { /* feature not available on this tenant — silently ignore */ }
    })();
  }, []);

  if (!status?.locked) return null;
  return (
    <div
      data-testid="cutoff-banner"
      className="bg-[#FBEAEA] border-b border-[#E9C2C2] px-6 py-2.5 flex items-center gap-2 text-sm text-[#8C2F2F]"
      role="alert"
    >
      <Lock className="w-4 h-4" strokeWidth={1.7} />
      <div className="flex-1">
        <strong>Payroll cutoff active</strong> —
        employee changes are locked until the <span className="font-data">{status.period}</span> payroll run is completed.
        Cutoff day: {status.cutoff_day}.
      </div>
    </div>
  );
}
