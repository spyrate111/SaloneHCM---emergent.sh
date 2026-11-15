import { useEffect, useState } from "react";
import api from "../lib/api";
import {
  Shield, TrendingUp, ChevronRight, AlertTriangle, Check, Activity,
} from "lucide-react";

const GRADE_COLOR = {
  "A+": { bg: "from-[#17A035] to-[#117030]", ring: "#17A035", chip: "bg-[#E4F7E7] text-[#17A035]" },
  "A":  { bg: "from-[#17A035] to-[#117030]", ring: "#17A035", chip: "bg-[#E4F7E7] text-[#17A035]" },
  "B":  { bg: "from-[#26547C] to-[#1A3D5C]", ring: "#26547C", chip: "bg-[#E5EEF6] text-[#26547C]" },
  "C":  { bg: "from-[#8B6A14] to-[#6B4F0D]", ring: "#8B6A14", chip: "bg-[#FBF1DE] text-[#8B6A14]" },
  "D":  { bg: "from-[#D1603D] to-[#A8462B]", ring: "#D1603D", chip: "bg-[#FBE9DF] text-[#B84F2F]" },
  "F":  { bg: "from-[#3A7CB8] to-[#2C5E8E]", ring: "#3A7CB8", chip: "bg-[#E9F2FB] text-[#3A7CB8]" },
};

const GRADE_LABEL = {
  "A+": "Excellent",
  "A": "Excellent",
  "B": "Strong",
  "C": "Watch",
  "D": "Action needed",
  "F": "Critical",
};

const DIM_LABELS = {
  payroll_timeliness: { label: "NRA filing timeliness", icon: TrendingUp },
  nassit_accuracy: { label: "NASSIT contribution accuracy", icon: Check },
  sms_delivery: { label: "Payslip SMS delivery (30d)", icon: Activity },
  audit_coverage: { label: "Audit-log coverage (30d)", icon: Shield },
};

export default function ComplianceScoreWidget() {
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    api.get("/dashboard/compliance-score")
      .then((r) => setData(r.data))
      .catch(() => setData(null));
  }, []);

  if (!data) return null;
  const colors = GRADE_COLOR[data.grade] || GRADE_COLOR.C;
  const circumference = 2 * Math.PI * 36;
  const offset = circumference - (data.score / 100) * circumference;

  return (
    <section
      data-testid="compliance-score-widget"
      className={`rounded-xl overflow-hidden border border-[#E2DFD6] bg-gradient-to-br ${colors.bg} text-white`}
    >
      <div className="p-6 sm:p-7">
        <div className="flex items-start gap-6 flex-wrap">
          <div className="relative w-[100px] h-[100px] shrink-0">
            <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
              <circle cx="40" cy="40" r="36" stroke="rgba(255,255,255,0.15)" strokeWidth="6" fill="none" />
              <circle
                cx="40" cy="40" r="36"
                stroke="rgba(255,255,255,0.95)" strokeWidth="6" fill="none"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                strokeLinecap="round"
                style={{ transition: "stroke-dashoffset 1s ease-out" }}
              />
            </svg>
            <div className="absolute inset-0 grid place-items-center">
              <div>
                <div className="font-heading text-3xl font-bold leading-none">{data.score}</div>
                <div className="text-[9px] uppercase tracking-widest text-white/60 text-center mt-1">of 100</div>
              </div>
            </div>
          </div>
          <div className="flex-1 min-w-[200px]">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-white/60">
              <Shield className="w-3.5 h-3.5" strokeWidth={1.7} /> Compliance Score
            </div>
            <h2 className="font-heading text-2xl sm:text-3xl font-bold mt-1 flex items-center gap-3">
              Grade {data.grade}
              <span className={`text-[10px] uppercase tracking-wider font-medium px-2.5 py-1 rounded-full ${colors.chip}`}>
                {GRADE_LABEL[data.grade] || "Critical"}
              </span>
            </h2>
            <p className="text-white/75 text-sm mt-1.5 max-w-md leading-relaxed">
              Weighted across NRA filing, NASSIT accuracy, SMS delivery, and audit coverage — refreshed live each visit.
            </p>
          </div>
          <button
            data-testid="compliance-toggle"
            onClick={() => setExpanded((v) => !v)}
            className="inline-flex items-center gap-1.5 text-xs bg-white/10 hover:bg-white/15 backdrop-blur-sm border border-white/15 rounded-md px-3 py-2"
          >
            {expanded ? "Hide" : "View"} breakdown
            <ChevronRight className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-90" : ""}`} />
          </button>
        </div>

        {expanded && (
          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="compliance-breakdown">
            {Object.entries(data.breakdown).map(([k, p]) => {
              const meta = DIM_LABELS[k] || { label: k, icon: Shield };
              const Icon = meta.icon;
              const score = p.score ?? 0;
              const muted = p.applicable === false;
              return (
                <div key={k} className={`bg-white/8 backdrop-blur-sm border border-white/10 rounded-lg p-4 ${muted ? "opacity-50" : ""}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <Icon className="w-4 h-4 text-white/80" strokeWidth={1.6} />
                      {meta.label}
                    </div>
                    {muted ? (
                      <span className="text-[10px] uppercase tracking-wider text-white/50">N/A</span>
                    ) : (
                      <span className="font-data font-semibold text-base">{score}</span>
                    )}
                  </div>
                  {!muted && (
                    <div className="mt-2 h-1.5 bg-white/15 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-white/80 rounded-full"
                        style={{ width: `${score}%`, transition: "width 800ms ease-out" }}
                      />
                    </div>
                  )}
                  <p className="text-[11px] text-white/65 mt-2 leading-relaxed">{p.note}</p>
                </div>
              );
            })}
          </div>
        )}

        {!expanded && data.score < 70 && (
          <div className="mt-5 flex items-center gap-2 text-xs text-white/85 bg-white/8 rounded-md px-3 py-2 inline-flex">
            <AlertTriangle className="w-3.5 h-3.5 text-[#FBD3A4]" strokeWidth={1.7} />
            Some areas need attention — open the breakdown to see specifics.
          </div>
        )}
      </div>
    </section>
  );
}
