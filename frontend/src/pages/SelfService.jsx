import { useEffect, useState } from "react";
import api, { fmtSLE, API, getToken } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Download, FileText, CheckCircle2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

export default function SelfService() {
  const { user } = useAuth();
  const [slip, setSlip] = useState(null);
  const [history, setHistory] = useState([]);
  const [leaves, setLeaves] = useState([]);
  const [ackBusy, setAckBusy] = useState(null);
  const [acks, setAcks] = useState({}); // {run_id: true}

  const refresh = () => {
    api.get("/payroll/my-payslip").then((r) => setSlip(r.data.slip));
    api.get("/payroll/my-payslips").then((r) => setHistory(r.data));
    api.get("/leave").then((r) => setLeaves(r.data));
  };

  useEffect(() => { refresh(); }, []);

  const downloadPdf = async (rid, eid, name, period) => {
    const token = getToken();
    const res = await fetch(`${API}/payroll/runs/${rid}/payslip/${eid}.pdf`, { headers: { Authorization: `Bearer ${token}` } });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `payslip-${name.replace(/\s/g, "_")}-${period}.pdf`; a.click();
    URL.revokeObjectURL(url);
  };

  const acknowledge = async (rid) => {
    setAckBusy(rid);
    try {
      await api.post(`/civil-service/payslip-ack/${rid}`, { note: "Acknowledged via ESS" });
      setAcks((a) => ({ ...a, [rid]: true }));
      toast.success("Payslip acknowledged");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not acknowledge");
    } finally {
      setAckBusy(null);
    }
  };

  return (
    <div className="space-y-6" data-testid="self-service-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Employee Self-Service</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Welcome, {user?.name}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <h3 className="font-heading text-lg font-semibold">Estimated payslip (current period)</h3>
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

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="my-payslips">
        <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center justify-between">
          <div>
            <h3 className="font-heading text-lg font-semibold flex items-center gap-2"><FileText className="w-4 h-4" /> Payslip history</h3>
            <p className="text-xs text-[#686D76] mt-0.5">Download official PDF payslips from completed payroll runs.</p>
          </div>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Period", "Gross", "NASSIT", "PAYE", "Net", ""].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.run_id} className="border-t border-[#E2DFD6]">
                <td className="py-3 px-4 font-medium">{h.period}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(h.slip.gross)}</td>
                <td className="py-3 px-4 font-data text-[#B83A3A]">− {fmtSLE(h.slip.nassit_employee)}</td>
                <td className="py-3 px-4 font-data text-[#B83A3A]">− {fmtSLE(h.slip.paye)}</td>
                <td className="py-3 px-4 font-data font-semibold">{fmtSLE(h.slip.net)}</td>
                <td className="py-3 px-4 text-right">
                  <div className="inline-flex items-center gap-1.5">
                    <button
                      data-testid={`download-payslip-${h.run_id}`}
                      onClick={() => downloadPdf(h.run_id, h.slip.employee_id, h.slip.employee_name, h.period)}
                      className="inline-flex items-center gap-1.5 text-xs bg-[#133326] hover:bg-[#0F281E] text-white px-3 py-1.5 rounded"
                    >
                      <Download className="w-3.5 h-3.5" /> PDF
                    </button>
                    {acks[h.run_id] ? (
                      <span data-testid={`ack-done-${h.run_id}`} className="inline-flex items-center gap-1 text-xs text-[#2D7A5D] font-medium px-2">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Acknowledged
                      </span>
                    ) : (
                      <button
                        data-testid={`ack-payslip-${h.run_id}`}
                        onClick={() => acknowledge(h.run_id)}
                        disabled={ackBusy === h.run_id}
                        className="inline-flex items-center gap-1.5 text-xs bg-white border border-[#2D7A5D] text-[#2D7A5D] hover:bg-[#E6F4EC] px-3 py-1.5 rounded disabled:opacity-50"
                        title="Confirm you received this payslip (ghost-worker check)"
                      >
                        <ShieldCheck className="w-3.5 h-3.5" /> Acknowledge
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!history.length && <tr><td colSpan={6} className="py-10 text-center text-sm text-[#686D76]">No completed payroll runs yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
