import { NavLink } from "react-router-dom";
import { ChevronRight, X, LogOut } from "lucide-react";

/** Presentational sidebar for the authenticated app shell. */
export default function AppSidebar({ items, user, mobileOpen, onClose, onLogout }) {
  return (
    <aside
      data-testid="sidebar"
      className={`w-64 shrink-0 bg-[#0A4A1E] text-white flex flex-col fixed inset-y-0 left-0 z-50 transition-transform duration-200
        ${mobileOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`}
    >
      <div className="px-6 pt-7 pb-6 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-md bg-[#D1603D] grid place-items-center font-heading font-bold text-white">S</div>
          <div>
            <div className="font-heading font-bold text-[17px] tracking-tight leading-tight">SaloneHCM</div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-white/50 mt-0.5">Sierra Leone HCM</div>
          </div>
        </div>
        <button
          data-testid="sidebar-close"
          onClick={onClose}
          className="lg:hidden p-1.5 rounded text-white/70 hover:bg-white/10"
          aria-label="Close menu"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              data-testid={`nav-${item.label.toLowerCase().replace(/[^a-z]/g, "-")}`}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-all ${
                  isActive
                    ? "bg-white/10 text-white"
                    : "text-white/70 hover:text-white hover:bg-white/5"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className="w-[18px] h-[18px]" strokeWidth={1.5} />
                  <span className="flex-1">{item.label}</span>
                  {isActive && <ChevronRight className="w-3.5 h-3.5 opacity-60" />}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>
      <div className="p-3 border-t border-white/10">
        <div className="px-3 py-2 rounded-md flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-[#0F6428] grid place-items-center font-medium text-sm">
            {user.name?.[0] || "U"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{user.name}</div>
            <div className="text-[11px] uppercase tracking-wider text-white/50">{user.role}</div>
          </div>
          <button
            data-testid="logout-button"
            onClick={onLogout}
            className="p-1.5 rounded hover:bg-white/10 text-white/70 hover:text-white transition"
            title="Logout"
          >
            <LogOut className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>
      </div>
    </aside>
  );
}
