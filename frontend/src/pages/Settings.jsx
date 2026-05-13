import { useEffect, useState } from "react";
import api from "../lib/api";
import { useFeatures, TIER_COLORS, TIER_DESCRIPTIONS } from "../lib/features";
import { Target, Globe, Briefcase, Building2, Check, Lock, Sparkles } from "lucide-react";
import TwoFactorCard from "../components/TwoFactorCard";
import TransparencyCard from "../components/TransparencyCard";
import PushSetupCard from "../components/PushSetupCard";
import DigestPrefsCard from "../components/DigestPrefsCard";

const FEATURE_LABELS = {
  employees: "Employee directory & profiles",
  payroll: "Payroll engine (PAYE + NASSIT)",
  compliance: "NRA / NASSIT compliance & exports",
  leave: "Leave requests & approvals",
  attendance: "Time & attendance tracking",
  self_service: "Employee self-service portal",
  benefits: "Benefits administration",
  talent: "Talent: jobs, applicants, training",
  documents: "Document Vault",
  ai_assistant: "AI Assistant (chat)",
  ai_context: "AI live-data context",
  team_view: "Manager Self-Service",
  audit_log: "Audit log",
  analytics: "Advanced analytics dashboards",
  simulator: "What-if payroll simulator",
  scenarios: "Saved scenarios & approval workflow",
  scenario_compare: "Side-by-side scenario comparison",
  decision_brief_pdf: "Decision Brief PDF export",
  ai_action_mode: "AI Action Mode (execute HR tasks)",
  gov_payroll: "Government payroll module",
  ministry_reports: "Ministry-level reporting",
  bulk_sms_payslips: "Bulk SMS payslip delivery",
  nra_export: "Automated NRA filing export",
};

const ALL_FEATURE_ORDER = Object.keys(FEATURE_LABELS);

export default function Settings() {
  const { company: authCompany, tier: authTier, has: authHas } = useFeatures();
  const [allTiers, setAllTiers] = useState([]);
  const [company, setCompany] = useState(authCompany || null);

  useEffect(() => {
    api.get("/company/tiers").then((r) => setAllTiers(r.data)).catch(() => {});
    api.get("/company").then((r) => setCompany(r.data)).catch(() => {});
  }, []);

  const tier = company?.tier || authTier;
  const has = (f) => (company?.features ? company.features.includes(f) : authHas(f));
  const tierColor = TIER_COLORS[tier] || TIER_COLORS.lite;

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Settings</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Organization</h1>
      </div>

      {/* Mission */}
      <section
        data-testid="mission-statement"
        className="relative overflow-hidden rounded-xl border border-[#E2DFD6] bg-gradient-to-br from-[#133326] via-[#0F281E] to-[#133326] text-white"
      >
        <div className="absolute -top-16 -right-16 w-64 h-64 rounded-full bg-[#D1603D]/20 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-12 -left-12 w-56 h-56 rounded-full bg-[#26547C]/25 blur-3xl pointer-events-none" />
        <div className="relative p-7 sm:p-9">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-white/60">
            <Target className="w-3.5 h-3.5" strokeWidth={1.7} /> Our Mission
          </div>
          <p className="mt-4 font-heading text-[20px] sm:text-[22px] leading-[1.5] max-w-4xl text-white/95">
            Build a cloud-based, enterprise-grade <span className="text-[#F0B47B] font-semibold">Human Capital Management (HCM)</span> and
            payroll platform tailored specifically to Sierra Leone’s labor laws, tax framework, and financial regulations —
            offering the same depth and feature parity as <span className="text-white">ADP&nbsp;Workforce&nbsp;Now, Gusto, Sure&nbsp;Payroll, Paychex&nbsp;Flex,</span> and
            <span className="text-white"> Rippling</span> — but localized for Sierra Leonean businesses of all sizes, from SMEs to
            large enterprises all around the country and the Government of Sierra Leone.
          </p>
          <div className="mt-7 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-3xl">
            <Pillar icon={Globe} label="Localized for Sierra Leone" sub="NRA · NASSIT · Employment Act 2023" />
            <Pillar icon={Briefcase} label="Enterprise depth" sub="Parity with ADP, Gusto, Rippling" />
            <Pillar icon={Building2} label="SMEs to Government" sub="From Bo to Freetown · GovTier ready" />
          </div>
        </div>
      </section>

      {/* Current plan */}
      <section data-testid="current-plan" className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden">
        <div className="px-7 py-6 flex flex-wrap items-start justify-between gap-4 border-b border-[#F1EEE6]">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Current plan</div>
            <div className="flex items-center gap-3 mt-2">
              <Sparkles className="w-5 h-5 text-[#D1603D]" strokeWidth={1.6} />
              <h2 className="font-heading text-2xl font-bold">{company?.label || "SaloneHCM"}</h2>
              <span className={`text-[10px] uppercase tracking-wider font-medium px-2.5 py-1 rounded-full ${tierColor}`} data-testid="tier-pill">
                {tier}
              </span>
            </div>
            <p className="text-sm text-[#525860] mt-2 max-w-2xl">
              {TIER_DESCRIPTIONS[tier] || "Custom plan."}
            </p>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wider text-[#525860]">Active features</div>
            <div className="font-heading text-3xl font-bold mt-1 font-data">
              {company?.features?.length || 0}
              <span className="text-base text-[#A1A5AB] font-normal"> / {ALL_FEATURE_ORDER.length}</span>
            </div>
          </div>
        </div>

        <div className="px-7 py-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5" data-testid="feature-list">
            {ALL_FEATURE_ORDER.map((f) => {
              const enabled = has(f);
              return (
                <div
                  key={f}
                  data-testid={`feature-${f}`}
                  className={`flex items-center gap-2.5 px-3 py-2 rounded-md border text-sm ${
                    enabled ? "border-[#9CC8B1] bg-[#E6F4EC] text-[#133326]" : "border-[#E2DFD6] bg-[#F7F6F2] text-[#A1A5AB]"
                  }`}
                >
                  {enabled
                    ? <Check className="w-4 h-4 text-[#2D7A5D] shrink-0" strokeWidth={2} />
                    : <Lock className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />}
                  <span className="text-[13px]">{FEATURE_LABELS[f]}</span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Tier ladder */}
      {allTiers.length > 0 && (
        <section data-testid="tier-ladder" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {allTiers.map((t) => {
            const isCurrent = t.id === tier;
            const color = TIER_COLORS[t.id] || TIER_COLORS.lite;
            return (
              <div
                key={t.id}
                data-testid={`tier-card-${t.id}`}
                className={`relative bg-white border rounded-xl p-5 ${isCurrent ? "border-[#133326] shadow-md" : "border-[#E2DFD6]"}`}
              >
                {isCurrent && (
                  <span className="absolute -top-2.5 right-4 text-[9px] uppercase tracking-widest font-semibold bg-[#133326] text-white px-2 py-1 rounded-full">
                    Current
                  </span>
                )}
                <span className={`inline-block text-[10px] uppercase tracking-wider font-medium px-2 py-0.5 rounded-full ${color}`}>
                  {t.id}
                </span>
                <h3 className="font-heading font-semibold text-lg mt-3">{t.label}</h3>
                <p className="text-xs text-[#525860] mt-1 leading-relaxed">{TIER_DESCRIPTIONS[t.id]}</p>
                <div className="mt-3 text-[11px] text-[#686D76] font-data">{t.features.length} features included</div>
              </div>
            );
          })}
        </section>
      )}

      <TwoFactorCard />

      <PushSetupCard />

      <DigestPrefsCard />

      {has("ministry_reports") && <TransparencyCard />}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="company-card">
          <h3 className="font-heading text-lg font-semibold">Company</h3>
          <dl className="mt-4 space-y-3 text-sm font-data">
            {[
              ["Legal name", company?.name || "—"],
              ["TIN", company?.tin || "—"],
              ["NASSIT employer", company?.nassit_employer || "—"],
              ["Country", company?.country || "Sierra Leone"],
              ["Tier", company?.label || "—"],
              ["Active headcount", company?.active_headcount ?? "—"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-[#F1EEE6] pb-2 last:border-0">
                <dt className="text-[#525860]">{k}</dt>
                <dd className="font-medium">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <h3 className="font-heading text-lg font-semibold">Pay configuration</h3>
          <dl className="mt-4 space-y-3 text-sm font-data">
            {[
              ["Currency", `${company?.currency || "SLE"} (Sierra Leonean Leone)`],
              ["Pay frequency", company?.pay_frequency || "Monthly"],
              ["Pay day", "Last working day"],
              ["NRA filing day", "15th of next month"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-[#F1EEE6] pb-2 last:border-0">
                <dt className="text-[#525860]">{k}</dt>
                <dd className="font-medium">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </div>
  );
}

function Pillar({ icon: Icon, label, sub }) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-lg px-4 py-3 backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-[#F0B47B]" strokeWidth={1.6} />
        <div className="text-[12px] font-medium text-white/95">{label}</div>
      </div>
      <div className="text-[11px] text-white/55 mt-1">{sub}</div>
    </div>
  );
}
