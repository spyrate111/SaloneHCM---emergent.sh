import { Target, Globe, Briefcase, Building2 } from "lucide-react";

export default function Settings() {
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <h3 className="font-heading text-lg font-semibold">Company</h3>
          <dl className="mt-4 space-y-3 text-sm font-data">
            {[["Legal name", "Demo Salone Ltd."], ["TIN", "TIN-100200300"], ["NASSIT employer", "NS-EMP-001"], ["Country", "Sierra Leone"], ["Tier", "SaloneHCM Professional"]].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-[#F1EEE6] pb-2 last:border-0"><dt className="text-[#525860]">{k}</dt><dd className="font-medium">{v}</dd></div>
            ))}
          </dl>
        </div>
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <h3 className="font-heading text-lg font-semibold">Pay configuration</h3>
          <dl className="mt-4 space-y-3 text-sm font-data">
            {[["Currency", "SLE (Sierra Leonean Leone)"], ["Pay frequency", "Monthly"], ["Pay day", "Last working day"], ["NRA filing day", "15th of next month"]].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-[#F1EEE6] pb-2 last:border-0"><dt className="text-[#525860]">{k}</dt><dd className="font-medium">{v}</dd></div>
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
