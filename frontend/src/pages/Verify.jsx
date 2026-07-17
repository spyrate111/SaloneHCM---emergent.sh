import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../lib/api";
import { CheckCircle2, XCircle, Award, Calendar, GraduationCap, Building2, Star, ShieldCheck } from "lucide-react";

export default function Verify() {
  const { cid } = useParams();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/public/certificate/${cid}`)
      .then((r) => setResult(r.data))
      .catch(() => setResult({ valid: false, reason: "lookup_failed" }))
      .finally(() => setLoading(false));
  }, [cid]);

  return (
    <div className="min-h-screen bg-[#F7F6F2] py-12 px-4" data-testid="verify-page">
      <div className="max-w-2xl mx-auto">
        <Link to="/" className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-[#525860] mb-6 hover:text-[#0A4A1E]">
          <ShieldCheck className="w-4 h-4" /> SaloneHCM Certificate Verification
        </Link>

        {loading && <div className="bg-white border border-[#E2DFD6] rounded-xl p-10 text-center text-[#686D76]">Looking up certificate…</div>}

        {!loading && result && !result.valid && (
          <div className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden" data-testid="verify-invalid">
            <div className="bg-[#E9F2FB] px-8 py-10 text-center border-b border-[#D0E2F2]">
              <XCircle className="w-14 h-14 text-[#3A7CB8] mx-auto" strokeWidth={1.5} />
              <h1 className="font-heading text-3xl font-bold mt-4 text-[#1A1C1E]">Certificate not found</h1>
              <p className="text-[#525860] mt-2 text-sm">No SaloneHCM certificate matches this identifier.</p>
            </div>
            <div className="px-8 py-6 text-xs text-[#686D76] font-data break-all">
              Certificate ID: {cid}
            </div>
          </div>
        )}

        {!loading && result && result.valid && (
          <div className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden" data-testid="verify-valid">
            <div className="bg-gradient-to-br from-[#E4F7E7] to-[#F7F6F2] px-8 py-10 text-center border-b border-[#E2DFD6]">
              <CheckCircle2 className="w-14 h-14 text-[#17A035] mx-auto" strokeWidth={1.5} />
              <div className="text-[10px] uppercase tracking-[0.22em] text-[#525860] mt-4">Verified certificate</div>
              <h1 className="font-heading text-3xl font-bold mt-2 text-[#1A1C1E]" data-testid="verify-employee-name">{result.employee_name}</h1>
              <p className="text-[#525860] mt-2 text-sm">successfully completed</p>
              <h2 className="font-heading text-xl font-semibold mt-1.5 text-[#26547C]" data-testid="verify-program-title">{result.program_title}</h2>
            </div>

            <div className="px-8 py-6 grid grid-cols-1 sm:grid-cols-2 gap-5 text-sm">
              <Row icon={GraduationCap} label="Skill area" value={result.skill_area} />
              <Row icon={Award} label="Training hours" value={`${result.hours}h`} />
              <Row icon={Calendar} label="Completed on" value={result.completed_on} />
              {result.score !== null && result.score !== undefined && (
                <Row icon={Star} label="Final score" value={`${result.score}%`} accent="#17A035" />
              )}
              <Row icon={Building2} label="Issued by" value={result.issued_by} fullWidth />
            </div>

            <div className="px-8 py-4 bg-[#F7F6F2] border-t border-[#E2DFD6] flex items-center justify-between text-[11px] text-[#686D76] font-data">
              <span>Certificate ID</span>
              <span className="text-[#1A1C1E] break-all text-right" data-testid="verify-cert-id">{result.certificate_id}</span>
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

function Row({ icon: Icon, label, value, accent, fullWidth }) {
  return (
    <div className={`flex items-start gap-3 ${fullWidth ? "sm:col-span-2" : ""}`}>
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
