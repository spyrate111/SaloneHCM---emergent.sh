import { Link } from "react-router-dom";
import { Facebook, Linkedin, Twitter, Youtube, Globe } from "lucide-react";

const FOOTER = {
  "What we offer": [
    { label: "Payroll Engine", to: "/#products" },
    { label: "HR & Employee records", to: "/#products" },
    { label: "Compliance & Tax", to: "/#products" },
    { label: "AI Assistant", to: "/#products" },
    { label: "Civil Service", to: "/#products" },
    { label: "IFMIS integration", to: "/#products" },
    { label: "Loans & advances", to: "/#products" },
    { label: "Performance reviews", to: "/#products" },
  ],
  "Who we serve": [
    { label: "Small Business (1–49)", to: "/#personas" },
    { label: "Midsize (50–999)", to: "/#personas" },
    { label: "Enterprise (1,000+)", to: "/#personas" },
    { label: "Government & MDAs", to: "/#personas" },
    { label: "NGO", to: "/#industries" },
    { label: "Mining", to: "/#industries" },
    { label: "Banking", to: "/#industries" },
    { label: "Telecommunications", to: "/#industries" },
  ],
  "Resources": [
    { label: "Insights & guides", to: "/#resources" },
    { label: "Pricing", to: "/pricing" },
    { label: "Help center", to: "/#footer" },
    { label: "Transparency portal", to: "/transparency/government-of-sierra-leone" },
    { label: "Compliance hub", to: "/#why" },
    { label: "Testimonials", to: "/#testimonials" },
  ],
  "About SaloneHCM": [
    { label: "Our story", to: "/#why" },
    { label: "Careers", to: "/#footer" },
    { label: "Press", to: "/#footer" },
    { label: "Partners", to: "/#footer" },
    { label: "Contact us", to: "/#contact" },
    { label: "Sign in", to: "/login" },
  ],
};

export default function MarketingFooter() {
  return (
    <footer id="footer" data-testid="marketing-footer" className="bg-[#073A16] text-white">
      {/* Top: Talk-to-sales bar */}
      <div className="border-b border-white/10">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-10 grid md:grid-cols-2 gap-6 items-center">
          <div>
            <h3 className="text-[22px] sm:text-[28px] font-bold leading-tight">Ready to streamline HR & payroll across Sierra Leone?</h3>
            <p className="text-white/70 text-[14px] mt-1.5">Speak to a SaloneHCM specialist — quote in 24 hours, onboarding in 7 days.</p>
          </div>
          <div className="flex flex-wrap gap-3 md:justify-end">
            <a href="tel:+23230000000" className="px-5 h-11 inline-flex items-center text-[14px] font-semibold bg-[#0072C6] rounded-full hover:bg-[#005A9C]" data-testid="footer-call-sales">
              Call sales: +232 30 000 000
            </a>
            <Link to="/#contact" className="px-5 h-11 inline-flex items-center text-[14px] font-semibold border border-white rounded-full hover:bg-white hover:text-[#073A16]" data-testid="footer-contact-us">
              Contact us
            </Link>
          </div>
        </div>
      </div>

      {/* Link columns */}
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-12 grid grid-cols-2 md:grid-cols-4 gap-x-8 gap-y-10">
        {Object.entries(FOOTER).map(([heading, links]) => (
          <div key={heading}>
            <h4 className="text-[13px] font-bold uppercase tracking-[0.1em] text-white/95 mb-3">{heading}</h4>
            <ul className="space-y-2">
              {links.map((l) => (
                <li key={l.label}>
                  <Link to={l.to} className="text-[13px] text-white/70 hover:text-[#E07B4A] transition-colors">{l.label}</Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Legal strip */}
      <div className="border-t border-white/10">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <span className="w-9 h-9 rounded-md bg-white grid place-items-center text-[#073A16] font-bold tracking-tight">SH</span>
            <div className="leading-none">
              <div className="font-bold text-[13px]">SaloneHCM</div>
              <div className="text-[11px] text-white/60">© {new Date().getFullYear()} SaloneHCM Ltd. — Freetown, Sierra Leone</div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <a href="#" aria-label="LinkedIn" className="text-white/70 hover:text-white" data-testid="footer-social-linkedin"><Linkedin className="w-4 h-4" /></a>
            <a href="#" aria-label="Twitter" className="text-white/70 hover:text-white" data-testid="footer-social-twitter"><Twitter className="w-4 h-4" /></a>
            <a href="#" aria-label="Facebook" className="text-white/70 hover:text-white" data-testid="footer-social-facebook"><Facebook className="w-4 h-4" /></a>
            <a href="#" aria-label="YouTube" className="text-white/70 hover:text-white" data-testid="footer-social-youtube"><Youtube className="w-4 h-4" /></a>
            <span className="text-white/30">|</span>
            <button type="button" className="flex items-center gap-1.5 text-[12px] text-white/70 hover:text-white" data-testid="footer-language-switcher">
              <Globe className="w-3.5 h-3.5" /> English
            </button>
          </div>
        </div>
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 pb-6 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[11px] text-white/50">
          <a href="#" className="hover:text-white">Privacy</a>
          <a href="#" className="hover:text-white">Terms of use</a>
          <a href="#" className="hover:text-white">Cookie preferences</a>
          <a href="#" className="hover:text-white">Accessibility</a>
          <a href="#" className="hover:text-white">Modern slavery statement</a>
          <a href="#" className="hover:text-white">Site map</a>
        </div>
      </div>
    </footer>
  );
}
