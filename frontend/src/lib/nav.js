import {
  LayoutDashboard, Users, Calculator, ShieldCheck, CalendarDays, Clock,
  Sparkles, Settings, UserCircle, ScrollText, Heart, GraduationCap,
  BarChart3, FlaskConical, FolderArchive, Building2, UserCog, MessageSquare,
  Repeat, Landmark, Award, Wallet, CreditCard, Layers, TrendingUp, Video, FileCheck2,
} from "lucide-react";

// Single source-of-truth for the app sidebar navigation.
// Each entry: { to, label, icon, roles, feature? }
export const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "superadmin", "employee"] },
  { to: "/employees", label: "Employees", icon: Users, roles: ["admin", "superadmin"], feature: "employees" },
  { to: "/payroll", label: "Payroll Engine", icon: Calculator, roles: ["admin", "superadmin"], feature: "payroll" },
  { to: "/schedules", label: "Recurring Schedules", icon: Repeat, roles: ["admin", "superadmin"], feature: "payroll" },
  { to: "/vouchers", label: "Payroll Vouchers", icon: FileCheck2, roles: ["admin", "superadmin", "employee"], feature: "payroll_vouchers" },
  { to: "/simulator", label: "What-if Simulator", icon: FlaskConical, roles: ["admin", "superadmin"], feature: "simulator" },
  { to: "/compliance", label: "Compliance & Tax", icon: ShieldCheck, roles: ["admin", "superadmin"], feature: "compliance" },
  { to: "/leave", label: "Leave", icon: CalendarDays, roles: ["admin", "superadmin", "employee"], feature: "leave" },
  { to: "/attendance", label: "Time & Attendance", icon: Clock, roles: ["admin", "superadmin", "employee"], feature: "attendance" },
  { to: "/benefits", label: "Benefits", icon: Heart, roles: ["admin", "superadmin", "employee"], feature: "benefits" },
  { to: "/talent", label: "Talent", icon: GraduationCap, roles: ["admin", "superadmin", "employee"], feature: "talent" },
  { to: "/performance", label: "Performance", icon: Sparkles, roles: ["admin", "superadmin", "employee"], feature: "talent" },
  { to: "/documents", label: "Document Vault", icon: FolderArchive, roles: ["admin", "superadmin", "employee"], feature: "documents" },
  { to: "/analytics", label: "Analytics", icon: BarChart3, roles: ["admin", "superadmin"], feature: "analytics" },
  { to: "/ministry", label: "Ministry rollup", icon: Landmark, roles: ["admin", "superadmin"], feature: "ministry_reports" },
  { to: "/civil-service", label: "Civil Service", icon: Award, roles: ["admin", "superadmin"], feature: "civil_service" },
  { to: "/establishment", label: "Establishment", icon: Building2, roles: ["admin", "superadmin"], feature: "establishment_control" },
  { to: "/sector-presets", label: "Sector presets", icon: Layers, roles: ["admin", "superadmin"], feature: "sector_presets" },
  { to: "/promotion", label: "Promotions", icon: TrendingUp, roles: ["admin", "superadmin"], feature: "civil_service" },
  { to: "/loans", label: "Loans", icon: Wallet, roles: ["admin", "superadmin", "employee"], feature: "loans_advances" },
  { to: "/billing", label: "Billing", icon: CreditCard, roles: ["admin", "superadmin"] },
  { to: "/assistant", label: "AI Assistant", icon: Sparkles, roles: ["admin", "superadmin", "employee"], feature: "ai_assistant" },
  { to: "/self-service", label: "Self Service", icon: UserCircle, roles: ["employee", "admin", "superadmin"] },
  { to: "/audit", label: "Audit Log", icon: ScrollText, roles: ["admin", "superadmin"], feature: "audit_log" },
  { to: "/sms-logs", label: "SMS Audit", icon: MessageSquare, roles: ["admin", "superadmin"], feature: "bulk_sms_payslips" },
  { to: "/team", label: "My Team", icon: UserCircle, roles: ["admin", "superadmin", "employee"] },
  { to: "/users", label: "Users & Access", icon: UserCog, roles: ["admin", "superadmin"] },
  { to: "/settings", label: "Settings", icon: Settings, roles: ["admin", "superadmin"] },
  { to: "/companies", label: "Tenants", icon: Building2, roles: ["superadmin"] },
  { to: "/admin/videos", label: "Marketing Videos", icon: Video, roles: ["superadmin"] },
];

// Filter based on user role + which features their company tier grants.
// `has` is the `useFeatures().has(featureName) => boolean` helper.
export function filterNavForUser(user, has) {
  if (!user) return [];
  return NAV.filter((n) => n.roles.includes(user.role) && (!n.feature || has(n.feature)));
}
