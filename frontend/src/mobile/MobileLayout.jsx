/**
 * Mobile PWA shell — bottom nav, safe-area padding, mobile-first typography.
 * The shell renders inside `<ProtectedRoute>` so all children can trust that
 * `user` is populated. All screens under /m/* live in ./pages/*.jsx and use the
 * same authenticated API instance as the desktop app.
 *
 * IMPORTANT: this layout is designed so that a future Capacitor / React
 * Native shell can point at these routes with zero refactor — the layout is
 * pure React + Tailwind and does not depend on window internals.
 */
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { Home, FileText, Calendar, Timer, ClipboardCheck, User2, WifiOff } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const TABS = [
  { to: "/m", label: "Home", icon: Home, testid: "m-nav-home", roles: null, end: true },
  { to: "/m/payslips", label: "Pay", icon: FileText, testid: "m-nav-payslips", roles: null },
  { to: "/m/leave", label: "Leave", icon: Calendar, testid: "m-nav-leave", roles: null },
  { to: "/m/clock", label: "Clock", icon: Timer, testid: "m-nav-clock", roles: null },
  { to: "/m/vouchers", label: "Vouchers", icon: ClipboardCheck, testid: "m-nav-vouchers",
    roles: ["admin", "superadmin", "mof_approver", "finance_officer", "supervisor"] },
  { to: "/m/profile", label: "Profile", icon: User2, testid: "m-nav-profile", roles: null },
];

export default function MobileLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [online, setOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  const visibleTabs = TABS.filter((t) => !t.roles || t.roles.includes(user?.role));

  return (
    <div className="min-h-screen flex flex-col bg-[#F7F6F2]" data-testid="mobile-shell">
      {/* header */}
      <header className="bg-[#0A4A1E] text-white sticky top-0 z-30" style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}>
        <div className="flex items-center justify-between px-4 h-14">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-white/10 flex items-center justify-center overflow-hidden">
              <img src="/icon-192.png" alt="SaloneHCM" className="w-6 h-6" />
            </div>
            <div>
              <div className="text-sm font-semibold leading-none">SaloneHCM</div>
              <div className="text-[10px] text-white/70 leading-tight mt-0.5">
                {user?.name || user?.email}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!online && (
              <span className="text-[10px] bg-[#8B6A14] text-white px-2 py-1 rounded flex items-center gap-1" data-testid="mobile-offline-pill">
                <WifiOff className="w-3 h-3" /> Offline
              </span>
            )}
            <button
              data-testid="mobile-logout"
              onClick={() => { logout(); nav("/login"); }}
              className="text-[11px] bg-white/10 hover:bg-white/20 text-white px-2.5 py-1.5 rounded"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* main scroll area */}
      <main className="flex-1 overflow-y-auto pb-24" data-testid="mobile-main">
        <Outlet />
      </main>

      {/* bottom nav */}
      <nav
        className="fixed bottom-0 inset-x-0 bg-white border-t border-[#E2DFD6] z-40"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
        data-testid="mobile-bottom-nav"
      >
        <div className="flex items-stretch">
          {visibleTabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              data-testid={t.testid}
              className={({ isActive }) =>
                `flex-1 flex flex-col items-center py-2 text-[10px] font-medium ` +
                (isActive
                  ? "text-[#0A4A1E]"
                  : "text-[#525860] hover:text-[#0A4A1E]")
              }
            >
              <t.icon className={`w-5 h-5 mb-1 ${loc.pathname === t.to ? "" : "opacity-70"}`} />
              {t.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
