import { useEffect, useState } from "react";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function SelfService() {
  const { user } = useAuth();
  const [slip, setSlip] = useState(null);
  const [leaves, setLeaves] = useState([]);

  useEffect(() => {
    api.get("/payroll/my-payslip").then((r) => setSlip(r.data.slip));
    api.get("/leave").then((r) => setLeaves(r.data));
  }, []);

  return (
    <div className="space-y-6" data-testid="self-service-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Employee Self-Service</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Welcome, {user?.name}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <h3 className="font-heading text-lg font-semibold">My latest payslip</h3>
          {slip ? (
            <div className="mt-4 space-y-2 text-sm font-data">
              <div className="flex justify-between"><span className="text-[#525860]">Basic</span><span>{fmtSLE(slip.basic)}</span></div>
              <div className="flex justify-between"><span className="text-[#525860]">Allowances</span><span>{fmtSLE(slip.allowances)}</span></div>
              <div className="flex justify-between font-medium border-t border-[#E2DFD6] pt-2"><span>Gross</span><span>{fmtSLE(slip.gross)}</span></div>
              <div className="flex justify-between text-[#B83A3A]"><span>NASSIT (5%)</span><span>− {fmtSLE(slip.nassit_employee)}</span></div>
              <div className="flex justify-between text-[#B83A3A]"><span>PAYE</span><span>− {fmtSLE(slip.paye)}</span></div>
              <div className="flex justify-between text-base font-semibold border-t border-[#E2DFD6] pt-2"><span>Net pay</span><span className="text-[#133326]">{fmtSLE(slip.net)}</span></div>
            </div>
          ) : (
            <div className="text-sm text-[#686D76] mt-3">No payslip available yet.</div>
          )}
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <h3 className="font-heading text-lg font-semibold">My leave requests</h3>
          {leaves.length ? (
            <ul className="mt-3 divide-y divide-[#F1EEE6] text-sm">
              {leaves.map((l) => (
                <li key={l.id} className="py-2 flex justify-between">
                  <span className="capitalize">{l.leave_type} · <span className="text-[#525860] font-data">{l.start_date} → {l.end_date}</span></span>
                  <span className="text-[11px] uppercase tracking-wider text-[#686D76]">{l.status}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-[#686D76] mt-3">No requests yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}
