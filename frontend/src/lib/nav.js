import {
  LayoutDashboard, Users, Calculator, ShieldCheck, CalendarDays, Clock,
  Sparkles, Settings, UserCircle, ScrollText, Heart, GraduationCap,
  BarChart3, FlaskConical, FolderArchive, Building2, UserCog, MessageSquare,
  Repeat, Landmark, Award, Wallet, CreditCard, Layers, TrendingUp, Video, FileCheck2, Compass,
} from "lucide-react";

// Role groups — keep in sync with backend core.can_role / require_roles.
const ALL = ["admin", "superadmin", "hr", "payroll", "manager", "employee"];
const ADMIN = ["admin", "superadmin"];
const HR = ["admin", "superadmin", "hr"];
const PAY = ["admin", "superadmin", "payroll"];
const STAFF = ["admin", "superadmin", "hr", "payroll"]; // employees directory
const INSIGHT = ["admin", "superadmin", "hr", "payroll"];

// Single source-of-truth for the app sidebar navigation.
// Each entry: { to, label, icon, roles, feature? }
export const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ALL },
  { to: "/directory", label: "Feature Directory", icon: Compass, roles: ALL },
  { to: "/employees", label: "Employees", icon: Users, roles: STAFF, feature: "employees" },
  { to: "/payroll", label: "Payroll Engine", icon: Calculator, roles: PAY, feature: "payroll" },
  { to: "/schedules", label: "Recurring Schedules", icon: Repeat, roles: PAY, feature: "payroll" },
  { to: "/vouchers", label: "Payroll Vouchers", icon: FileCheck2, roles: ALL, feature: "payroll_vouchers" },
  { to: "/simulator", label: "What-if Simulator", icon: FlaskConical, roles: PAY, feature: "simulator" },
  { to: "/compliance", label: "Compliance & Tax", icon: ShieldCheck, roles: PAY, feature: "compliance" },
  { to: "/leave", label: "Leave", icon: CalendarDays, roles: ALL, feature: "leave" },
  { to: "/attendance", label: "Time & Attendance", icon: Clock, roles: ALL, feature: "attendance" },
  { to: "/benefits", label: "Benefits", icon: Heart, roles: ALL, feature: "benefits" },
  { to: "/talent", label: "Talent", icon: GraduationCap, roles: ALL, feature: "talent" },
  { to: "/performance", label: "Performance", icon: Sparkles, roles: ALL, feature: "talent" },
  { to: "/documents", label: "Document Vault", icon: FolderArchive, roles: ALL, feature: "documents" },
  { to: "/analytics", label: "Analytics", icon: BarChart3, roles: INSIGHT, feature: "analytics" },
  { to: "/ministry", label: "Ministry rollup", icon: Landmark, roles: PAY, feature: "ministry_reports" },
  { to: "/civil-service", label: "Civil Service", icon: Award, roles: HR, feature: "civil_service" },
  { to: "/establishment", label: "Establishment", icon: Building2, roles: HR, feature: "establishment_control" },
  { to: "/sector-presets", label: "Sector presets", icon: Layers, roles: HR, feature: "sector_presets" },
  { to: "/promotion", label: "Promotions", icon: TrendingUp, roles: HR, feature: "civil_service" },
  { to: "/loans", label: "Loans", icon: Wallet, roles: ALL, feature: "loans_advances" },
  { to: "/billing", label: "Billing", icon: CreditCard, roles: ADMIN },
  { to: "/assistant", label: "AI Assistant", icon: Sparkles, roles: ALL, feature: "ai_assistant" },
  { to: "/self-service", label: "Self Service", icon: UserCircle, roles: ALL },
  { to: "/audit", label: "Audit Log", icon: ScrollText, roles: ADMIN, feature: "audit_log" },
  { to: "/sms-logs", label: "SMS Audit", icon: MessageSquare, roles: PAY, feature: "bulk_sms_payslips" },
  { to: "/team", label: "My Team", icon: UserCircle, roles: ALL },
  { to: "/users", label: "Users & Access", icon: UserCog, roles: ADMIN },
  { to: "/settings", label: "Settings", icon: Settings, roles: ADMIN },
  { to: "/companies", label: "Tenants", icon: Building2, roles: ["superadmin"] },
  { to: "/admin/videos", label: "Marketing Videos", icon: Video, roles: ["superadmin"] },
];

// Filter based on user role + which features their company tier grants.
// `has` is the `useFeatures().has(featureName) => boolean` helper.
export function filterNavForUser(user, has) {
  if (!user) return [];
  return NAV.filter((n) => n.roles.includes(user.role) && (!n.feature || has(n.feature)));
}
