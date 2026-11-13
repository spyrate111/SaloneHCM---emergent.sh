import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { Briefcase, Building2, CalendarDays, Award, ChevronRight } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** Public careers listing — no login required. Routes to /apply/:token. */
export default function Careers() {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    axios.get(`${API}/careers`)
      .then((r) => setRows(r.data))
      .catch(() => setErr(true));
  }, []);

  return (
    <div className="min-h-screen bg-[#F7F6F2] py-10 px-4" data-testid="careers-page">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-8">
          <div className="flex items-center gap-2 text-[#0A4A1E] font-heading font-bold text-lg">
            <Briefcase className="w-5 h-5" /> SaloneHCM Careers
          </div>
          <Link to="/login" className="text-sm text-[#26547C] hover:underline" data-testid="careers-login-link">
            Staff sign in
          </Link>
        </div>

        <h1 className="font-heading text-3xl sm:text-4xl font-bold">Open positions</h1>
        <p className="text-[#525860] text-sm mt-2 mb-8">
          Apply directly online — no account needed. You&rsquo;ll just need your CV (PDF, DOC or DOCX).
        </p>

        {err && (
          <div className="bg-[#FBE9E9] text-[#B03A2E] text-sm rounded-lg p-4" data-testid="careers-error">
            Could not load vacancies — please try again shortly.
          </div>
        )}
        {!err && rows === null && <div className="text-sm text-[#686D76]">Loading vacancies…</div>}
        {rows !== null && rows.length === 0 && (
          <div className="bg-white border border-[#E2DFD6] rounded-xl p-10 text-center" data-testid="careers-empty">
            <Briefcase className="w-8 h-8 text-[#A1A5AB] mx-auto" />
            <div className="font-heading text-lg font-semibold mt-3">No open vacancies right now</div>
            <p className="text-sm text-[#525860] mt-1">Please check back soon — new roles are posted here as they open.</p>
          </div>
        )}

        <div className="space-y-4">
          {(rows || []).map((v) => (
            <Link key={v.public_token} to={`/apply/${v.public_token}`}
              data-testid={`careers-vacancy-${v.public_token}`}
              className="block bg-white border border-[#E2DFD6] rounded-xl p-5 sm:p-6 hover:border-[#0A4A1E] hover:shadow-sm transition group">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860] flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5" /> {v.company_name || "SaloneHCM"}
                  </div>
                  <div className="font-heading text-lg font-semibold text-[#1A1C1E] mt-1 group-hover:text-[#0A4A1E]">
                    {v.title}
                  </div>
                  <div className="flex items-center gap-4 flex-wrap text-xs text-[#525860] mt-2">
                    <span>{v.department}</span>
                    {v.grade_level && (
                      <span className="inline-flex items-center gap-1">
                        <Award className="w-3.5 h-3.5" /> Grade {v.grade_level}
                      </span>
                    )}
                    <span className="inline-flex items-center gap-1">
                      <CalendarDays className="w-3.5 h-3.5" /> Closes {v.closing_date}
                    </span>
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 text-[#A1A5AB] group-hover:text-[#0A4A1E] shrink-0" />
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
