import { useEffect, useState } from "react";
import api from "../lib/api";
import { Mail, ShieldAlert, MapPinOff, GraduationCap } from "lucide-react";

const Stat = ({ icon: Icon, label, value, names, tone, testId }) => (
  <div className="flex-1 min-w-[150px] rounded-md border border-[#E2DFD6] p-3" data-testid={testId}>
    <div className="flex items-center gap-2">
      <Icon className={`w-4 h-4 ${tone}`} strokeWidth={1.75} />
      <span className="font-data text-xl font-bold text-[#1A1C1E]" data-testid={`${testId}-count`}>{value}</span>
    </div>
    <div className="text-[11px] text-[#525860] mt-1">{label}</div>
    {names?.length > 0 && (
      <div className="text-[10px] text-[#8A8F96] mt-0.5 truncate">
        {names.slice(0, 3).join(", ")}{names.length > 3 ? ` +${names.length - 3}` : ""}
      </div>
    )}
  </div>
);

export const DigestPreviewCard = () => {
  const [snap, setSnap] = useState(null);
  const [at, setAt] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () => api.get("/users/me/digest-preview").then((r) => {
      if (alive) { setSnap(r.data); setAt(new Date()); }
    }).catch(() => {});
    load();
    const t = setInterval(load, 60000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (!snap) return null;
  const scans = snap.scan_alerts || [];
  const ooz = snap.ooz_punches || [];

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-5" data-testid="digest-preview-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <Mail className="w-4 h-4 text-[#26547C]" strokeWidth={1.75} />
          <div>
            <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Tonight&rsquo;s digest preview</div>
            <div className="text-xs text-[#686D76]">What the end-of-day digest email will contain</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-[#8A8F96]" data-testid="digest-preview-updated">
          <span className="w-1.5 h-1.5 rounded-full bg-[#17A035] animate-pulse" />
          live · {at ? at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <Stat icon={ShieldAlert} tone="text-[#B03A2E]" label="Flagged payslip scans" value={scans.length}
              names={scans.map((s) => s.employee_name)} testId="digest-preview-scans" />
        <Stat icon={MapPinOff} tone="text-[#8B6A14]" label="Out-of-zone punches" value={ooz.length}
              names={ooz.map((o) => o.employee_name)} testId="digest-preview-ooz" />
        <Stat icon={GraduationCap} tone="text-[#26547C]" label="Training nudges sent" value={snap.training_nudges_sent || 0}
              testId="digest-preview-nudges" />
      </div>
    </div>
  );
};

export default DigestPreviewCard;
