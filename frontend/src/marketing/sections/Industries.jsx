import { Link } from "react-router-dom";
import { HandCoins, Pickaxe, Banknote, Signal, Landmark, HeartHandshake } from "lucide-react";

const INDUSTRIES = [
  { icon: HandCoins, label: "NGO", desc: "Per-diem, field, hardship allowances" },
  { icon: Pickaxe, label: "Mining", desc: "Hazard, remote-site, family separation" },
  { icon: Banknote, label: "Banking", desc: "Cash-handling, transport, performance" },
  { icon: Signal, label: "Telecom", desc: "On-call, tower-climb, fuel & comms" },
  { icon: Landmark, label: "Government", desc: "Civil-service grade & step structure" },
  { icon: HeartHandshake, label: "General Private", desc: "Housing, transport, communication" },
];

export default function Industries() {
  return (
    <section
      id="industries"
      data-testid="industries-section"
      className="py-16 lg:py-24 bg-white"
    >
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
        <div className="grid lg:grid-cols-12 gap-10 lg:gap-16 items-start">
          <div className="lg:col-span-4">
            <p className="text-[12px] font-bold uppercase tracking-[0.16em] text-[#C02719]">Industries</p>
            <h2 className="mt-2 text-[32px] sm:text-[40px] font-extrabold text-[#0F2C24] leading-tight">
              Sector-aware allowance presets.
            </h2>
            <p className="mt-3 text-[15px] text-[#374049] leading-relaxed">
              Apply industry-tuned allowance bundles to one employee or a whole department in seconds. Pre-built templates for the sectors that matter in Sierra Leone — or roll your own.
            </p>
            <Link
              to="/pricing"
              className="mt-5 inline-flex items-center px-5 h-11 text-[13px] font-semibold border border-[#0F2C24] rounded-full text-[#0F2C24] hover:bg-[#0F2C24] hover:text-white transition-colors"
              data-testid="industries-cta"
            >
              See sector pricing
            </Link>
          </div>
          <div className="lg:col-span-8 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {INDUSTRIES.map((it) => {
              const Icon = it.icon;
              return (
                <div
                  key={it.label}
                  className="border border-[#EAE7DF] rounded-xl p-5 hover:border-[#C02719] transition-colors group bg-[#FAF8F2]"
                  data-testid={`industry-${it.label.toLowerCase().replace(/\s+/g, "-")}`}
                >
                  <Icon className="w-7 h-7 text-[#0F2C24] group-hover:text-[#C02719] transition-colors" />
                  <h3 className="mt-3 text-[15px] font-bold text-[#0F2C24]">{it.label}</h3>
                  <p className="mt-1 text-[12.5px] text-[#525860] leading-snug">{it.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
