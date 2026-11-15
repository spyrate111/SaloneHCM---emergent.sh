import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useFeatures } from "../lib/features";
import { toast } from "sonner";
import { TrendingUp, Check, X, Clock, Lock, AlertCircle } from "lucide-react";

export default function Promotion() {
  const { user } = useAuth();
  const { has } = useFeatures();
  const [eligible, setEligible] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [tab, setTab] = useState("eligible");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!has("civil_service")) return;
    const [e, r] = await Promise.all([
      api.get("/promotion/eligible"),
      api.get("/promotion/recommendations"),
    ]);
    setEligible(e.data);
    setRecommendations(r.data);
  }, [has]);

  useEffect(() => { refresh(); }, [refresh]);

  if (!has("civil_service")) {
    return (
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center">
        <Lock className="w-10 h-10 text-[#A1A5AB] mx-auto mb-3" strokeWidth={1.4} />
        <h3 className="font-heading text-xl">Promotion Eligibility Tracker</h3>
        <p className="text-sm text-[#525860] mt-2 max-w-md mx-auto">Available on the Government tier — paired with the Civil Service step structure.</p>
      </div>
    );
  }

  const recommend = async (employeeId, name) => {
    setBusy(true);
    try {
      await api.post("/promotion/recommendations", { employee_id: employeeId, notes: `Recommended via tracker` });
      toast.success(`Recommended ${name} for promotion`);
      refresh();
      setTab("recommendations");
    } catch (e) { toast.error(e?.response?.data?.detail || "Recommend failed"); }
    finally { setBusy(false); }
  };

  const decide = async (rid, action) => {
    const note = action === "approve"
      ? "Approved by MoF reviewer"
      : window.prompt("Reason for rejection?") || "Rejected";
    if (action === "reject" && !note) return;
    setBusy(true);
    try {
      await api.post(`/promotion/recommendations/${rid}/${action}`, { note });
      toast.success(action === "approve" ? "Promotion applied" : "Rejected");
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || `${action} failed`); }
    finally { setBusy(false); }
  };

  const isApprover = user?.mof_approver || user?.role === "superadmin";

  return (
    <div className="space-y-6" data-testid="promotion-page">
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Civil Service · Workforce</div>
        <h1 className="font-heading text-3xl font-bold mt-1">Promotion Eligibility</h1>
        <p className="text-sm text-[#525860] mt-1 max-w-2xl">
          Surfaces civil servants ready for step promotion based on tenure, last performance review, and availability of a next step in their grade.
        </p>
        {eligible && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
            <KPI label="Eligible" value={eligible.eligible_count} color="text-[#17A035]" />
            <KPI label="Total reviewed" value={eligible.rows.length} />
            <KPI label="Min tenure" value={`${eligible.thresholds.min_tenure_days}d`} small />
            <KPI label="Min rating" value={eligible.thresholds.min_rating} small />
          </div>
        )}
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-6 py-3 border-b border-[#E2DFD6] flex gap-2">
          <Tab active={tab === "eligible"} onClick={() => setTab("eligible")} testid="tab-eligible">
            Candidates · {eligible?.rows.length || 0}
          </Tab>
          <Tab active={tab === "recommendations"} onClick={() => setTab("recommendations")} testid="tab-recs">
            Recommendations · {recommendations.length}
          </Tab>
        </div>

        {tab === "eligible" && eligible && (
          <table className="w-full text-sm" data-testid="eligible-table">
            <thead className="bg-[#F7F6F2]">
              <tr>{["Name", "Grade · Step", "Tenure", "Last rating", "Status", ""].map((h) => (
                <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-4 font-medium">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {eligible.rows.map((r) => (
                <tr key={r.employee_id} className="border-t border-[#E2DFD6]">
                  <td className="py-2 px-4">
                    <div className="font-medium">{r.name}</div>
                    <div className="text-[10px] text-[#686D76]">{r.department}</div>
                  </td>
                  <td className="py-2 px-4 font-data">
                    {r.grade_code} · {r.current_step}
                    {r.next_step && <span className="text-[#17A035]"> → {r.next_step}</span>}
                  </td>
                  <td className="py-2 px-4 font-data text-xs">{r.tenure_days}d</td>
                  <td className="py-2 px-4 font-data text-xs">{r.last_rating || "—"}/5</td>
                  <td className="py-2 px-4">
                    {r.eligible ? (
                      <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#E4F7E7] text-[#17A035]">
                        <Check className="w-3 h-3" /> Eligible
                      </span>
                    ) : (
                      <span title={r.reasons.join("; ")} className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#E9F2FB] text-[#3A7CB8] cursor-help">
                        <AlertCircle className="w-3 h-3" /> Blocked
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-4 text-right">
                    {r.eligible && (
                      <button data-testid={`recommend-${r.employee_id}`} disabled={busy}
                              onClick={() => recommend(r.employee_id, r.name)}
                              className="text-xs bg-[#26547C] hover:bg-[#1F4569] text-white px-3 py-1.5 rounded inline-flex items-center gap-1 disabled:opacity-60">
                        <TrendingUp className="w-3 h-3" /> Recommend
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === "recommendations" && (
          <table className="w-full text-sm" data-testid="recommendations-table">
            <thead className="bg-[#F7F6F2]">
              <tr>{["Employee", "From → To", "Status", "Recommended by", "Decided", ""].map((h) => (
                <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-4 font-medium">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {recommendations.length === 0 && (
                <tr><td colSpan={6} className="py-8 text-center text-sm text-[#525860]">No recommendations yet.</td></tr>
              )}
              {recommendations.map((rec) => (
                <tr key={rec.id} className="border-t border-[#E2DFD6]" data-testid={`rec-row-${rec.id}`}>
                  <td className="py-2 px-4">{rec.employee_name}</td>
                  <td className="py-2 px-4 font-data">{rec.grade_code} · {rec.from_step} → {rec.to_step}</td>
                  <td className="py-2 px-4"><StatusPill status={rec.status} /></td>
                  <td className="py-2 px-4 text-xs">{rec.recommended_by}</td>
                  <td className="py-2 px-4 text-xs text-[#525860]">
                    {rec.approved_at ? new Date(rec.approved_at).toLocaleDateString() :
                     rec.rejected_at ? new Date(rec.rejected_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="py-2 px-4 text-right">
                    {rec.status === "pending" && isApprover && (
                      <>
                        <button data-testid={`approve-${rec.id}`} onClick={() => decide(rec.id, "approve")} disabled={busy}
                                className="text-xs bg-[#17A035] hover:bg-[#137D30] text-white px-2.5 py-1 rounded mr-1 disabled:opacity-60">
                          <Check className="w-3 h-3 inline" /> Approve
                        </button>
                        <button data-testid={`reject-${rec.id}`} onClick={() => decide(rec.id, "reject")} disabled={busy}
                                className="text-xs bg-[#3A7CB8] hover:bg-[#34689A] text-white px-2.5 py-1 rounded disabled:opacity-60">
                          <X className="w-3 h-3 inline" /> Reject
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Tab({ active, onClick, children, testid }) {
  return (
    <button data-testid={testid} onClick={onClick} className={`text-sm px-3 py-1.5 rounded ${active ? "bg-[#0A4A1E] text-white" : "text-[#525860] hover:bg-[#F7F6F2]"}`}>
      {children}
    </button>
  );
}

function KPI({ label, value, color = "text-[#1A1C1E]", small }) {
  return (
    <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-3">
      <div className="text-[10px] uppercase tracking-wider text-[#525860]">{label}</div>
      <div className={`font-heading ${small ? "text-lg" : "text-2xl"} font-bold mt-1 font-data ${color}`}>{value}</div>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    pending: { bg: "bg-[#FBF1DE]", fg: "text-[#8B6A14]", icon: Clock, label: "Pending" },
    approved: { bg: "bg-[#E4F7E7]", fg: "text-[#17A035]", icon: Check, label: "Approved" },
    rejected: { bg: "bg-[#E9F2FB]", fg: "text-[#3A7CB8]", icon: X, label: "Rejected" },
  };
  const p = map[status] || map.pending;
  const Icon = p.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${p.bg} ${p.fg}`}>
      <Icon className="w-3 h-3" /> {p.label}
    </span>
  );
}
