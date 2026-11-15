import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Users, Wallet, CalendarClock, ArrowUpRight, UserCircle, ChevronLeft } from "lucide-react";

export default function Team() {
  const { eid } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const isAdminView = !!eid;
  const [data, setData] = useState(null);
  const [allManagers, setAllManagers] = useState([]);

  useEffect(() => {
    const url = eid ? `/team/${eid}` : "/team/me";
    api.get(url).then((r) => setData(r.data));
    if (user?.role === "admin") api.get("/team/managers").then((r) => setAllManagers(r.data));
  }, [eid, user]);

  if (!data) return <div className="text-sm text-[#525860]">Loading…</div>;

  return (
    <div className="space-y-6" data-testid="team-page">
      <div>
        {isAdminView && (
          <Link to="/team" className="inline-flex items-center gap-1.5 text-sm text-[#525860] hover:text-[#1A1C1E] mb-2">
            <ChevronLeft className="w-4 h-4" /> Back to my team
          </Link>
        )}
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Manager Self-Service</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">
          {isAdminView ? (data.manager ? `${data.manager.name}'s team` : "Team") : "My team"}
        </h1>
        {isAdminView && data.manager && (
          <p className="text-[#525860] text-sm mt-1">{data.manager.job_title} · {data.manager.department}</p>
        )}
      </div>

      {/* Admin team picker */}
      {user?.role === "admin" && allManagers.length > 0 && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-4">
          <div className="text-[10px] uppercase tracking-wider text-[#525860] mb-2">Switch to another manager&rsquo;s team</div>
          <div className="flex flex-wrap gap-2">
            {allManagers.map((m) => (
              <button
                key={m.id}
                data-testid={`team-pick-${m.id}`}
                onClick={() => nav(`/team/${m.id}`)}
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border transition ${
                  eid === m.id ? "bg-[#0A4A1E] text-white border-[#0A4A1E]" : "border-[#E2DFD6] hover:border-[#0A4A1E] text-[#1A1C1E]"
                }`}
              >
                <UserCircle className="w-3.5 h-3.5" strokeWidth={1.5} /> {m.first_name} {m.last_name}
                <span className="text-[#A1A5AB]">·</span> {m.department}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <KPI label="Team size" value={data.team_size} sub={`${data.payroll.headcount_active} active`} icon={Users} accent="bg-[#0A4A1E]" />
        <KPI label="Monthly payroll" value={fmtSLE(data.payroll.gross)} sub={`Net: ${fmtSLE(data.payroll.net)}`} icon={Wallet} accent="bg-[#26547C]" />
        <KPI label="Pending leave" value={data.pending_leaves} sub="Awaiting approval" icon={CalendarClock} accent="bg-[#D1603D]" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-[#E2DFD6]">
            <h3 className="font-heading text-lg font-semibold">Direct reports</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[#F7F6F2]">
              <tr>{["Name", "Title", "Status", ""].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {data.reports.map((r) => (
                <tr key={r.id} className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB]">
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-full bg-[#EBE8E0] grid place-items-center text-xs font-medium">
                        {r.first_name?.[0]}{r.last_name?.[0]}
                      </div>
                      <div>
                        <div className="font-medium">{r.first_name} {r.last_name}</div>
                        <div className="text-xs text-[#686D76]">{r.department}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-[#525860]">{r.job_title}</td>
                  <td className="py-3 px-4">
                    <span className={`text-[11px] uppercase tracking-wider px-2 py-0.5 rounded-full ${
                      r.status === "active" ? "bg-[#E4F7E7] text-[#17A035]" : r.status === "on_leave" ? "bg-[#FBF1DE] text-[#8B6A14]" : "bg-[#E9F2FB] text-[#3A7CB8]"
                    }`}>{r.status.replace("_", " ")}</span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    {user?.role === "admin" && (
                      <Link to={`/employees/${r.id}`} className="text-xs text-[#26547C] hover:underline inline-flex items-center gap-1">View <ArrowUpRight className="w-3 h-3" /></Link>
                    )}
                  </td>
                </tr>
              ))}
              {!data.reports.length && <tr><td colSpan={4} className="py-10 text-center text-sm text-[#686D76]">No direct reports.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-[#E2DFD6]">
            <h3 className="font-heading text-lg font-semibold">Recent leave</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[#F7F6F2]">
              <tr>{["Employee", "Type", "Period", "Status"].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {data.recent_leaves.map((l) => (
                <tr key={l.id} className="border-t border-[#E2DFD6]">
                  <td className="py-3 px-4">{l.employee_name}</td>
                  <td className="py-3 px-4 capitalize text-[#525860]">{l.leave_type}</td>
                  <td className="py-3 px-4 font-data text-[#686D76] text-xs">{l.start_date} → {l.end_date}</td>
                  <td className="py-3 px-4 text-[10px] uppercase tracking-wider text-[#686D76]">{l.status}</td>
                </tr>
              ))}
              {!data.recent_leaves.length && <tr><td colSpan={4} className="py-10 text-center text-sm text-[#686D76]">No recent leave.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function KPI({ label, value, sub, icon: Icon, accent }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{label}</div>
          <div className="font-heading text-2xl font-bold mt-2 font-data">{value}</div>
          {sub && <div className="text-xs text-[#686D76] mt-1">{sub}</div>}
        </div>
        <div className={`w-9 h-9 rounded-md grid place-items-center ${accent}`}>
          <Icon className="w-[18px] h-[18px] text-white" strokeWidth={1.5} />
        </div>
      </div>
    </div>
  );
}
