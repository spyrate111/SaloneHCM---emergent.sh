import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, CheckCircle2 } from "lucide-react";

const INTERESTS = [
  { value: "", label: "What are you interested in?" },
  { value: "payroll", label: "Payroll & Tax (PAYE, NASSIT)" },
  { value: "hr", label: "HR & Employee management" },
  { value: "civil_service", label: "Civil Service (Gov / MDA)" },
  { value: "ifmis", label: "IFMIS & bank disbursement" },
  { value: "ats", label: "Recruiting & talent (ATS)" },
  { value: "ai", label: "AI Assistant" },
  { value: "self_service", label: "Employee self-service" },
];

const PROOF = [
  { stat: "<2 hrs", label: "to run a full monthly payroll" },
  { stat: "100%", label: "NRA PAYE & NASSIT compliant" },
  { stat: "7 days", label: "average go-live" },
];

export default function Hero() {
  const nav = useNavigate();
  const [emp, setEmp] = useState("");
  const [interest, setInterest] = useState("");
  const ready = useMemo(() => Number(emp) > 0 && !!interest, [emp, interest]);

  const submit = (e) => {
    e.preventDefault();
    if (!ready) return;
    // Stash in sessionStorage; pricing page can use this to pre-fill
    try {
      sessionStorage.setItem("salonehcm_lead", JSON.stringify({ employees: Number(emp), interest }));
    } catch (err) {
      // sessionStorage may be disabled (Safari private mode etc.) — log and continue.
      console.debug("[Hero] sessionStorage write skipped:", err?.message || err);
    }
    nav("/demo");
  };

  return (
    <section
      id="hero"
      data-testid="hero-section"
      className="relative overflow-hidden bg-gradient-to-b from-[#FAF8F2] via-[#FAF8F2] to-white"
    >
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-14 lg:py-20 grid lg:grid-cols-12 gap-10 items-center">
        {/* Left: copy + form */}
        <div className="lg:col-span-7">
          <span className="inline-flex items-center px-3 h-7 text-[11px] font-bold uppercase tracking-[0.14em] rounded-full bg-[#073A16] text-white">
            HR · Payroll · Compliance for Sierra Leone
          </span>
          <h1 className="mt-5 text-[40px] sm:text-[52px] lg:text-[60px] font-extrabold leading-[1.04] text-[#073A16]">
            Experience better HR <span className="text-[#0072C6]">and payroll</span>
          </h1>
          <p className="mt-5 text-[18px] sm:text-[20px] text-[#374049] max-w-[640px] leading-relaxed">
            Answer two questions &mdash; we&rsquo;ll build you a plan that fits Sierra Leone&rsquo;s tax laws, NASSIT rules, and the way you actually pay your people.
          </p>

          {/* Solution Wizard */}
          <form onSubmit={submit} className="mt-8 bg-white border border-[#EAE7DF] rounded-xl shadow-sm p-4 sm:p-5 flex flex-col sm:flex-row gap-3 max-w-[640px]" data-testid="hero-solution-wizard">
            <input
              type="number"
              min="1"
              required
              value={emp}
              onChange={(e) => setEmp(e.target.value)}
              placeholder="# of employees"
              className="flex-1 h-12 px-4 text-[14px] border border-[#EAE7DF] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#073A16] focus:border-transparent"
              data-testid="hero-input-employees"
            />
            <select
              value={interest}
              onChange={(e) => setInterest(e.target.value)}
              required
              className="flex-1 h-12 px-3 text-[14px] border border-[#EAE7DF] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#073A16] bg-white"
              data-testid="hero-select-interest"
            >
              {INTERESTS.map((i) => (
                <option key={i.value} value={i.value} disabled={!i.value}>{i.label}</option>
              ))}
            </select>
            <button
              type="submit"
              disabled={!ready}
              className={`h-12 px-6 text-[14px] font-bold rounded-lg inline-flex items-center justify-center gap-1.5 transition-all ${
                ready
                  ? "bg-[#0072C6] text-white hover:bg-[#005A9C]"
                  : "bg-[#EAE7DF] text-[#9aa0a6] cursor-not-allowed"
              }`}
              data-testid="hero-submit-button"
            >
              Let&rsquo;s go <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Secondary CTAs */}
          <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px] text-[#525860]">
            <a href="/tour" className="font-semibold text-[#073A16] hover:text-[#0072C6] inline-flex items-center gap-1" data-testid="hero-secondary-tour">
              Or take the interactive tour <ArrowRight className="w-3.5 h-3.5" />
            </a>
            <span className="text-[#EAE7DF]">|</span>
            <a href="#personas" className="font-semibold text-[#073A16] hover:text-[#0072C6] inline-flex items-center gap-1" data-testid="hero-secondary-personas">
              Pick by business size <ArrowRight className="w-3.5 h-3.5" />
            </a>
            <span className="text-[#EAE7DF]">|</span>
            <a href="tel:+23230000000" className="hover:text-[#0072C6]" data-testid="hero-secondary-call">
              Talk to a specialist: <strong className="text-[#073A16]">+232 30 000 000</strong>
            </a>
          </div>

          {/* Proof strip */}
          <ul className="mt-8 grid grid-cols-3 gap-3 sm:gap-6 max-w-[640px]">
            {PROOF.map((p) => (
              <li key={p.label} className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#128A2C] flex-none mt-1" />
                <div>
                  <div className="text-[18px] sm:text-[22px] font-extrabold text-[#073A16] leading-none">{p.stat}</div>
                  <div className="text-[11px] sm:text-[12px] text-[#525860] mt-1 leading-snug">{p.label}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Right: hero illustration */}
        <div className="lg:col-span-5 relative hidden lg:block">
          <HeroIllustration />
        </div>
      </div>
    </section>
  );
}

function HeroIllustration() {
  return (
    <div className="relative" aria-hidden="true">
      {/* Floating cards atop a base panel */}
      <div className="absolute -top-6 -left-10 w-[240px] bg-white rounded-xl shadow-lg border border-[#EAE7DF] p-4 rotate-[-4deg] z-20">
        <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#525860]">Payroll run · June 2026</div>
        <div className="mt-1 text-[24px] font-extrabold text-[#073A16]">SLE 184,720</div>
        <div className="mt-1 text-[11px] text-[#128A2C]">+2.3% vs last month · 142 employees</div>
        <div className="mt-3 h-2 bg-[#FAF8F2] rounded-full overflow-hidden">
          <div className="h-full w-[72%] bg-[#128A2C] rounded-full"></div>
        </div>
      </div>

      <div className="ml-14 mt-8 bg-gradient-to-br from-[#073A16] to-[#128A2C] rounded-2xl p-7 shadow-xl text-white relative overflow-hidden z-10">
        <div className="absolute -right-10 -bottom-10 w-44 h-44 rounded-full bg-[#E07B4A] opacity-30 blur-2xl"></div>
        <div className="text-[11px] font-bold uppercase tracking-[0.16em] opacity-80">Compliance score</div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-[56px] font-extrabold leading-none">98</span>
          <span className="text-[18px] font-semibold opacity-80">/100</span>
        </div>
        <div className="mt-1 text-[13px] opacity-80">NRA PAYE filed · NASSIT remitted · MoF approval pending</div>
        <ul className="mt-5 space-y-2 text-[13px]">
          {["NRA PAYE return — submitted", "NASSIT contribution — remitted", "GST — current", "Ghost-worker audit — clean"].map((t) => (
            <li key={t} className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-white/85" />{t}</li>
          ))}
        </ul>
      </div>

      <div className="absolute -right-2 -bottom-4 w-[220px] bg-white rounded-xl shadow-lg border border-[#EAE7DF] p-4 rotate-[4deg] z-20">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-full bg-[#FAF8F2] grid place-items-center text-[#073A16] font-bold">AI</div>
          <div>
            <div className="text-[12px] font-bold text-[#073A16]">SaloneHCM Assistant</div>
            <div className="text-[10px] text-[#525860]">Action mode · ready</div>
          </div>
        </div>
        <p className="mt-2 text-[11px] text-[#374049] leading-relaxed">
          &ldquo;Show me total PAYE owed for Q2.&rdquo; <span className="text-[#0072C6] font-semibold">Computing&hellip;</span>
        </p>
      </div>
    </div>
  );
}
