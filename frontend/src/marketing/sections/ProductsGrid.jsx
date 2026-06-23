import { Link } from "react-router-dom";
import {
  Calculator, Users, ShieldCheck, Sparkles, Award, Building2,
  Wallet, GraduationCap, Landmark, ArrowUpRight,
} from "lucide-react";

const PRODUCTS = [
  {
    icon: Calculator,
    title: "Payroll Engine",
    desc: "SLE-aware payroll with NRA PAYE, NASSIT, GST and bonus tax — done in one click.",
    cta: "Payroll overview",
    testId: "product-payroll",
  },
  {
    icon: Users,
    title: "HR & Employees",
    desc: "Centralized records, leave, attendance, documents and an audit-trail you can prove.",
    cta: "Employee management",
    testId: "product-hr",
  },
  {
    icon: ShieldCheck,
    title: "Compliance & Tax",
    desc: "NRA PAYE return, NASSIT, GST and MoF approval workflow — all kept current.",
    cta: "Compliance hub",
    testId: "product-compliance",
  },
  {
    icon: Sparkles,
    title: "AI Assistant",
    desc: "Ask anything in English or Krio. Action mode lets admins approve, file and email — by chat.",
    cta: "Try the assistant",
    testId: "product-ai",
  },
  {
    icon: Award,
    title: "Civil Service Module",
    desc: "Grade-step structure, budget-code roll-ups, ghost-worker detection and MoF approval.",
    cta: "Civil Service module",
    testId: "product-civil-service",
  },
  {
    icon: Building2,
    title: "Establishment Control",
    desc: "Position & vacancy tracking by ministry, department and unit — with budget code attached.",
    cta: "Establishment overview",
    testId: "product-establishment",
  },
  {
    icon: Wallet,
    title: "Loans & Advances",
    desc: "Issue loans, deduct from payroll automatically, track balance and amortization.",
    cta: "Loans engine",
    testId: "product-loans",
  },
  {
    icon: Landmark,
    title: "IFMIS Integration",
    desc: "Generate bank-format CSVs (Rokel, SLCB, UBA, Ecobank) and reconcile disbursements.",
    cta: "IFMIS layer",
    testId: "product-ifmis",
  },
  {
    icon: GraduationCap,
    title: "Talent & Performance",
    desc: "ATS Kanban, recurring training, reviews and analytics — built for SL labor laws.",
    cta: "Talent & Performance",
    testId: "product-talent",
  },
];

export default function ProductsGrid() {
  return (
    <section
      id="products"
      data-testid="products-section"
      className="py-16 lg:py-24 bg-[#FAF8F2]"
    >
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-12">
          <div className="max-w-[680px]">
            <p className="text-[12px] font-bold uppercase tracking-[0.16em] text-[#C02719]">What we offer</p>
            <h2 className="mt-2 text-[32px] sm:text-[40px] font-extrabold text-[#0F2C24] leading-tight">
              Nine pillars, one platform — all localized for Sierra Leone.
            </h2>
          </div>
          <Link to="/pricing" className="inline-flex items-center gap-1.5 text-[14px] font-bold text-[#0F2C24] hover:text-[#C02719]" data-testid="products-see-all">
            See all features <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {PRODUCTS.map((p) => {
            const Icon = p.icon;
            return (
              <div
                key={p.title}
                className="bg-white border border-[#EAE7DF] rounded-xl p-6 hover:border-[#0F2C24] hover:shadow-md transition-all group"
                data-testid={p.testId}
              >
                <div className="w-11 h-11 rounded-lg bg-[#FAF8F2] grid place-items-center group-hover:bg-[#0F2C24] transition-colors">
                  <Icon className="w-5 h-5 text-[#0F2C24] group-hover:text-white transition-colors" />
                </div>
                <h3 className="mt-4 text-[18px] font-extrabold text-[#0F2C24]">{p.title}</h3>
                <p className="mt-2 text-[14px] text-[#525860] leading-relaxed">{p.desc}</p>
                <Link to="/pricing" className="mt-4 inline-flex items-center gap-1 text-[13px] font-bold text-[#C02719] hover:gap-2 transition-all">
                  {p.cta} <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
