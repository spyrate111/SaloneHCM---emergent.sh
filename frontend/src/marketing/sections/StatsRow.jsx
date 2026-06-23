import { Users, Building2, Wallet, ShieldCheck } from "lucide-react";

const STATS = [
  { icon: Users, label: "Employees paid each month", value: "42,000+" },
  { icon: Building2, label: "Companies & MDAs onboarded", value: "180+" },
  { icon: Wallet, label: "SLE moved through SaloneHCM annually", value: "SLE 1.2B" },
  { icon: ShieldCheck, label: "On-time NRA PAYE returns", value: "99.4%" },
];

export default function StatsRow() {
  return (
    <section
      id="why"
      data-testid="stats-section"
      className="py-14 lg:py-20 bg-[#0F2C24] text-white"
    >
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
        <div className="max-w-[760px] mb-10">
          <p className="text-[12px] font-bold uppercase tracking-[0.16em] text-[#E07B4A]">Why SaloneHCM</p>
          <h2 className="mt-2 text-[32px] sm:text-[40px] font-extrabold leading-tight">
            Managing and paying people across Sierra Leone, every month.
          </h2>
          <p className="mt-3 text-white/75 text-[16px] leading-relaxed">
            From owner-operators in Bo to ministries in Freetown — employers trust SaloneHCM to keep their teams paid, compliant and informed.
          </p>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-white/10 rounded-2xl overflow-hidden">
          {STATS.map((s) => {
            const Icon = s.icon;
            return (
              <div key={s.label} className="bg-[#0F2C24] p-7" data-testid={`stat-${s.label.toLowerCase().replace(/\s+/g, "-")}`}>
                <Icon className="w-7 h-7 text-[#E07B4A]" />
                <div className="mt-4 text-[28px] sm:text-[36px] font-extrabold leading-none">{s.value}</div>
                <div className="mt-2 text-[12.5px] text-white/70 leading-snug">{s.label}</div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
