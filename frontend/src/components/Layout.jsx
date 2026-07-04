import { useEffect, useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useFeatures, TIER_COLORS } from "../lib/features";
import { filterNavForUser } from "../lib/nav";
import AppSidebar from "./AppSidebar";
import AppHeader from "./AppHeader";

export default function Layout() {
  const { user, logout } = useAuth();
  const { has, company, tier, isSuperAdmin } = useFeatures();
  const nav = useNavigate();
  const loc = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close drawer on route change
  useEffect(() => { setMobileOpen(false); }, [loc.pathname]);

  if (!user) return null;
  const items = filterNavForUser(user, has);
  const tierKey = tier || "lite";
  const tierColor = TIER_COLORS[tierKey] || TIER_COLORS.lite;

  const handleLogout = async () => { await logout(); nav("/login"); };

  return (
    <div className="min-h-screen flex bg-[#F7F6F2]">
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      <AppSidebar
        items={items}
        user={user}
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        onLogout={handleLogout}
      />

      <div className="flex-1 lg:ml-64 min-h-screen flex flex-col min-w-0">
        <AppHeader
          company={company}
          tierColor={tierColor}
          isSuperAdmin={isSuperAdmin}
          onOpenSidebar={() => setMobileOpen(true)}
        />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-[1400px] w-full mx-auto animate-fade-up">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
