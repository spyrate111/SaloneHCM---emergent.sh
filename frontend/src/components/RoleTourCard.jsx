/**
 * One-time welcome card for HR Managers & Payroll Officers — shown on their
 * first sign-in, summarising what the role can do and where. Dismiss persists
 * via POST /users/me/role-tour-seen (never shown again for that user).
 */
import { useState } from "react";
import api from "../lib/api";
import { X, Briefcase, Calculator, ArrowRight } from "lucide-react";

const TOURS = {
  hr: {
    icon: Briefcase,
    title: "You're set up as HR Manager",
    accent: "bg-[#0A4A1E]",
    items: [
      ["Employees", "Add, edit and organise staff records — full control"],
      ["Leave", "Approve any request, see the team calendar & coverage warnings"],
      ["Talent → Learning", "Track training progress and send reminder nudges"],
      ["Performance & Benefits", "Run review cycles and manage benefit plans"],
      ["Civil Service", "Establishment control, promotions and sector presets"],
    ],
    footnote: "Payroll money movement and user accounts stay with Admins and Payroll Officers.",
  },
  payroll: {
    icon: Calculator,
    title: "You're set up as Payroll Officer",
    accent: "bg-[#26547C]",
    items: [
      ["Payroll Engine", "Preview and commit payroll runs, payslip PDFs & SMS"],
      ["Recurring Schedules", "Automate monthly runs and what-if simulations"],
      ["Payroll Vouchers", "Voucher packs, branch payout rails & QR scan log"],
      ["Compliance & Tax", "NRA PAYE / NASSIT filings and exports"],
      ["Employees", "Directory is read-only for you — HR owns the records"],
    ],
    footnote: "People management and user accounts stay with Admins and HR.",
  },
};

export default function RoleTour({ user }) {
  const [dismissed, setDismissed] = useState(false);
  const tour = TOURS[user?.role];
  if (!tour || dismissed || user?.role_tour_seen) return null;
  const Icon = tour.icon;
  const close = () => {
    setDismissed(true);
    api.post("/users/me/role-tour-seen").catch(() => {});
  };
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="role-tour-card">
      <div className={`${tour.accent} px-6 py-4 flex items-center gap-3`}>
        <Icon className="w-5 h-5 text-white" strokeWidth={1.5} />
        <h3 className="font-heading text-lg font-semibold text-white">{tour.title}</h3>
        <button onClick={close} className="ml-auto text-white/80 hover:text-white" data-testid="role-tour-dismiss" title="Got it — don't show again">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="px-6 py-4 grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2.5">
        {tour.items.map(([where, what]) => (
          <div key={where} className="flex items-start gap-2 text-sm">
            <ArrowRight className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-[#8B6A14]" />
            <span><b className="font-semibold text-[#1A1C1E]">{where}</b>{" — "}<span className="text-[#525860]">{what}</span></span>
          </div>
        ))}
      </div>
      <div className="px-6 pb-4 flex items-center justify-between gap-3 flex-wrap">
        <span className="text-[11px] text-[#8A8F96]">{tour.footnote}</span>
        <button onClick={close} className="text-xs font-semibold bg-[#0A4A1E] text-white px-4 py-2 rounded-md hover:bg-[#063514]" data-testid="role-tour-got-it">
          Got it
        </button>
      </div>
    </div>
  );
}
