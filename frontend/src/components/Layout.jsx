import { useEffect, useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useFeatures, TIER_COLORS } from "../lib/features";
import api, { setToken } from "../lib/api";
import { toast } from "sonner";
import {
  LayoutDashboard, Users, Calculator, ShieldCheck, CalendarDays, Clock,
  Sparkles, Settings, UserCircle, LogOut, ChevronRight, ScrollText,
  Heart, GraduationCap, BarChart3, FlaskConical, FolderArchive,
  Building2, UserCog, ChevronDown, ArrowRightLeft, MessageSquare,
} from "lucide-react";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "superadmin", "employee"] },
  { to: "/employees", label: "Employees", icon: Users, roles: ["admin", "superadmin"], feature: "employees" },
  { to: "/payroll", label: "Payroll Engine", icon: Calculator, roles: ["admin", "superadmin"], feature: "payroll" },
  { to: "/simulator", label: "What-if Simulator", icon: FlaskConical, roles: ["admin", "superadmin"], feature: "simulator" },
  { to: "/compliance", label: "Compliance & Tax", icon: ShieldCheck, roles: ["admin", "superadmin"], feature: "compliance" },
  { to: "/leave", label: "Leave", icon: CalendarDays, roles: ["admin", "superadmin", "employee"], feature: "leave" },
  { to: "/attendance", label: "Time & Attendance", icon: Clock, roles: ["admin", "superadmin", "employee"], feature: "attendance" },
  { to: "/benefits", label: "Benefits", icon: Heart, roles: ["admin", "superadmin", "employee"], feature: "benefits" },
  { to: "/talent", label: "Talent", icon: GraduationCap, roles: ["admin", "superadmin", "employee"], feature: "talent" },
  { to: "/documents", label: "Document Vault", icon: FolderArchive, roles: ["admin", "superadmin", "employee"], feature: "documents" },
  { to: "/analytics", label: "Analytics", icon: BarChart3, roles: ["admin", "superadmin"], feature: "analytics" },
  { to: "/assistant", label: "AI Assistant", icon: Sparkles, roles: ["admin", "superadmin", "employee"], feature: "ai_assistant" },
  { to: "/self-service", label: "Self Service", icon: UserCircle, roles: ["employee", "admin", "superadmin"] },
  { to: "/audit", label: "Audit Log", icon: ScrollText, roles: ["admin", "superadmin"], feature: "audit_log" },
  { to: "/sms-logs", label: "SMS Audit", icon: MessageSquare, roles: ["admin", "superadmin"], feature: "bulk_sms_payslips" },
  { to: "/team", label: "My Team", icon: UserCircle, roles: ["admin", "superadmin", "employee"] },
  { to: "/users", label: "Users & Access", icon: UserCog, roles: ["admin", "superadmin"] },
  { to: "/settings", label: "Settings", icon: Settings, roles: ["admin", "superadmin"] },
  { to: "/companies", label: "Tenants", icon: Building2, roles: ["superadmin"] },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { has, company, tier, isSuperAdmin } = useFeatures();
  const nav = useNavigate();
  if (!user) return null;
  const items = NAV.filter((n) => n.roles.includes(user.role) && (!n.feature || has(n.feature)));
  const tierKey = tier || "lite";
  const tierColor = TIER_COLORS[tierKey] || TIER_COLORS.lite;

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
          <div className="flex items-center gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.16em] text-[#525860]" data-testid="header-company-country">
                Republic of Sierra Leone
              </div>
              <div className="text-sm font-medium text-[#1A1C1E]" data-testid="header-company-name">
                {company?.name || "SaloneHCM"}
              </div>
            </div>
            {isSuperAdmin && <CompanySwitcher />}
          </div>
          <div className="flex items-center gap-3">
            <span
              data-testid="header-tier-badge"
              className={`hidden sm:inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-medium px-2.5 py-1 rounded-full ${tierColor}`}
            >
              {company?.label || "SaloneHCM"}
            </span>
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

function CompanySwitcher() {
  const { user, refetch } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/admin/companies").then((r) => setCompanies(r.data)).catch(() => {});
  }, []);

  const switchTo = async (cid) => {
    if (cid === user?.company_id) { setOpen(false); return; }
    setBusy(true);
    try {
      const r = await api.post(`/admin/companies/${cid}/switch`);
      setToken(r.data.token);
      await refetch();
      toast.success(`Switched to ${r.data.company.name}`);
      setOpen(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Switch failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative" data-testid="company-switcher">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-xs font-medium border border-[#E2DFD6] rounded-md px-2.5 py-1.5 hover:bg-[#F7F6F2]"
        data-testid="company-switcher-toggle"
      >
        <ArrowRightLeft className="w-3.5 h-3.5 text-[#525860]" strokeWidth={1.7} />
        Switch tenant
        <ChevronDown className={`w-3.5 h-3.5 text-[#525860] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute top-full mt-2 left-0 w-72 bg-white border border-[#E2DFD6] rounded-lg shadow-lg z-30 overflow-hidden" data-testid="company-switcher-menu">
          <div className="px-4 py-2.5 text-[10px] uppercase tracking-wider text-[#525860] border-b border-[#F1EEE6] bg-[#F7F6F2]">
            Tenants ({companies.length})
          </div>
          <div className="max-h-72 overflow-y-auto">
            {companies.map((c) => (
              <button
                key={c.id}
                disabled={busy}
                onClick={() => switchTo(c.id)}
                data-testid={`switcher-item-${c.id}`}
                className={`w-full text-left px-4 py-2.5 text-sm hover:bg-[#F7F6F2] flex items-center justify-between gap-2 ${c.id === user?.company_id ? "bg-[#E6F4EC]" : ""}`}
              >
                <div className="min-w-0">
                  <div className="font-medium truncate">{c.name}</div>
                  <div className="text-[10px] uppercase tracking-wider text-[#686D76]">{c.tier} · {c.active_headcount} active</div>
                </div>
                {c.id === user?.company_id && (
                  <span className="text-[9px] uppercase tracking-widest font-semibold bg-[#133326] text-white px-1.5 py-0.5 rounded-full">
                    Active
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
