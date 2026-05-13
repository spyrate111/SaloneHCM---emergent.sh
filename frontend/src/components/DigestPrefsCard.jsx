import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Bell, Mail, Save } from "lucide-react";
import api from "../lib/api";

export default function DigestPrefsCard() {
  const [prefs, setPrefs] = useState({ push: true, email: false });
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    api.get("/users/me/digest-prefs").then((r) => setPrefs(r.data)).catch(() => {});
  }, []);

  const toggle = (k) => { setPrefs((p) => ({ ...p, [k]: !p[k] })); setDirty(true); };

  const save = async () => {
    setBusy(true);
    try {
      await api.put("/users/me/digest-prefs", prefs);
      toast.success("Digest preferences saved");
      setDirty(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save");
    } finally { setBusy(false); }
  };

  return (
    <section data-testid="digest-prefs-card" className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden">
      <div className="px-7 py-6 border-b border-[#F1EEE6]">
        <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Daily Digest</div>
        <h2 className="font-heading text-2xl font-bold mt-1">Notification preferences</h2>
        <p className="text-sm text-[#525860] mt-2 max-w-2xl">
          The daily digest runs every morning at 07:00 UTC, summarising pending leaves, payroll runs due in 72 hours, outstanding NRA filings, and reviews awaiting manager input.
        </p>
      </div>
      <div className="px-7 py-6 space-y-3">
        <PrefRow
          icon={Bell}
          label="Web push notification"
          desc="Real-time popup on your devices subscribed for push notifications."
          checked={prefs.push}
          onChange={() => toggle("push")}
          testId="digest-push-toggle"
        />
        <PrefRow
          icon={Mail}
          label="Email summary"
          desc="HTML email summary sent to your account email each morning."
          checked={prefs.email}
          onChange={() => toggle("email")}
          testId="digest-email-toggle"
        />
        <div className="flex justify-end pt-2">
          <button
            data-testid="digest-prefs-save"
            disabled={!dirty || busy}
            onClick={save}
            className="inline-flex items-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white text-sm px-4 py-2 rounded-md disabled:opacity-50"
          >
            <Save className="w-4 h-4" /> Save preferences
          </button>
        </div>
      </div>
    </section>
  );
}

function PrefRow({ icon: Icon, label, desc, checked, onChange, testId }) {
  return (
    <label className="flex items-start justify-between gap-4 p-3 border border-[#E2DFD6] rounded-md hover:bg-[#FDFCFB] cursor-pointer">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-md bg-[#F7F6F2] grid place-items-center flex-shrink-0">
          <Icon className="w-4 h-4 text-[#26547C]" strokeWidth={1.5} />
        </div>
        <div>
          <div className="text-sm font-medium">{label}</div>
          <div className="text-xs text-[#686D76] mt-0.5">{desc}</div>
        </div>
      </div>
      <input data-testid={testId} type="checkbox" checked={checked} onChange={onChange} className="w-4 h-4 mt-2.5 accent-[#133326]" />
    </label>
  );
}
