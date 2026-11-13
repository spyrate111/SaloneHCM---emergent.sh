import { useCallback, useEffect, useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { AlertTriangle, CalendarDays, Clock3, Plus, X } from "lucide-react";

const CATEGORIES = [
  ["conduct", "Conduct"],
  ["attendance", "Attendance"],
  ["performance", "Performance"],
  ["policy", "Policy"],
  ["other", "Other"],
];
const EVENT_TYPES = [
  ["warning", "Warning"],
  ["hearing", "Hearing"],
  ["outcome", "Outcome"],
  ["note", "Case note"],
];
const STATUSES = [
  ["open", "Open"],
  ["under_review", "Under review"],
  ["hearing_scheduled", "Hearing scheduled"],
  ["closed", "Closed"],
];
const EVENT_LABELS = {
  case_opened: "Case opened",
  warning: "Warning",
  hearing: "Hearing",
  outcome: "Outcome",
  note: "Case note",
  status_changed: "Status updated",
};
const STATUS_STYLES = {
  open: "bg-[#FBF1DE] text-[#8B6A14]",
  under_review: "bg-[#E9F2FB] text-[#26547C]",
  hearing_scheduled: "bg-[#FBE9DF] text-[#B84F2F]",
  closed: "bg-[#E4F7E7] text-[#0A4A1E]",
};
const today = () => new Date().toISOString().slice(0, 10);
const emptyCase = () => ({
  category: "conduct",
  title: "",
  incident_date: today(),
  summary: "",
});
const emptyEvent = () => ({
  event_type: "note",
  occurred_on: today(),
  details: "",
});
const statusText = (status) => Object.fromEntries(STATUSES)[status] || status;

export default function DisciplinaryPanel({ employee }) {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [caseForm, setCaseForm] = useState(emptyCase);
  const [eventFor, setEventFor] = useState(null);
  const [eventForm, setEventForm] = useState(emptyEvent);
  const [eventBusy, setEventBusy] = useState(false);
  const [statusBusy, setStatusBusy] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const r = await api.get("/disciplinary/employees/" + encodeURIComponent(employee.id) + "/cases");
      setCases(Array.isArray(r.data) ? r.data : []);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [employee.id]);

  useEffect(() => { load(); }, [load]);

  const openCase = async (ev) => {
    ev.preventDefault();
    setCreateBusy(true);
    try {
      await api.post(
        "/disciplinary/employees/" + encodeURIComponent(employee.id) + "/cases",
        caseForm,
      );
      setCaseForm(emptyCase());
      setCreateOpen(false);
      toast.success("HR case opened");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not open case");
    } finally {
      setCreateBusy(false);
    }
  };

  const changeStatus = async (row, nextStatus) => {
    if (!nextStatus || nextStatus === row.status) return;
    const note = window.prompt("Record the reason for this status change:");
    if (!note || note.trim().length < 3) {
      toast.error("Enter a short reason to update case status");
      return;
    }
    setStatusBusy(row.id);
    try {
      await api.patch("/disciplinary/cases/" + encodeURIComponent(row.id) + "/status", {
        status: nextStatus,
        note: note.trim(),
      });
      toast.success("Case status updated");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update case status");
    } finally {
      setStatusBusy(null);
    }
  };

  const addEvent = async (ev) => {
    ev.preventDefault();
    if (!eventFor) return;
    setEventBusy(true);
    try {
      await api.post("/disciplinary/cases/" + encodeURIComponent(eventFor) + "/events", eventForm);
      setEventFor(null);
      setEventForm(emptyEvent());
      toast.success("Timeline entry added");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not add timeline entry");
    } finally {
      setEventBusy(false);
    }
  };

  return (
    <section className="bg-white border border-[#E2DFD6] rounded-lg p-6 space-y-4" data-testid="disciplinary-panel">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="font-heading text-lg font-semibold inline-flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-[#8B6A14]" strokeWidth={1.5} />
            Disciplinary cases
          </h3>
          <p className="text-xs text-[#686D76] mt-1">
            Confidential HR records. Entries are retained in the case timeline and audit log.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen((open) => !open)}
          className="inline-flex items-center gap-1.5 bg-[#0A4A1E] hover:bg-[#063514] text-white text-xs px-3 py-2 rounded-md"
          data-testid="disciplinary-create-toggle"
        >
          {createOpen ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
          {createOpen ? "Cancel" : "Open HR case"}
        </button>
      </div>

      {createOpen && (
        <form onSubmit={openCase} className="border border-[#E2DFD6] bg-[#FDFCFB] rounded-md p-4 space-y-3" data-testid="disciplinary-create-form">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-[11px] text-[#525860] uppercase tracking-wider">
              Category
              <select
                value={caseForm.category}
                onChange={(ev) => setCaseForm({ ...caseForm, category: ev.target.value })}
                className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm normal-case tracking-normal"
                data-testid="disciplinary-category"
              >
                {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="text-[11px] text-[#525860] uppercase tracking-wider">
              Incident date
              <input
                required type="date" value={caseForm.incident_date}
                onChange={(ev) => setCaseForm({ ...caseForm, incident_date: ev.target.value })}
                className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data normal-case tracking-normal"
                data-testid="disciplinary-incident-date"
              />
            </label>
          </div>
          <label className="block text-[11px] text-[#525860] uppercase tracking-wider">
            Case title
            <input
              required minLength={3} maxLength={160} value={caseForm.title}
              onChange={(ev) => setCaseForm({ ...caseForm, title: ev.target.value })}
              className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm normal-case tracking-normal"
              data-testid="disciplinary-title"
            />
          </label>
          <label className="block text-[11px] text-[#525860] uppercase tracking-wider">
            Initial summary
            <textarea
              required minLength={10} maxLength={5000} rows={3} value={caseForm.summary}
              onChange={(ev) => setCaseForm({ ...caseForm, summary: ev.target.value })}
              className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm normal-case tracking-normal"
              data-testid="disciplinary-summary"
            />
          </label>
          <div className="flex justify-end">
            <button
              type="submit" disabled={createBusy}
              className="bg-[#0A4A1E] text-white text-xs font-medium px-4 py-2 rounded-md disabled:opacity-50"
              data-testid="disciplinary-create-submit"
            >
              {createBusy ? "Saving…" : "Create case"}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="py-6 text-center text-xs text-[#686D76]" data-testid="disciplinary-loading">Loading HR cases…</div>
      ) : loadError ? (
        <div className="flex items-center justify-between gap-3 bg-[#FBF1DE] rounded-md p-3" data-testid="disciplinary-error">
          <span className="text-xs text-[#8B6A14]">Could not load confidential HR cases.</span>
          <button type="button" onClick={load} className="text-xs underline text-[#8B6A14]" data-testid="disciplinary-retry">Retry</button>
        </div>
      ) : cases.length === 0 ? (
        <div className="py-6 text-center text-xs text-[#686D76]" data-testid="disciplinary-empty">No cases recorded for this employee.</div>
      ) : (
        <div className="space-y-3" data-testid="disciplinary-case-list">
          {cases.map((row) => (
            <article key={row.id} className="border border-[#E2DFD6] rounded-md p-4 space-y-3" data-testid="disciplinary-case">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0">
                  <h4 className="font-semibold text-sm text-[#1A1C1E]">{row.title}</h4>
                  <div className="flex items-center gap-2 mt-1 text-[10px] text-[#686D76]">
                    <span>{CATEGORIES.find(([value]) => value === row.category)?.[1] || "Other"}</span>
                    <span>·</span>
                    <span className="inline-flex items-center gap-1">
                      <CalendarDays className="w-3 h-3" /> Incident {row.incident_date}
                    </span>
                  </div>
                </div>
                <span className={"text-[10px] uppercase tracking-wide px-2 py-1 rounded-full " + (STATUS_STYLES[row.status] || "bg-[#F1EEE6] text-[#525860]")}>
                  {statusText(row.status)}
                </span>
              </div>
              <p className="text-xs text-[#525860] whitespace-pre-wrap break-words">{row.summary}</p>

              <div className="flex items-end justify-between gap-3 flex-wrap border-t border-[#F1EEE6] pt-3">
                <label className="block text-[10px] uppercase tracking-wider text-[#525860]">
                  Case status
                  <select
                    value={row.status}
                    disabled={statusBusy === row.id}
                    onChange={(ev) => changeStatus(row, ev.target.value)}
                    className="mt-1 block bg-white border border-[#E2DFD6] rounded-md px-2.5 py-1.5 text-xs normal-case tracking-normal disabled:opacity-50"
                    data-testid="disciplinary-status"
                  >
                    {STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                {row.status !== "closed" && (
                  <button
                    type="button"
                    onClick={() => {
                      setEventForm(emptyEvent());
                      setEventFor(eventFor === row.id ? null : row.id);
                    }}
                    className="inline-flex items-center gap-1.5 text-xs text-[#26547C] hover:underline"
                    data-testid="disciplinary-event-toggle"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add timeline entry
                  </button>
                )}
              </div>

              {eventFor === row.id && row.status !== "closed" && (
                <form onSubmit={addEvent} className="bg-[#F7F6F2] rounded-md p-3 space-y-3" data-testid="disciplinary-event-form">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <label className="text-[10px] uppercase tracking-wider text-[#525860]">
                      Entry type
                      <select
                        value={eventForm.event_type}
                        onChange={(ev) => setEventForm({ ...eventForm, event_type: ev.target.value })}
                        className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-2.5 py-2 text-xs normal-case tracking-normal"
                        data-testid="disciplinary-event-type"
                      >
                        {EVENT_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    </label>
                    <label className="text-[10px] uppercase tracking-wider text-[#525860]">
                      Date
                      <input
                        required type="date" value={eventForm.occurred_on}
                        onChange={(ev) => setEventForm({ ...eventForm, occurred_on: ev.target.value })}
                        className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-2.5 py-2 text-xs font-data normal-case tracking-normal"
                        data-testid="disciplinary-event-date"
                      />
                    </label>
                  </div>
                  <label className="block text-[10px] uppercase tracking-wider text-[#525860]">
                    Record
                    <textarea
                      required minLength={3} maxLength={5000} rows={3} value={eventForm.details}
                      onChange={(ev) => setEventForm({ ...eventForm, details: ev.target.value })}
                      className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm normal-case tracking-normal"
                      data-testid="disciplinary-event-details"
                    />
                  </label>
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setEventFor(null)} className="text-xs px-3 py-2 border border-[#E2DFD6] rounded-md" data-testid="disciplinary-event-cancel">Cancel</button>
                    <button type="submit" disabled={eventBusy} className="text-xs px-3 py-2 bg-[#0A4A1E] text-white rounded-md disabled:opacity-50" data-testid="disciplinary-event-submit">
                      {eventBusy ? "Saving…" : "Add entry"}
                    </button>
                  </div>
                </form>
              )}

              {(row.events || []).length > 0 && (
                <div className="space-y-2" data-testid="disciplinary-timeline">
                  <div className="text-[10px] uppercase tracking-wider text-[#525860]">Case timeline</div>
                  {[...(row.events || [])].reverse().map((event) => (
                    <div key={event.id} className="border-l-2 border-[#E2DFD6] pl-3 py-0.5">
                      <div className="flex items-center gap-1.5 text-[10px] text-[#686D76]">
                        <Clock3 className="w-3 h-3" />
                        <span>{EVENT_LABELS[event.event_type] || "Timeline entry"}</span>
                        <span>· {event.occurred_on}</span>
                        <span>· {event.created_by}</span>
                      </div>
                      <p className="mt-0.5 text-xs text-[#525860] whitespace-pre-wrap break-words">{event.details}</p>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
