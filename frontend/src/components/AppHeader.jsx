import { Menu, Smartphone } from "lucide-react";
import { Link } from "react-router-dom";
import CompanySwitcher from "./CompanySwitcher";

/** Top header for the authenticated app shell. */
export default function AppHeader({ company, tierColor, isSuperAdmin, onOpenSidebar }) {
  return (
    <header className="sticky top-0 z-30 h-16 px-4 sm:px-8 flex items-center justify-between border-b border-[#E2DFD6] bg-white/85 backdrop-blur">
      <div className="flex items-center gap-3 min-w-0">
        <button
          data-testid="sidebar-open"
          onClick={onOpenSidebar}
          className="lg:hidden p-2 -ml-2 rounded text-[#525860] hover:bg-[#F1EEE6]"
          aria-label="Open menu"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#525860] hidden sm:block" data-testid="header-company-country">
            Republic of Sierra Leone
          </div>
          <div className="text-sm font-medium text-[#1A1C1E] truncate" data-testid="header-company-name">
            {company?.name || "SaloneHCM"}
          </div>
        </div>
        {isSuperAdmin && <div className="hidden md:block"><CompanySwitcher /></div>}
      </div>
      <div className="flex items-center gap-2 sm:gap-3">
        <Link
          to="/m"
          data-testid="header-mobile-launcher"
          className="inline-flex items-center gap-1.5 text-[11px] font-medium text-[#0A4A1E] bg-[#E4F7E7] hover:bg-[#D6F0DB] px-2.5 py-1.5 rounded-full"
          title="Open the mobile app view"
        >
          <Smartphone className="w-3.5 h-3.5" /> Mobile
        </Link>
        <span
          data-testid="header-tier-badge"
          className={`hidden sm:inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-medium px-2.5 py-1 rounded-full ${tierColor}`}
        >
          {company?.label || "SaloneHCM"}
        </span>
        <span className="hidden xl:inline-flex items-center gap-2 text-xs text-[#525860] font-data px-3 py-1.5 rounded-full border border-[#E2DFD6] bg-white">
          <span className="w-1.5 h-1.5 rounded-full bg-[#17A035]" /> NRA & NASSIT compliant
        </span>
      </div>
    </header>
  );
}
