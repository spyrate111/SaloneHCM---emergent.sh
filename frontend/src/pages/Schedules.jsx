import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { CalendarClock, Plus, Play, Trash2, X, Pause, PlayCircle, Repeat } from "lucide-react";

const CADENCE_LABEL = {
  monthly: "Monthly",
  biweekly: "Every 2 weeks",
  weekly: "Weekly",
};

export default function Schedules() {
  const [schedules, setSchedules] = useState([]);
  const [open, setOpen] = useState(false);

  const load = useCallback(() => api.get("/payroll/schedules").then((r) => setSchedules(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const onCreate = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.currentTarget);
    const body = {
      title: fd.get("title"),
      cadence: fd.get("cadence"),
      day_of_month: parseInt(fd.get("day_of_month")) || 28,
      description: fd.get("description") || "",
      active: true,
    };
    try {
      await api.post("/payroll/schedules", body);
      toast.success("Schedule created");
      setOpen(false);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Create failed");
    }
  };

  const toggle = async (s) => {
    try {
      await api.patch(`/payroll/schedules/${s.id}`, { active: !s.active });
      toast.success(s.active ? "Schedule paused" : "Schedule activated");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Update failed"); }
  };

  const remove = async (s) => {
    if (!window.confirm(`Delete "${s.title}"?`)) return;
    try {
      await api.delete(`/payroll/schedules/${s.id}`);
      toast.success("Schedule deleted");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Delete failed"); }
  };

  const runNow = async (s) => {
    if (!window.confirm(`Run payroll now for "${s.title}"? This will create a real payroll run.`)) return;
    try {
      const { data } = await api.post(`/payroll/schedules/${s.id}/run-now`);
      toast.success(`Payroll fired for ${data.run.period} — net SLE ${data.run.totals.net.toLocaleString()}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Run failed"); }
  };

  return (
    <div className="space-y-6" data-testid="schedules-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Payroll automation</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1 flex items-center gap-2">
            Recurring schedules <Repeat className="w-6 h-6 text-[#D1603D]" />
          </h1>
          <p className="text-[#525860] text-sm mt-1.5 max-w-2xl">
            Auto-run payroll on a cadence. Each schedule fires at <span className="font-data">06:00 UTC</span> on its due date and creates a normal payroll run — the same one you'd get from the manual wizard.
          </p>
        </div>
        <button
          data-testid="schedule-create-open"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white text-sm px-4 py-2.5 rounded-md transition"
        >
          <Plus className="w-4 h-4" strokeWidth={1.5} /> New schedule
        </button>
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Schedule", "Cadence", "Next run", "Last run", "Runs", "Status", ""].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {schedules.map((s) => (
              <tr key={s.id} className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB]" data-testid={`schedule-row-${s.id}`}>
                <td className="py-3 px-4">
                  <div className="font-medium flex items-center gap-2"><CalendarClock className="w-4 h-4 text-[#26547C]" />{s.title}</div>
                  {s.description && <div className="text-xs text-[#686D76] mt-0.5">{s.description}</div>}
                </td>
                <td className="py-3 px-4 text-xs text-[#525860]">
                  {CADENCE_LABEL[s.cadence] || s.cadence}
                  {s.cadence === "monthly" && <span className="text-[#686D76]"> · day {s.day_of_month}</span>}
                </td>
                <td className="py-3 px-4 font-data text-xs">{s.next_run_at ? new Date(s.next_run_at).toLocaleString() : "—"}</td>
                <td className="py-3 px-4 font-data text-xs text-[#686D76]">
                  {s.last_run_at ? new Date(s.last_run_at).toLocaleDateString() : "—"}
                  {s.last_run_status && s.last_run_status !== "success" && s.last_run_status !== "manual" && (
                    <div className="text-[10px] text-[#B83A3A] mt-0.5">{s.last_run_status}</div>
                  )}
                </td>
                <td className="py-3 px-4 font-data text-[#525860]">{s.runs_completed || 0}</td>
                <td className="py-3 px-4">
                  {s.active
                    ? <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-[#E6F4EC] text-[#2D7A5D]"><PlayCircle className="w-3 h-3" /> Active</span>
                    : <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-[#EBE8E0] text-[#525860]"><Pause className="w-3 h-3" /> Paused</span>}
                </td>
                <td className="py-3 px-4 text-right">
                  <div className="inline-flex gap-1">
                    <button data-testid={`run-now-${s.id}`} onClick={() => runNow(s)} title="Run now" className="p-1.5 rounded text-[#D1603D] hover:bg-[#FBE9DF]"><Play className="w-3.5 h-3.5" /></button>
                    <button data-testid={`toggle-${s.id}`} onClick={() => toggle(s)} title={s.active ? "Pause" : "Activate"} className="p-1.5 rounded text-[#26547C] hover:bg-[#E5EEF6]">
                      {s.active ? <Pause className="w-3.5 h-3.5" /> : <PlayCircle className="w-3.5 h-3.5" />}
                    </button>
                    <button data-testid={`delete-${s.id}`} onClick={() => remove(s)} title="Delete" className="p-1.5 rounded text-[#B83A3A] hover:bg-[#FBEAEA]"><Trash2 className="w-3.5 h-3.5" /></button>
                  </div>
                </td>
              </tr>
            ))}
            {!schedules.length && (
              <tr><td colSpan={7} className="py-10 text-center text-sm text-[#686D76]">
                <CalendarClock className="w-8 h-8 mx-auto mb-2 text-[#A1A5AB]" strokeWidth={1.3} />
                No schedules yet — create one to auto-run payroll on a cadence.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setOpen(false)} data-testid="schedule-create-modal">
          <form onClick={(e) => e.stopPropagation()} onSubmit={onCreate} className="bg-white rounded-lg w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-heading text-xl font-semibold">New payroll schedule</h2>
              <button type="button" onClick={() => setOpen(false)} className="text-[#525860]"><X className="w-4 h-4" /></button>
            </div>
            <Field label="Title">
              <input data-testid="new-schedule-title" required name="title" placeholder="Monthly end-of-month payroll" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
            </Field>
            <Field label="Cadence">
              <select data-testid="new-schedule-cadence" required name="cadence" defaultValue="monthly" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                <option value="monthly">Monthly</option>
                <option value="biweekly">Every 2 weeks</option>
                <option value="weekly">Weekly</option>
              </select>
            </Field>
            <Field label="Day of month (used for Monthly only)">
              <input data-testid="new-schedule-day" name="day_of_month" type="number" min={1} max={31} defaultValue={28} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
              <div className="text-[11px] text-[#686D76] mt-1">If the chosen day doesn't exist (e.g. Feb 30), it falls back to the last day of the month.</div>
            </Field>
            <Field label="Description (optional)">
              <input name="description" placeholder="Notes for your team" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setOpen(false)} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Cancel</button>
              <button type="submit" data-testid="new-schedule-submit" className="text-sm bg-[#133326] text-white px-4 py-2 rounded-md inline-flex items-center gap-2">
                <Plus className="w-4 h-4" /> Create
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">{label}</label>
      {children}
    </div>
  );
}
