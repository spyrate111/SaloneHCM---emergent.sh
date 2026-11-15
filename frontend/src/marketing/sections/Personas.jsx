import { Link } from "react-router-dom";
import { ChevronRight, Briefcase, Building2, Landmark, Factory } from "lucide-react";

const PERSONAS = [
  {
    icon: Briefcase,
    title: "Small Business",
    range: "1–49 employees",
    color: "bg-[#FFF7F0] border-[#E07B4A]/40",
    accent: "text-[#E07B4A]",
    bullets: [
      "Monthly payroll in under 2 hours",
      "PAYE & NASSIT auto-computed",
      "Employee self-service from day one",
    ],
    cta: "Explore Small Business",
    to: "/pricing",
    testId: "persona-small",
  },
  {
    icon: Building2,
    title: "Midsize Business",
    range: "50–999 employees",
    color: "bg-[#F0F9F1] border-[#128A2C]/30",
    accent: "text-[#128A2C]",
    bullets: [
      "Multi-department analytics",
      "Performance & talent ATS",
      "Loans & advances integrated",
    ],
    cta: "Explore Midsize",
    to: "/pricing",
    testId: "persona-midsize",
    featured: true,
  },
  {
    icon: Factory,
    title: "Enterprise",
    range: "1,000+ employees",
    color: "bg-[#F5F3FB] border-[#5a4FCF]/30",
    accent: "text-[#5a4FCF]",
    bullets: [
      "Multi-entity & multi-currency",
      "What-if scenario simulator",
      "AI Assistant Action Mode",
    ],
    cta: "Explore Enterprise",
    to: "/pricing",
    testId: "persona-enterprise",
  },
  {
    icon: Landmark,
    title: "Government & MDAs",
    range: "Civil Service tier",
    color: "bg-[#F5F1EC] border-[#073A16]/30",
    accent: "text-[#073A16]",
    bullets: [
      "Grade & step civil-service payroll",
      "IFMIS bank disbursement",
      "Ghost-worker & MoF approval audit",
    ],
    cta: "Explore Government",
    to: "/pricing",
    testId: "persona-government",
  },
];

export default function Personas() {
  return (
    <section
      id="personas"
      data-testid="personas-section"
      className="py-16 lg:py-24 bg-white"
    >
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
        <div className="max-w-[760px] mb-12">
          <p className="text-[12px] font-bold uppercase tracking-[0.16em] text-[#0072C6]">Who we serve</p>
          <h2 className="mt-2 text-[32px] sm:text-[40px] font-extrabold text-[#073A16] leading-tight">
            One platform. Every business size in Sierra Leone.
          </h2>
          <p className="mt-3 text-[16px] text-[#374049]">
            Whether you&rsquo;re a 5-person startup in Bo or a 5,000-person ministry in Freetown, SaloneHCM scales with you &mdash; no rip-and-replace.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {PERSONAS.map((p) => {
            const Icon = p.icon;
            return (
              <div
                key={p.title}
                data-testid={p.testId}
                className={`relative border rounded-2xl p-6 ${p.color} hover:shadow-lg transition-shadow group`}
              >
                {p.featured && (
                  <span className="absolute -top-3 left-6 inline-flex items-center px-2.5 h-6 text-[10px] font-bold uppercase tracking-[0.12em] bg-[#073A16] text-white rounded-full">
                    Most popular
                  </span>
                )}
                <Icon className={`w-9 h-9 ${p.accent}`} />
                <h3 className="mt-4 text-[20px] font-extrabold text-[#073A16]">{p.title}</h3>
                <p className={`text-[12px] font-semibold ${p.accent} mt-0.5`}>{p.range}</p>
                <ul className="mt-4 space-y-2">
                  {p.bullets.map((b) => (
                    <li key={b} className="text-[13px] text-[#374049] flex items-start gap-2 leading-snug">
                      <span className={`mt-1 inline-block w-1.5 h-1.5 rounded-full ${p.accent.replace("text", "bg")} flex-none`}></span>
                      {b}
                    </li>
                  ))}
                </ul>
                <Link
                  to={p.to}
                  className={`mt-5 inline-flex items-center gap-1 text-[13px] font-bold ${p.accent} group-hover:gap-2 transition-all`}
                  data-testid={`${p.testId}-cta`}
                >
                  {p.cta} <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
