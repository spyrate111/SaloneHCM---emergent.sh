import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  LayoutDashboard, Users, Calculator, ShieldCheck, CalendarDays, Clock,
  Sparkles, Settings, UserCircle, LogOut, ChevronRight, ScrollText,
  Heart, GraduationCap, BarChart3, FlaskConical,
} from "lucide-react";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "employee"] },
  { to: "/employees", label: "Employees", icon: Users, roles: ["admin"] },
  { to: "/payroll", label: "Payroll Engine", icon: Calculator, roles: ["admin"] },
  { to: "/simulator", label: "What-if Simulator", icon: FlaskConical, roles: ["admin"] },
  { to: "/compliance", label: "Compliance & Tax", icon: ShieldCheck, roles: ["admin"] },
  { to: "/leave", label: "Leave", icon: CalendarDays, roles: ["admin", "employee"] },
  { to: "/attendance", label: "Time & Attendance", icon: Clock, roles: ["admin", "employee"] },
  { to: "/benefits", label: "Benefits", icon: Heart, roles: ["admin", "employee"] },
  { to: "/talent", label: "Talent", icon: GraduationCap, roles: ["admin", "employee"] },
  { to: "/analytics", label: "Analytics", icon: BarChart3, roles: ["admin"] },
  { to: "/assistant", label: "AI Assistant", icon: Sparkles, roles: ["admin", "employee"] },
  { to: "/self-service", label: "Self Service", icon: UserCircle, roles: ["employee", "admin"] },
  { to: "/audit", label: "Audit Log", icon: ScrollText, roles: ["admin"] },
  { to: "/team", label: "My Team", icon: UserCircle, roles: ["admin", "employee"] },
  { to: "/settings", label: "Settings", icon: Settings, roles: ["admin"] },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  if (!user) return null;
  const items = NAV.filter((n) => n.roles.includes(user.role));

  return (
    <div className="min-h-screen flex bg-[#F7F6F2]">
      <aside className="w-64 shrink-0 bg-[#133326] text-white flex flex-col fixed inset-y-0 left-0 z-30">
        <div className="px-6 pt-7 pb-6">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-md bg-[#D1603D] grid place-items-center font-heading font-bold text-white">S</div>
            <div>
              <div className="font-heading font-bold text-[17px] tracking-tight leading-tight">SaloneHCM</div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-white/50 mt-0.5">Sierra Leone HCM</div>
            </div>
          </div>
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
            <div className="w-9 h-9 rounded-full bg-[#1F4A38] grid place-items-center font-medium text-sm">
              {user.name?.[0] || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{user.name}</div>
              <div className="text-[11px] uppercase tracking-wider text-white/50">{user.role}</div>
            </div>
            <button
              data-testid="logout-button"
              onClick={async () => { await logout(); nav("/login"); }}
              className="p-1.5 rounded hover:bg-white/10 text-white/70 hover:text-white transition"
              title="Logout"
            >
              <LogOut className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 ml-64 min-h-screen flex flex-col">
        <header className="sticky top-0 z-20 h-16 px-8 flex items-center justify-between border-b border-[#E2DFD6] bg-white/85 backdrop-blur">
          <div>
            <div className="text-[11px] uppercase tracking-[0.16em] text-[#525860]">Republic of Sierra Leone</div>
            <div className="text-sm font-medium text-[#1A1C1E]">SaloneHCM Professional</div>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden md:inline-flex items-center gap-2 text-xs text-[#525860] font-data px-3 py-1.5 rounded-full border border-[#E2DFD6] bg-white">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2D7A5D]" /> NRA & NASSIT compliant
            </span>
          </div>
        </header>
        <main className="flex-1 p-8 max-w-[1400px] w-full mx-auto animate-fade-up">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
