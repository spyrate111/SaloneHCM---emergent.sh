import { useEffect, useState, useCallback, useMemo } from "react";
import api, { downloadBlob } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Clock, Plus, MapPin, Download } from "lucide-react";
import { DatePicker } from "../components/ui/date-picker";
import PunchMap from "../components/PunchMap";

export default function Attendance() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [emps, setEmps] = useState([]);
  const [form, setForm] = useState({ employee_id: "", date: new Date().toISOString().split("T")[0], hours: 8, overtime_hours: 0, notes: "" });
  const [team, setTeam] = useState(null); // null = no map access (employees)
  const [mapDate, setMapDate] = useState(new Date().toISOString().split("T")[0]);
  const [mapEmp, setMapEmp] = useState("");

  const load = useCallback(() => api.get("/attendance").then((r) => setList(r.data)), []);
  useEffect(() => {
    load();
    if (user?.role === "admin") api.get("/employees").then((r) => setEmps(r.data));
  }, [user, load]);

  useEffect(() => {
    api.get("/mobile/punch/team", { params: { date: mapDate } })
      .then((r) => setTeam(r.data))
      .catch(() => setTeam(null));
  }, [mapDate]);

  const mapPunches = useMemo(
    () => (team?.punches || []).filter((p) => !mapEmp || p.employee_id === mapEmp),
    [team, mapEmp],
  );
  const empOptions = useMemo(() => {
    const seen = new Map();
    (team?.punches || []).forEach((p) => { if (p.employee_id) seen.set(p.employee_id, p.employee_name); });
    return [...seen.entries()];
  }, [team]);
  const mapStats = useMemo(() => ({
    in_zone: mapPunches.filter((p) => p.in_zone === true).length,
    out_zone: mapPunches.filter((p) => p.in_zone === false).length,
    no_gps: mapPunches.filter((p) => p.in_zone === null || p.in_zone === undefined).length,
  }), [mapPunches]);

  const submit = async (e) => {
    e.preventDefault();
    await api.post("/attendance", { ...form, hours: Number(form.hours), overtime_hours: Number(form.overtime_hours) });
    setForm({ ...form, notes: "" }); load();
  };

  return (
    <div className="space-y-6" data-testid="attendance-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Time & Attendance</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Clock & timesheets</h1>
      </div>

      {/* GPS punch map — supervisors & admins */}
      {team && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="attendance-map-section">
          <div className="px-6 py-4 border-b border-[#E2DFD6] flex flex-wrap items-center gap-3">
            <h3 className="font-heading text-lg font-semibold flex items-center gap-2">
              <MapPin className="w-4 h-4 text-[#0A4A1E]" /> GPS punch map
            </h3>
            <div className="flex items-center gap-2 text-[11px]" data-testid="attendance-map-stats">
              <span className="px-2 py-1 rounded-full bg-[#E4F7E7] text-[#0A4A1E] font-semibold">{mapStats.in_zone} in-zone</span>
              <span className={`px-2 py-1 rounded-full font-semibold ${mapStats.out_zone > 0 ? "bg-[#FBE9E9] text-[#B03A2E]" : "bg-[#F7F6F2] text-[#525860]"}`}>{mapStats.out_zone} out-of-zone</span>
              <span className="px-2 py-1 rounded-full bg-[#F7F6F2] text-[#525860] font-semibold">{mapStats.no_gps} no GPS</span>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <div className="w-40" data-testid="attendance-map-date">
                <DatePicker value={mapDate} onChange={setMapDate} />
              </div>
              <select value={mapEmp} onChange={(e) => setMapEmp(e.target.value)}
                className="bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm max-w-[200px]"
                data-testid="attendance-map-emp-filter">
                <option value="">All employees</option>
                {empOptions.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
              </select>
              <button
                onClick={() => downloadBlob(`/mobile/punch/team.csv?date=${mapDate}${mapEmp ? `&employee_id=${mapEmp}` : ""}`, `punch-map-${mapDate}.csv`)}
                className="inline-flex items-center gap-1.5 text-sm border border-[#E2DFD6] px-3 py-2 rounded-md hover:bg-[#F7F6F2]"
                data-testid="attendance-map-export">
                <Download className="w-4 h-4" /> CSV
              </button>
            </div>
          </div>
          <div className="p-4">
            <PunchMap punches={mapPunches} branches={team.branches} height={360} />
            {mapPunches.length > 0 && (
              <table className="w-full text-sm mt-4" data-testid="attendance-map-table">
                <thead className="bg-[#F7F6F2]">
                  <tr>{["Employee", "Kind", "Time", "Branch", "Distance", "Zone"].map((h) => (
                    <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-4 font-medium">{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {mapPunches.map((p) => (
                    <tr key={p.id} className="border-t border-[#E2DFD6]">
                      <td className="py-2.5 px-4">{p.employee_name}</td>
                      <td className="py-2.5 px-4 uppercase font-data text-xs">{p.kind}</td>
                      <td className="py-2.5 px-4 font-data text-xs">{new Date(p.clocked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                      <td className="py-2.5 px-4 text-[#525860]">{p.branch_name || "—"}</td>
                      <td className="py-2.5 px-4 font-data text-xs">{p.distance_from_branch_m != null ? `${Math.round(p.distance_from_branch_m)}m` : "—"}</td>
                      <td className="py-2.5 px-4">
                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                          p.in_zone === true ? "bg-[#E4F7E7] text-[#0A4A1E]"
                          : p.in_zone === false ? "bg-[#FBE9E9] text-[#B03A2E]"
                          : "bg-[#F7F6F2] text-[#8A8F96]"}`}>
                          {p.in_zone === true ? "In zone" : p.in_zone === false ? "Out of zone" : "No GPS"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {mapPunches.length === 0 && (
              <p className="text-center text-sm text-[#686D76] py-6" data-testid="attendance-map-empty">No GPS punches on {mapDate}.</p>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <form onSubmit={submit} className="bg-white border border-[#E2DFD6] rounded-lg p-6 space-y-4 lg:col-span-1" data-testid="attendance-form">
          <h3 className="font-heading text-lg font-semibold flex items-center gap-2"><Clock className="w-4 h-4" /> Log time</h3>
          {user?.role === "admin" && (
            <div>
              <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Employee</label>
              <select required value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                <option value="">Select…</option>
                {emps.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
              </select>
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Date</label>
            <DatePicker data-testid="attendance-date" value={form.date} onChange={(v) => setForm({ ...form, date: v })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Hours</label>
              <input type="number" step="0.25" value={form.hours} onChange={(e) => setForm({ ...form, hours: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Overtime</label>
              <input type="number" step="0.25" value={form.overtime_hours} onChange={(e) => setForm({ ...form, overtime_hours: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Notes</label>
            <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
          </div>
          <button data-testid="attendance-submit" type="submit" className="w-full inline-flex items-center justify-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2.5 rounded-md text-sm font-medium">
            <Plus className="w-4 h-4" /> Submit entry
          </button>
        </form>

        <div className="lg:col-span-2 bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-[#E2DFD6]"><h3 className="font-heading text-lg font-semibold">Recent entries</h3></div>
          <table className="w-full text-sm">
            <thead className="bg-[#F7F6F2]">
              <tr>{["Date", "Hours", "Overtime", "Notes"].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {list.map((t) => (
                <tr key={t.id} className="border-t border-[#E2DFD6]">
                  <td className="py-3 px-4 font-data">{t.date}</td>
                  <td className="py-3 px-4 font-data">{t.hours}</td>
                  <td className="py-3 px-4 font-data text-[#D1603D]">{t.overtime_hours}</td>
                  <td className="py-3 px-4 text-[#686D76]">{t.notes || "—"}</td>
                </tr>
              ))}
              {!list.length && <tr><td colSpan={4} className="py-10 text-center text-sm text-[#686D76]">No timesheets yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
