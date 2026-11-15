import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check, ArrowRight, Sparkles } from "lucide-react";
import MarketingLayout from "./MarketingLayout";
import api from "../lib/api";

const FALLBACK_PLANS = [
  {
    id: "lite",
    name: "Lite",
    tagline: "For small employers getting started.",
    price_monthly_sle: 750,
    employees: "Up to 25",
    features: [
      "Payroll engine (PAYE, NASSIT)",
      "Employee records & leave",
      "Attendance tracking",
      "Self-service portal",
      "Email + WhatsApp payslips",
    ],
    cta: "Start with Lite",
    featured: false,
  },
  {
    id: "professional",
    name: "Professional",
    tagline: "For growing teams that need analytics + talent.",
    price_monthly_sle: 2500,
    employees: "Up to 250",
    features: [
      "Everything in Lite",
      "Benefits administration",
      "Talent ATS + recurring training",
      "Performance reviews",
      "Loans & advances",
      "Sector allowance presets",
      "AI Assistant (Q&A)",
      "Analytics dashboards",
    ],
    cta: "Start with Professional",
    featured: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    tagline: "For multi-entity employers with complex needs.",
    price_monthly_sle: 7500,
    employees: "Unlimited",
    features: [
      "Everything in Professional",
      "What-if scenario simulator",
      "Decision-brief PDF generator",
      "AI Assistant Action Mode",
      "IFMIS bank disbursement",
      "Establishment control",
      "Multi-tenant company switching",
    ],
    cta: "Talk to sales",
    featured: false,
  },
  {
    id: "gov",
    name: "Government & MDA",
    tagline: "Civil-service grade & step. IFMIS + ghost-worker audits.",
    price_monthly_sle: null,
    employees: "Unlimited",
    features: [
      "Everything in Enterprise",
      "Civil Service module (grade/step)",
      "MoF approval workflow",
      "Ghost-worker detection",
      "Bulk-SMS payslips (+232 ready)",
      "NRA bulk export",
      "Auditor-General reporting (PDF)",
    ],
    cta: "Request a Gov demo",
    featured: false,
  },
];

export default function PricingPage() {
  const nav = useNavigate();
  const [plans, setPlans] = useState(FALLBACK_PLANS);

  useEffect(() => {
    // Best-effort fetch of plans from /api/billing/plans (requires auth, so this typically fails 401 — fallback is fine)
    api.get("/billing/plans")
      .then((r) => {
        if (Array.isArray(r.data?.plans) && r.data.plans.length) {
          // Merge but keep our marketing copy
          setPlans((cur) => cur.map((c) => {
            const found = r.data.plans.find((p) => p.id === c.id);
            return found ? { ...c, price_monthly_sle: found.price_monthly_sle ?? c.price_monthly_sle } : c;
          }));
        }
      })
      .catch(() => {}); // expected when unauthenticated
  }, []);

  const goCta = (planId) => {
    if (planId === "gov" || planId === "enterprise") {
      nav("/#contact");
    } else {
      nav("/login");
    }
  };

  return (
    <MarketingLayout>
      <section className="bg-gradient-to-b from-[#FAF8F2] to-white py-16 lg:py-20" data-testid="pricing-hero">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 text-center">
          <span className="inline-flex items-center px-3 h-7 text-[11px] font-bold uppercase tracking-[0.14em] rounded-full bg-[#073A16] text-white gap-1.5">
            <Sparkles className="w-3 h-3" /> Simple, transparent SLE pricing
          </span>
          <h1 className="mt-5 text-[40px] sm:text-[52px] font-extrabold text-[#073A16] leading-[1.05]">
            One platform. <span className="text-[#0072C6]">Four tiers</span>. Built for Sierra Leone.
          </h1>
          <p className="mt-4 text-[16px] sm:text-[18px] text-[#374049] max-w-[680px] mx-auto">
            Pay in SLE. Pay monthly. Cancel anytime. New customers — get up to 3 months free.
          </p>
        </div>
      </section>

      <section className="py-12 lg:py-20" data-testid="pricing-grid-section">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {plans.map((p) => (
              <div
                key={p.id}
                data-testid={`plan-${p.id}`}
                className={`relative rounded-2xl p-7 flex flex-col ${
                  p.featured
                    ? "bg-[#073A16] text-white border-2 border-[#073A16] shadow-xl scale-[1.02]"
                    : "bg-white border border-[#EAE7DF] hover:shadow-lg transition-shadow"
                }`}
              >
                {p.featured && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 inline-flex items-center px-3 h-6 text-[10px] font-bold uppercase tracking-[0.14em] bg-[#0072C6] text-white rounded-full">
                    Most popular
                  </span>
                )}
                <h3 className={`text-[22px] font-extrabold ${p.featured ? "text-white" : "text-[#073A16]"}`}>{p.name}</h3>
                <p className={`text-[13px] mt-1 ${p.featured ? "text-white/75" : "text-[#525860]"} leading-snug`}>{p.tagline}</p>

                <div className="mt-6">
                  {p.price_monthly_sle ? (
                    <>
                      <div className="flex items-baseline gap-1">
                        <span className={`text-[12px] font-bold ${p.featured ? "text-white/70" : "text-[#525860]"}`}>SLE</span>
                        <span className={`text-[42px] font-extrabold leading-none ${p.featured ? "text-white" : "text-[#073A16]"}`}>
                          {p.price_monthly_sle.toLocaleString()}
                        </span>
                      </div>
                      <div className={`text-[11px] ${p.featured ? "text-white/70" : "text-[#525860]"} mt-1`}>per month · billed monthly</div>
                    </>
                  ) : (
                    <div className={`text-[22px] font-extrabold ${p.featured ? "text-white" : "text-[#073A16]"}`}>Custom</div>
                  )}
                  <div className={`mt-2 text-[12px] font-semibold ${p.featured ? "text-[#E07B4A]" : "text-[#128A2C]"}`}>{p.employees} employees</div>
                </div>

                <ul className="mt-6 space-y-2.5 flex-1">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <Check className={`w-4 h-4 flex-none mt-0.5 ${p.featured ? "text-[#E07B4A]" : "text-[#128A2C]"}`} />
                      <span className={`text-[13px] leading-snug ${p.featured ? "text-white/90" : "text-[#374049]"}`}>{f}</span>
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  onClick={() => goCta(p.id)}
                  className={`mt-7 w-full h-12 text-[14px] font-bold rounded-full inline-flex items-center justify-center gap-1.5 ${
                    p.featured
                      ? "bg-[#0072C6] text-white hover:bg-[#005A9C]"
                      : "border border-[#073A16] text-[#073A16] hover:bg-[#073A16] hover:text-white"
                  } transition-colors`}
                  data-testid={`plan-${p.id}-cta`}
                >
                  {p.cta} <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          <div className="mt-12 max-w-[760px] mx-auto text-center" data-testid="pricing-bank-transfer">
            <p className="text-[14px] text-[#525860]">
              All plans support <strong className="text-[#073A16]">Stripe</strong> card billing and{" "}
              <strong className="text-[#073A16]">direct bank transfer</strong> to local SLE accounts (Rokel, SLCB, UBA, Ecobank).
            </p>
            <Link to="/#contact" className="mt-4 inline-flex items-center gap-1.5 text-[14px] font-bold text-[#0072C6] hover:text-[#005A9C]">
              Need a custom quote? Talk to sales <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}
