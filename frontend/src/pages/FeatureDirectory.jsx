import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useFeatures } from "../lib/features";
import { NAV } from "../lib/nav";
import { Compass, ArrowRight, Lock, ShieldAlert } from "lucide-react";

// Descriptions + grouping keyed by route. Route/feature/role gating stays in lib/nav.js.
const META = {
  "/dashboard": { group: "Core HR", desc: "KPIs, headcount, payroll trends and pending items at a glance." },
  "/employees": { group: "Core HR", desc: "Employee records, hiring, terminations and profiles." },
  "/leave": { group: "Core HR", desc: "Leave requests, balances and manager approvals." },
  "/attendance": { group: "Core HR", desc: "Clock-in/out, timesheets, offline-capable ESS attendance." },
  "/self-service": { group: "Core HR", desc: "Your payslips, acknowledgements and personal records." },
  "/team": { group: "Core HR", desc: "Manager view of direct reports and team approvals." },
  "/documents": { group: "Core HR", desc: "Secure document vault with tenant-scoped cloud storage." },
  "/payroll": { group: "Payroll & Finance", desc: "Gross-to-net runs with NRA PAYE bands and NASSIT, payslip PDFs, bank files." },
  "/schedules": { group: "Payroll & Finance", desc: "Recurring auto-run payroll schedules." },
  "/vouchers": { group: "Payroll & Finance", desc: "Centralized payroll voucher repository — branch submission, supervisor/finance/MoF approval chain, immutable audit trail." },
  "/loans": { group: "Payroll & Finance", desc: "Salary advances with automatic payroll repayment deductions." },
  "/simulator": { group: "Payroll & Finance", desc: "What-if payroll scenarios, comparisons and decision-brief PDFs." },
  "/billing": { group: "Payroll & Finance", desc: "Your SaloneHCM subscription — bank transfer or Stripe." },
  "/compliance": { group: "Payroll & Finance", desc: "NRA PAYE returns, NASSIT filings and compliance score." },
  "/civil-service": { group: "Government", desc: "Grades & steps, allowances, budget codes, retro-pay, ghost-worker audit." },
  "/establishment": { group: "Government", desc: "Approved posts vs filled — vacancy and overrun control." },
  "/ministry": { group: "Government", desc: "Ministry-level payroll rollups for MDA reporting." },
  "/promotion": { group: "Government", desc: "Promotion boards and grade progression workflows." },
  "/sms-logs": { group: "Government", desc: "Bulk SMS payslip delivery audit trail." },
  "/talent": { group: "Talent & Performance", desc: "Recruitment ATS with Kanban, training programs and certificates." },
  "/performance": { group: "Talent & Performance", desc: "Review cycles: self-assessment, manager scoring, analytics." },
  "/benefits": { group: "Talent & Performance", desc: "Benefit plans and employee enrollments." },
  "/assistant": { group: "Intelligence", desc: "AI assistant with tenant context and action mode." },
  "/analytics": { group: "Intelligence", desc: "Workforce and payroll analytics dashboards." },
  "/users": { group: "Administration", desc: "Invite users, reset passwords, grant Finance/MoF flags." },
  "/audit": { group: "Administration", desc: "Every sensitive action, logged and searchable." },
  "/settings": { group: "Administration", desc: "Organization profile, tier plan, integrations, 2FA, transparency portal." },
  "/sector-presets": { group: "Administration", desc: "Industry presets for departments and grades." },
  "/companies": { group: "Administration", desc: "Platform tenants — create, switch, manage tiers." },
  "/admin/videos": { group: "Administration", desc: "Manage the public training video library." },
};

const GROUP_ORDER = ["Core HR", "Payroll & Finance", "Government", "Talent & Performance", "Intelligence", "Administration"];

export default function FeatureDirectory() {
  const { user } = useAuth();
  const { has } = useFeatures();
  const [tiers, setTiers] = useState([]);

  useEffect(() => {
    api.get("/company/tiers").then((r) => setTiers(r.data)).catch(() => setTiers([]));
  }, []);

  const minTierFor = useMemo(() => {
    const m = {};
    [...tiers].sort((a, b) => a.rank - b.rank).forEach((t) => {
      (t.features || []).forEach((f) => { if (!(f in m)) m[f] = t.label; });
    });
    return m;
  }, [tiers]);

  const entries = NAV.filter((n) => META[n.to]).map((n) => {
    const meta = META[n.to];
    const roleOk = n.roles.includes(user?.role);
    const featureOk = !n.feature || has(n.feature);
    let status = "available";
    let statusLabel = "";
    if (!featureOk) {
      status = "tier";
      statusLabel = `Requires ${minTierFor[n.feature] || "a higher plan"}`;
    } else if (!roleOk) {
      status = "role";
      statusLabel = n.roles.includes("admin") ? "Admin only" : "Superadmin only";
    }
    return { ...n, ...meta, status, statusLabel };
  });

  const groups = GROUP_ORDER.map((g) => ({ name: g, items: entries.filter((e) => e.group === g) }))
    .filter((g) => g.items.length);

  const availableCount = entries.filter((e) => e.status === "available").length;

  return (
    <div className="space-y-6" data-testid="directory-page">
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 rounded-md bg-[#133326] grid place-items-center shrink-0">
            <Compass className="w-5 h-5 text-white" strokeWidth={1.6} />
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">All Modules</div>
            <h1 className="font-heading text-3xl font-bold mt-1">Feature Directory</h1>
            <p className="text-sm text-[#525860] mt-1 max-w-2xl">
              Every module in SaloneHCM and what unlocks it. You can open{" "}
              <span className="font-semibold text-[#133326]" data-testid="directory-available-count">{availableCount} of {entries.length}</span>{" "}
              modules with your current role ({user?.role}) and plan{user?.company?.label ? ` (${user.company.label})` : ""}.
            </p>
          </div>
        </div>
      </div>

      {groups.map((g) => (
        <section key={g.name} data-testid={`directory-group-${g.name.toLowerCase().replace(/[^a-z]+/g, "-")}`}>
          <h2 className="text-[11px] uppercase tracking-[0.18em] text-[#525860] mb-3">{g.name}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {g.items.map((e) => <ModuleCard key={e.to} entry={e} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

function ModuleCard({ entry }) {
  const Icon = entry.icon;
  const locked = entry.status !== "available";
  const inner = (
    <div className={`bg-white border rounded-lg p-4 h-full flex flex-col gap-2 transition ${locked ? "border-[#E2DFD6] opacity-70" : "border-[#E2DFD6] hover:border-[#133326] hover:shadow-sm"}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className={`w-8 h-8 rounded-md grid place-items-center ${locked ? "bg-[#F1EEE6]" : "bg-[#E6F4EC]"}`}>
            <Icon className={`w-4 h-4 ${locked ? "text-[#A1A5AB]" : "text-[#133326]"}`} strokeWidth={1.6} />
          </div>
          <span className="font-heading text-sm font-semibold">{entry.label}</span>
        </div>
        {entry.status === "available" && <ArrowRight className="w-4 h-4 text-[#26547C]" strokeWidth={1.6} />}
        {entry.status === "tier" && <Lock className="w-4 h-4 text-[#8B6A14]" strokeWidth={1.6} />}
        {entry.status === "role" && <ShieldAlert className="w-4 h-4 text-[#B84F2F]" strokeWidth={1.6} />}
      </div>
      <p className="text-xs text-[#525860] leading-relaxed flex-1">{entry.desc}</p>
      {locked ? (
        <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full w-fit ${entry.status === "tier" ? "bg-[#FBF3D9] text-[#8B6A14]" : "bg-[#FBE9DF] text-[#B84F2F]"}`}>
          {entry.statusLabel}
        </span>
      ) : (
        <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full w-fit bg-[#E6F4EC] text-[#2D7A5D]">Available</span>
      )}
    </div>
  );
  return entry.status === "available" ? (
    <Link to={entry.to} data-testid={`directory-item-${entry.to.replace(/\//g, "")}`}>{inner}</Link>
  ) : (
    <div data-testid={`directory-item-${entry.to.replace(/\//g, "")}`}>{inner}</div>
  );
}
