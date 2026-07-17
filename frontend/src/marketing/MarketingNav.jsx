import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Menu, X, ChevronDown, Phone } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const MENU = [
  {
    label: "What we offer",
    items: [
      { label: "Payroll Engine", to: "/#products", desc: "SLE payroll, NRA PAYE, NASSIT — automated" },
      { label: "HR & Employees", to: "/#products", desc: "Records, leave, attendance, documents" },
      { label: "Compliance & Tax", to: "/#products", desc: "NRA, NASSIT, MoF approval workflow" },
      { label: "AI Assistant", to: "/#products", desc: "Ask anything, action mode for admins" },
      { label: "Civil Service Module", to: "/#products", desc: "Grade-step, ghost-worker audit, budget codes" },
      { label: "IFMIS Integration", to: "/#products", desc: "Bank file disbursement + reconciliation" },
    ],
  },
  {
    label: "Who we serve",
    items: [
      { label: "Small Business (1–49)", to: "/#personas", desc: "Get pricing & onboarding in 24h" },
      { label: "Midsize (50–999)", to: "/#personas", desc: "Multi-department + analytics" },
      { label: "Enterprise (1,000+)", to: "/#personas", desc: "Multi-entity, advanced controls" },
      { label: "Government & MDAs", to: "/#personas", desc: "Civil service, IFMIS, ghost-worker" },
      { label: "Industries — NGO, Mining, Banking", to: "/#industries", desc: "Sector allowance presets" },
    ],
  },
  {
    label: "Why SaloneHCM",
    items: [
      { label: "Built in Sierra Leone", to: "/#why", desc: "SLE-first, Krio support, +232 SMS" },
      { label: "Compliance you can trust", to: "/#why", desc: "NRA PAYE, NASSIT, MoF audit-ready" },
      { label: "Awards & Recognition", to: "/#awards", desc: "Trusted by Government and Enterprise" },
      { label: "Customer stories", to: "/#testimonials", desc: "Real results from local employers" },
    ],
  },
  {
    label: "Resources",
    items: [
      { label: "Insights & guides", to: "/#resources", desc: "Payroll, tax, HR best-practice" },
      { label: "Pricing", to: "/pricing", desc: "Plans for every business size" },
      { label: "Help center", to: "/#footer", desc: "Documentation & FAQs" },
    ],
  },
];

export default function MarketingNav() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const goCta = () => nav(user ? "/billing" : "/demo");

  return (
    <header
      data-testid="marketing-nav"
      className={`sticky top-0 z-50 bg-white transition-shadow ${scrolled ? "shadow-md" : "shadow-sm"}`}
    >
      {/* Sales bar */}
      <div className="hidden lg:flex items-center justify-end gap-6 px-8 py-1.5 bg-[#073A16] text-white text-[12px]">
        <a href="tel:+23230000000" className="flex items-center gap-1.5 hover:text-[#E07B4A]" data-testid="nav-sales-phone">
          <Phone className="w-3.5 h-3.5" /> Talk to sales: +232 30 000 000
        </a>
        <a href="/#contact" className="hover:text-[#E07B4A]" data-testid="nav-support-link">Support</a>
        <Link to="/login" className="hover:text-[#E07B4A]" data-testid="nav-employee-signin">Employee sign-in</Link>
      </div>

      <div className="px-4 lg:px-8 flex items-center justify-between h-[64px]">
        {/* Mobile hamburger */}
        <button
          type="button"
          className="lg:hidden p-2 -ml-2"
          aria-label="Menu"
          onClick={() => setMobileOpen(true)}
          data-testid="nav-hamburger"
        >
          <Menu className="w-6 h-6 text-[#073A16]" />
        </button>

        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 group" data-testid="nav-logo-link">
          <span className="w-9 h-9 rounded-md bg-[#073A16] grid place-items-center text-white font-bold tracking-tight group-hover:bg-[#0B5222] transition-colors">SH</span>
          <span className="flex flex-col leading-none">
            <span className="font-bold text-[15px] text-[#073A16] tracking-tight">SaloneHCM</span>
            <span className="text-[10px] text-[#525860] uppercase tracking-[0.14em]">HR · Payroll · Compliance</span>
          </span>
        </Link>

        {/* Primary nav (desktop) */}
        <nav className="hidden lg:flex items-center gap-1">
          {MENU.map((m) => (
            <div
              key={m.label}
              className="relative"
              onMouseEnter={() => setOpen(m.label)}
              onMouseLeave={() => setOpen(false)}
            >
              <button
                type="button"
                className={`flex items-center gap-1 px-3 h-[44px] text-[14px] font-medium text-[#073A16] hover:text-[#0072C6] transition-colors border-b-2 ${open === m.label ? "border-[#0072C6]" : "border-transparent"}`}
                data-testid={`nav-menu-${m.label.replace(/\s+/g, "-").toLowerCase()}`}
              >
                {m.label}
                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open === m.label ? "rotate-180" : ""}`} />
              </button>
              {open === m.label && (
                <div className="absolute top-full left-0 w-[520px] -translate-x-12 bg-white shadow-xl border border-[#EAE7DF] rounded-md p-6 grid grid-cols-2 gap-x-6 gap-y-3 animate-in fade-in slide-in-from-top-1 duration-150">
                  {m.items.map((it) => (
                    <Link
                      key={it.label}
                      to={it.to}
                      className="group block py-1.5 hover:bg-[#FAF8F2] -mx-2 px-2 rounded transition-colors"
                      onClick={() => setOpen(false)}
                      data-testid={`menu-item-${it.label.split(" ")[0].toLowerCase()}`}
                    >
                      <div className="text-[13px] font-semibold text-[#073A16] group-hover:text-[#0072C6]">{it.label}</div>
                      <div className="text-[12px] text-[#525860] leading-snug">{it.desc}</div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}
          <Link to="/pricing" className="px-3 h-[44px] flex items-center text-[14px] font-medium text-[#073A16] hover:text-[#0072C6]" data-testid="nav-pricing">
            Pricing
          </Link>
          <Link to="/demo" className="px-3 h-[44px] flex items-center text-[14px] font-medium text-[#073A16] hover:text-[#0072C6]" data-testid="nav-demo">
            Get a demo
          </Link>
          <Link to="/tour" className="px-3 h-[44px] flex items-center text-[14px] font-medium text-[#073A16] hover:text-[#0072C6]" data-testid="nav-tour">
            Tour the product
          </Link>
          <Link to="/videos" className="px-3 h-[44px] flex items-center text-[14px] font-medium text-[#073A16] hover:text-[#0072C6]" data-testid="nav-videos">
            Videos
          </Link>
          <Link to="/training" className="px-3 h-[44px] flex items-center text-[14px] font-medium text-[#073A16] hover:text-[#0072C6]" data-testid="nav-training">
            Training
          </Link>
        </nav>

        {/* Right CTAs */}
        <div className="flex items-center gap-2.5">
          <Link
            to={user ? "/dashboard" : "/login"}
            className="hidden sm:inline-flex items-center px-4 h-9 text-[13px] font-semibold text-[#073A16] border border-[#073A16] rounded-full hover:bg-[#073A16] hover:text-white transition-colors"
            data-testid="nav-signin-button"
          >
            {user ? "Dashboard" : "Sign in"}
          </Link>
          <button
            type="button"
            onClick={goCta}
            className="inline-flex items-center px-4 h-9 text-[13px] font-semibold text-white bg-[#0072C6] rounded-full hover:bg-[#005A9C] transition-colors"
            data-testid="nav-get-pricing-button"
          >
            Get pricing
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 bg-white lg:hidden overflow-y-auto" data-testid="nav-mobile-drawer">
          <div className="flex items-center justify-between px-4 h-[64px] border-b border-[#EAE7DF]">
            <Link to="/" className="flex items-center gap-2.5" onClick={() => setMobileOpen(false)}>
              <span className="w-9 h-9 rounded-md bg-[#073A16] grid place-items-center text-white font-bold">SH</span>
              <span className="font-bold text-[#073A16]">SaloneHCM</span>
            </Link>
            <button type="button" aria-label="Close" onClick={() => setMobileOpen(false)} data-testid="nav-mobile-close">
              <X className="w-6 h-6 text-[#073A16]" />
            </button>
          </div>
          <div className="px-4 py-6 space-y-4">
            {MENU.map((m) => (
              <details key={m.label} className="border-b border-[#EAE7DF] pb-3">
                <summary className="flex items-center justify-between py-2 cursor-pointer text-[15px] font-semibold text-[#073A16]">
                  {m.label}
                  <ChevronDown className="w-4 h-4" />
                </summary>
                <div className="pt-2 space-y-2">
                  {m.items.map((it) => (
                    <Link
                      key={it.label}
                      to={it.to}
                      onClick={() => setMobileOpen(false)}
                      className="block text-[13px] text-[#525860] hover:text-[#0072C6]"
                    >
                      {it.label}
                    </Link>
                  ))}
                </div>
              </details>
            ))}
            <Link
              to="/pricing"
              onClick={() => setMobileOpen(false)}
              className="block py-2 text-[15px] font-semibold text-[#073A16]"
            >Pricing</Link>
            <Link
              to="/demo"
              onClick={() => setMobileOpen(false)}
              className="block py-2 text-[15px] font-semibold text-[#073A16]"
            >Get a demo</Link>
            <Link
              to="/tour"
              onClick={() => setMobileOpen(false)}
              className="block py-2 text-[15px] font-semibold text-[#073A16]"
            >Tour the product</Link>
            <Link
              to="/videos"
              onClick={() => setMobileOpen(false)}
              className="block py-2 text-[15px] font-semibold text-[#073A16]"
            >Videos</Link>
            <Link
              to="/training"
              onClick={() => setMobileOpen(false)}
              className="block py-2 text-[15px] font-semibold text-[#073A16]"
            >Training</Link>
            <div className="pt-4 flex flex-col gap-2">
              <Link to={user ? "/dashboard" : "/login"} className="text-center px-4 h-11 inline-flex items-center justify-center text-[14px] font-semibold text-[#073A16] border border-[#073A16] rounded-full">
                {user ? "Dashboard" : "Sign in"}
              </Link>
              <button type="button" onClick={() => { setMobileOpen(false); goCta(); }} className="px-4 h-11 text-[14px] font-semibold text-white bg-[#0072C6] rounded-full">
                Get pricing
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
