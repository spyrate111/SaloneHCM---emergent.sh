import { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Clock, Plus } from "lucide-react";
import { DatePicker } from "../components/ui/date-picker";

export default function Attendance() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [emps, setEmps] = useState([]);
  const [form, setForm] = useState({ employee_id: "", date: new Date().toISOString().split("T")[0], hours: 8, overtime_hours: 0, notes: "" });

  const load = () => api.get("/attendance").then((r) => setList(r.data));
  useEffect(() => {
    load();
    if (user?.role === "admin") api.get("/employees").then((r) => setEmps(r.data));
  }, [user]);

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
