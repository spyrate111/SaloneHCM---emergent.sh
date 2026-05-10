import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { fmtSLE } from "../lib/api";
import { ChevronLeft, Mail, Phone, MapPin, Briefcase, Calendar, Hash } from "lucide-react";

export default function EmployeeDetail() {
  const { id } = useParams();
  const [e, setE] = useState(null);
  const [slip, setSlip] = useState(null);

  useEffect(() => {
    api.get(`/employees/${id}`).then((r) => setE(r.data));
  }, [id]);

  useEffect(() => {
    if (!e) return;
    // compute slip via preview endpoint match
    api.post("/payroll/preview").then((r) => {
      const s = r.data.slips.find((x) => x.employee_id === e.id);
      if (s) setSlip(s);
    }).catch(() => {});
  }, [e]);

  if (!e) return <div className="text-sm text-[#525860]">Loading…</div>;

  return (
    <div className="space-y-6" data-testid="employee-detail">
      <Link to="/employees" className="inline-flex items-center gap-1.5 text-sm text-[#525860] hover:text-[#1A1C1E]">
        <ChevronLeft className="w-4 h-4" /> Back to employees
      </Link>

      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 flex items-center gap-5">
        <div className="w-20 h-20 rounded-full bg-[#133326] text-white grid place-items-center font-heading text-2xl font-bold">
          {e.first_name?.[0]}{e.last_name?.[0]}
        </div>
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{e.department}</div>
          <h1 className="font-heading text-3xl font-bold mt-1">{e.first_name} {e.last_name}</h1>
          <div className="text-[#525860] text-sm mt-1">{e.job_title} · {e.employment_type}</div>
        </div>
        <span className="text-[11px] font-medium px-3 py-1 rounded-full bg-[#E6F4EC] text-[#2D7A5D] uppercase tracking-wider">
          {e.status}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 bg-white border border-[#E2DFD6] rounded-lg p-6 space-y-4">
          <h3 className="font-heading text-lg font-semibold">Profile</h3>
          {[
            [Mail, "Email", e.email],
            [Phone, "Phone", e.phone],
            [MapPin, "Location", e.location],
            [Briefcase, "Job title", e.job_title],
            [Calendar, "Hire date", e.hire_date],
            [Hash, "NASSIT No.", e.nassit_no],
            [Hash, "TIN", e.tin],
          ].map(([Icon, label, val]) => (
            <div key={label} className="flex items-center gap-4 py-2 border-b border-[#F1EEE6] last:border-0">
              <Icon className="w-4 h-4 text-[#A1A5AB]" strokeWidth={1.5} />
              <div className="text-xs uppercase tracking-wider text-[#525860] w-32">{label}</div>
              <div className="text-sm text-[#1A1C1E] font-data">{val || "—"}</div>
            </div>
          ))}
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <h3 className="font-heading text-lg font-semibold mb-4">Compensation (monthly)</h3>
          <div className="space-y-3 font-data">
            {[
              ["Basic", fmtSLE(e.basic_salary_sle)],
              ["Allowances", fmtSLE(e.allowances_sle)],
              ["Gross", fmtSLE((e.basic_salary_sle || 0) + (e.allowances_sle || 0))],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm">
                <span className="text-[#686D76]">{k}</span><span className="text-[#1A1C1E] font-medium">{v}</span>
              </div>
            ))}
          </div>
          {slip && (
            <div className="mt-5 pt-4 border-t border-[#E2DFD6] space-y-3 font-data">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Estimated payslip</div>
              <div className="flex justify-between text-sm"><span className="text-[#686D76]">NASSIT (5%)</span><span>− {fmtSLE(slip.nassit_employee)}</span></div>
              <div className="flex justify-between text-sm"><span className="text-[#686D76]">PAYE</span><span>− {fmtSLE(slip.paye)}</span></div>
              <div className="flex justify-between text-base font-semibold pt-2 border-t border-[#E2DFD6]"><span>Net pay</span><span className="text-[#133326]">{fmtSLE(slip.net)}</span></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
