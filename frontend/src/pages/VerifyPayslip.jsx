/**
 * Public payslip verification — banks scan the QR on a payslip PDF and land
 * here. No login required; shows only what's printed on the slip.
 */
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { fmtSLE } from "../lib/api";
import { CheckCircle2, XCircle, Building2, Calendar, Banknote, ShieldCheck, User } from "lucide-react";

export default function VerifyPayslip() {
  const { vid } = useParams();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/public/payslip/${vid}`)
      .then((r) => setResult(r.data))
      .catch(() => setResult({ valid: false, reason: "lookup_failed" }))
      .finally(() => setLoading(false));
  }, [vid]);

  return (
    <div className="min-h-screen bg-[#F7F6F2] py-12 px-4" data-testid="verify-payslip-page">
      <div className="max-w-2xl mx-auto">
        <Link to="/" className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-[#525860] mb-6 hover:text-[#0A4A1E]">
          <ShieldCheck className="w-4 h-4" /> SaloneHCM Payslip Verification
        </Link>

        {loading && <div className="bg-white border border-[#E2DFD6] rounded-xl p-10 text-center text-[#686D76]">Looking up payslip…</div>}

        {!loading && result && !result.valid && (
          <div className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden" data-testid="verify-payslip-invalid">
            <div className="bg-[#FBE9E9] px-8 py-10 text-center border-b border-[#F2CFCC]">
              <XCircle className="w-14 h-14 text-[#B03A2E] mx-auto" strokeWidth={1.5} />
              <h1 className="font-heading text-3xl font-bold mt-4 text-[#1A1C1E]">Payslip not found</h1>
              <p className="text-[#525860] mt-2 text-sm">
                No SaloneHCM payslip matches this verification ID. Treat the document with caution.
              </p>
            </div>
            <div className="px-8 py-6 text-xs text-[#686D76] font-data break-all">
              Verification ID: {vid}
            </div>
          </div>
        )}

        {!loading && result && result.valid && (
          <div className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden" data-testid="verify-payslip-valid">
            <div className="bg-gradient-to-br from-[#E4F7E7] to-[#F7F6F2] px-8 py-10 text-center border-b border-[#E2DFD6]">
              <CheckCircle2 className="w-14 h-14 text-[#17A035] mx-auto" strokeWidth={1.5} />
              <div className="text-[10px] uppercase tracking-[0.22em] text-[#525860] mt-4">Genuine payslip</div>
              <h1 className="font-heading text-3xl font-bold mt-2 text-[#1A1C1E]" data-testid="verify-payslip-name">{result.employee_name}</h1>
              <p className="text-[#525860] mt-2 text-sm">This payslip was issued through SaloneHCM payroll.</p>
            </div>

            <div className="px-8 py-6 grid grid-cols-1 sm:grid-cols-2 gap-5 text-sm">
              <Row icon={Calendar} label="Pay period" value={result.period} testid="verify-payslip-period" />
              <Row icon={Banknote} label="Net pay" value={fmtSLE(result.net)} accent="#17A035" testid="verify-payslip-net" />
              <Row icon={User} label="Gross pay" value={fmtSLE(result.gross)} />
              <Row icon={Building2} label="Issued by" value={result.issued_by} />
            </div>

            <div className="px-8 py-4 bg-[#F7F6F2] border-t border-[#E2DFD6] flex items-center justify-between text-[11px] text-[#686D76] font-data">
              <span>Verification ID</span>
              <span className="text-[#1A1C1E] break-all text-right" data-testid="verify-payslip-vid">{result.verification_id}</span>
            </div>
          </div>
        )}

        <div className="mt-6 text-center text-[11px] text-[#A1A5AB] uppercase tracking-[0.18em]">
          Powered by SaloneHCM · Sierra Leone Human Capital Management
        </div>
      </div>
    </div>
  );
}

function Row({ icon: Icon, label, value, accent, testid }) {
  return (
    <div className="flex items-start gap-3" data-testid={testid}>
      <div className="w-9 h-9 rounded-md bg-[#F7F6F2] grid place-items-center flex-shrink-0">
        <Icon className="w-4 h-4 text-[#26547C]" strokeWidth={1.5} />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.14em] text-[#525860]">{label}</div>
        <div className="font-medium mt-0.5" style={accent ? { color: accent } : {}}>{value}</div>
      </div>
    </div>
  );
}
