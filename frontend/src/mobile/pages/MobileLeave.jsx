/**
 * Mobile leave — mine + reports queue (if I'm a manager). Employees can
 * submit a new request via a bottom-sheet modal.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import api from "../../lib/api";
import { CalendarDays, Plus, CheckCircle2, XCircle, Clock, ChevronLeft, ChevronRight, AlertTriangle, X } from "lucide-react";
import { ymNow, shiftMonth, daysInMonth, firstDow, monthLabel, buildDayMap, todayKey } from "../../lib/leaveCal";

const CACHE_KEY = "salonehcm_m_leave";
const ME_CACHE_KEY = "salonehcm_m_me";
const OUTBOX_PREFIX = "salonehcm_m_leave_outbox";

function readCachedMe() {
  try { return JSON.parse(localStorage.getItem(ME_CACHE_KEY) || "null"); } catch { return null; }
}

function outboxKey(employeeId) {
  return OUTBOX_PREFIX + ":" + employeeId;
}

function readOutbox(employeeId) {
  if (!employeeId) return [];
  try { return JSON.parse(localStorage.getItem(outboxKey(employeeId)) || "[]"); } catch { return []; }
}

function writeOutbox(employeeId, items) {
  if (!employeeId) return false;
  try {
    localStorage.setItem(outboxKey(employeeId), JSON.stringify(items));
    return true;
  } catch {
    return false;
  }
}

function makeClientRequestId() {
  return globalThis.crypto?.randomUUID?.()
    || "offline-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
}

const STATUS_STYLE = {
  pending:  { cls: "bg-[#F6EDD8] text-[#8B6A14]", icon: Clock },
  queued_offline: { cls: "bg-[#F6EDD8] text-[#8B6A14]", icon: Clock },
  needs_attention: { cls: "bg-[#FBE9E9] text-[#B03A2E]", icon: AlertTriangle },
  approved: { cls: "bg-[#E4F7E7] text-[#0A4A1E]", icon: CheckCircle2 },
  rejected: { cls: "bg-[#FBE9E9] text-[#B03A2E]", icon: XCircle },
  withdrawn: { cls: "bg-[#EFEEE9] text-[#686D76]", icon: XCircle },
};

export default function MobileLeave() {
  const [rows, setRows] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY) || "[]"); } catch { return []; }
  });
  const [showForm, setShowForm] = useState(false);
  const [me, setMe] = useState(readCachedMe);
  const [queued, setQueued] = useState(() => readOutbox(readCachedMe()?.employee_id));
  const syncInFlight = useRef(false);

  const refresh = () => {
    api.get("/leave").then((r) => {
      const data = r.data || [];
      setRows(data);
      try { localStorage.setItem(CACHE_KEY, JSON.stringify(data)); } catch { /* noop */ }
    }).catch(() => { /* keep cache */ });
    api.get("/auth/me").then((r) => {
      setMe(r.data);
      try { localStorage.setItem(ME_CACHE_KEY, JSON.stringify(r.data)); } catch { /* noop */ }
      setQueued(readOutbox(r.data?.employee_id));
    }).catch(() => {});
  };
  useEffect(refresh, []);

  useEffect(() => {
    const employeeId = me?.employee_id;
    if (!employeeId) return undefined;

    const sync = async () => {
      if (!navigator.onLine || syncInFlight.current) return;
      syncInFlight.current = true;
      let items = readOutbox(employeeId);
      try {
        for (const item of items) {
          if (item.sync_error) continue;
          try {
            const response = await api.post("/leave", {
              employee_id: employeeId,
              leave_type: item.leave_type,
              start_date: item.start_date,
              end_date: item.end_date,
              reason: item.reason,
              client_request_id: item.client_request_id,
            });
            items = items.filter((queuedItem) => queuedItem.client_request_id !== item.client_request_id);
            writeOutbox(employeeId, items);
            setQueued(items);
            setRows((current) => {
              const next = [response.data, ...current.filter((row) => row.client_request_id !== item.client_request_id)];
              try { localStorage.setItem(CACHE_KEY, JSON.stringify(next)); } catch { /* noop */ }
              return next;
            });
          } catch (e) {
            const status = e?.response?.status;
            if (status >= 400 && status < 500 && status !== 429) {
              const detail = e?.response?.data?.detail;
              const message = typeof detail === "string" ? detail : "The request was rejected. Remove it and submit again.";
              items = items.map((queuedItem) => queuedItem.client_request_id === item.client_request_id
                ? { ...queuedItem, status: "needs_attention", sync_error: message }
                : queuedItem);
              writeOutbox(employeeId, items);
              setQueued(items);
              toast.error("An offline leave request needs your attention.");
              continue;
            }
            break;
          }
        }
      } finally {
        syncInFlight.current = false;
      }
    };

    void sync();
    window.addEventListener("online", sync);
    return () => window.removeEventListener("online", sync);
  }, [me?.employee_id]);

  const removeQueued = (clientRequestId) => {
    const employeeId = me?.employee_id;
    if (!employeeId) return;
    const next = readOutbox(employeeId).filter((item) => item.client_request_id !== clientRequestId);
    writeOutbox(employeeId, next);
    setQueued(next);
  };

  const enqueueLeave = (item) => {
    const employeeId = item.employee_id || me?.employee_id;
    if (!employeeId) return false;
    const current = readOutbox(employeeId);
    if (current.some((queuedItem) => queuedItem.client_request_id === item.client_request_id)) return true;
    const next = [...current, item];
    if (!writeOutbox(employeeId, next)) return false;
    setQueued(next);
    if (navigator.onLine) window.dispatchEvent(new Event("online"));
    return true;
  };

  const serverRequestIds = new Set(rows.map((row) => row.client_request_id).filter(Boolean));
  const mine = [
    ...rows.filter((row) => row.employee_id === me?.employee_id),
    ...queued.filter((item) => item.employee_id === me?.employee_id
      && !serverRequestIds.has(item.client_request_id)),
  ].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
  const reports = rows.filter((r) => r.employee_id !== me?.employee_id && r.status === "pending");

  const focusId = useMemo(() => new URLSearchParams(window.location.search).get("focus"), []);
  useEffect(() => {
    if (!focusId || rows.length === 0) return;
    const el = document.getElementById(`leave-req-${focusId}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusId, rows.length]);

  const [conflict, setConflict] = useState(null); // {lid, ...conflictData}
  const [suggesting, setSuggesting] = useState(false);
  const suggestToEmployee = async () => {
    setSuggesting(true);
    try {
      await api.post(`/leave/${conflict.lid}/suggest-dates`);
      toast.success(`Alternative dates sent to ${conflict.employee_name}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not send suggestion");
    } finally {
      setSuggesting(false);
    }
  };

  const doDecide = async (id, status) => {
    try {
      await api.put(`/leave/${id}/decision`, { status });
      toast.success(`Leave ${status}`);
      refresh();
    } catch (e) {
      toast.error("Could not update — check your connection");
    }
  };

  const decide = async (id, status) => {
    if (status === "approved") {
      try {
        const r = await api.get(`/leave/${id}/conflicts`);
        if (r.data.warn) { setConflict({ lid: id, ...r.data }); return; }
      } catch { /* no access to check — proceed */ }
    }
    await doDecide(id, status);
  };

  return (
    <div className="p-4 space-y-4" data-testid="mobile-leave">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-[#0A4A1E]">Leave</h1>
          <p className="text-[11px] text-[#525860]">{mine.length} of mine · {reports.length} pending decisions</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="bg-[#0A4A1E] text-white text-sm px-3 py-2 rounded-lg flex items-center gap-1 active:bg-[#083A17]"
          data-testid="mobile-leave-new"
        >
          <Plus className="w-4 h-4" /> New
        </button>
      </div>

      <SuggestionsInbox onAccepted={refresh} />

      <TeamCalendar />

      {reports.length > 0 && (
        <section data-testid="mobile-leave-reports">
          <div className="text-[10px] uppercase tracking-widest text-[#8B6A14] mb-2">Waiting on you</div>
          <div className="space-y-2">
            {reports.map((lv) => (
              <div key={lv.id} id={`leave-req-${lv.id}`}
                   className={`bg-white border rounded-xl p-3 ${focusId === lv.id ? "border-[#D1603D] ring-2 ring-[#D1603D]/40" : "border-[#E2DFD6]"}`}>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium truncate">{lv.employee_name}</div>
                    <div className="text-[11px] text-[#525860] mt-0.5">
                      {lv.leave_type} · {lv.days}d · {lv.start_date} → {lv.end_date}
                    </div>
                    {lv.reason && <div className="text-[11px] text-[#686D76] mt-1 italic">"{lv.reason}"</div>}
                  </div>
                  <StatusPill s={lv.status} />
                </div>
                {lv.status === "pending" && (
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => decide(lv.id, "approved")}
                      className="flex-1 bg-[#0A4A1E] text-white text-xs py-2 rounded-lg active:bg-[#083A17]"
                      data-testid={`mobile-leave-approve-${lv.id}`}
                    >Approve</button>
                    <button
                      onClick={() => decide(lv.id, "rejected")}
                      className="flex-1 border border-[#B03A2E] text-[#B03A2E] text-xs py-2 rounded-lg active:bg-[#FBE9E9]"
                      data-testid={`mobile-leave-reject-${lv.id}`}
                    >Reject</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      <section data-testid="mobile-leave-mine">
        <div className="text-[10px] uppercase tracking-widest text-[#525860] mb-2">My requests</div>
        {mine.length === 0 ? (
          <div className="text-center py-8 text-[#525860]">
            <CalendarDays className="w-10 h-10 mx-auto text-[#A1A5AB]" />
            <p className="mt-2 text-sm">No leave requests yet.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {mine.map((lv) => (
              <div key={lv.id} className="bg-white border border-[#E2DFD6] rounded-xl p-3 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium capitalize">{lv.leave_type} · {lv.days}d</div>
                  <div className="text-[11px] text-[#525860] mt-0.5">{lv.start_date} → {lv.end_date}</div>
                  {lv.reason && <div className="text-[11px] text-[#686D76] mt-1 italic">"{lv.reason}"</div>}
                </div>
                <div className="flex items-center gap-2">
                  <StatusPill s={lv.status} />
                  {lv.is_offline_queue && (
                    <button onClick={() => removeQueued(lv.client_request_id)} className="text-[10px] text-[#686D76] underline">
                      Remove
                    </button>
                  )}
                </div>
                {lv.sync_error && (
                  <div className="text-[11px] text-[#B03A2E] mt-2">{lv.sync_error}</div>
                )}
              </div>
            ))}
          </div>
        )}
        {queued.some((item) => !item.sync_error) && (
          <p className="text-[10px] text-[#686D76] mt-2">Saved leave requests stay on this device until they are submitted online.</p>
        )}
      </section>

      {conflict && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-end" onClick={() => setConflict(null)} data-testid="mobile-leave-conflict-sheet">
          <div onClick={(e) => e.stopPropagation()} className="bg-white w-full rounded-t-2xl p-4 space-y-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-5 h-5 text-[#8B6A14] flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-bold">Coverage warning</div>
                <p className="text-[11px] text-[#8B6A14] mt-0.5">
                  Approving {conflict.employee_name}'s leave puts {conflict.threshold}+ of {conflict.branch_name}'s {conflict.headcount} staff off the same day.
                </p>
              </div>
            </div>
            <div className="max-h-40 overflow-y-auto space-y-1.5">
              {conflict.days.map((d) => (
                <div key={d.date} className="text-[11px]" data-testid={`mobile-leave-conflict-day-${d.date}`}>
                  <span className="font-data font-semibold">{d.date}</span>
                  <span className="text-[#B03A2E] font-semibold"> — {d.off_count} off</span>
                  {d.already_off.length > 0 && <span className="text-[#8A8F96]"> ({d.already_off.join(", ")})</span>}
                </div>
              ))}
            </div>
            {conflict.suggestions?.length > 0 && (
              <div className="border-t border-[#EAD9AE] pt-2" data-testid="mobile-leave-conflict-suggestions">
                <div className="text-[11px] font-semibold text-[#8B6A14] mb-1">Better-covered nearby dates:</div>
                <div className="flex flex-wrap gap-1 mb-2">
                  {conflict.suggestions.map((s) => (
                    <span key={s.start_date} className="text-[11px] font-data border border-[#8B6A14]/40 bg-white text-[#8B6A14] px-2 py-0.5 rounded-md"
                      data-testid={`mobile-leave-conflict-suggestion-${s.start_date}`}>
                      {s.start_date === s.end_date ? s.start_date : `${s.start_date} → ${s.end_date}`}
                    </span>
                  ))}
                </div>
                <button onClick={suggestToEmployee} disabled={suggesting}
                  className="w-full text-xs font-semibold border border-[#8B6A14] text-[#8B6A14] py-2 rounded-lg active:bg-[#FDF8EC] disabled:opacity-50"
                  data-testid="mobile-leave-conflict-suggest-btn">
                  {suggesting ? "Sending…" : "Suggest these dates to employee"}
                </button>
              </div>
            )}
            <div className="flex gap-2">
              <button onClick={() => setConflict(null)}
                className="flex-1 text-xs font-semibold border border-[#E2DFD6] py-2.5 rounded-lg"
                data-testid="mobile-leave-conflict-cancel">Cancel</button>
              <button onClick={async () => { const id = conflict.lid; setConflict(null); await doDecide(id, "approved"); }}
                className="flex-1 text-xs font-semibold bg-[#8B6A14] text-white py-2.5 rounded-lg"
                data-testid="mobile-leave-conflict-approve-anyway">Approve anyway</button>
            </div>
          </div>
        </div>
      )}
      {showForm && (
        <LeaveForm
          employeeId={me?.employee_id}
          employee={me}
          onQueued={enqueueLeave}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); refresh(); }}
        />
      )}
    </div>
  );
}

/** Alternative-date suggestions from an approver — 1-tap resubmit. */
function SuggestionsInbox({ onAccepted }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(null); // `${sid}:${start}`

  const load = () => {
    api.get("/leave/suggestions/mine").then((r) => setItems(r.data || [])).catch(() => {});
  };
  useEffect(load, []);

  const accept = async (sug, range) => {
    const key = `${sug.id}:${range.start_date}`;
    setBusy(key);
    try {
      await api.post(`/leave/suggestions/${sug.id}/accept`, {
        start_date: range.start_date, end_date: range.end_date,
      });
      toast.success("Leave re-submitted with the new dates");
      setItems((prev) => prev.filter((s) => s.id !== sug.id));
      onAccepted?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not re-submit — try again");
    } finally {
      setBusy(null);
    }
  };

  const dismiss = async (sug) => {
    try {
      await api.post(`/leave/suggestions/${sug.id}/dismiss`);
      setItems((prev) => prev.filter((s) => s.id !== sug.id));
      toast("Suggestion dismissed — your original request is unchanged");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not dismiss — try again");
    }
  };

  if (items.length === 0) return null;
  const fmt = (r) => (r.start_date === r.end_date ? r.start_date : `${r.start_date} → ${r.end_date}`);

  return (
    <section className="bg-[#FDF8EC] border border-[#EAD9AE] rounded-xl p-3 space-y-3" data-testid="mobile-leave-suggestions-inbox">
      <div className="flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-[#8B6A14] flex-shrink-0 mt-0.5" />
        <div>
          <div className="text-sm font-bold text-[#8B6A14]">Alternative dates suggested</div>
          <p className="text-[11px] text-[#8B6A14]/80 mt-0.5">
            Your approver proposed better-covered dates. Tap one to re-submit instantly.
          </p>
        </div>
      </div>
      {items.map((sug) => (
        <div key={sug.id} className="bg-white border border-[#EAD9AE] rounded-lg p-2.5 space-y-2"
             data-testid={`mobile-leave-suggestion-${sug.id}`}>
          <div className="flex items-start justify-between gap-2">
            <div className="text-[11px] text-[#525860]">
              <span className="capitalize font-semibold">{sug.leave_type}</span> leave{" "}
              <span className="font-data">{fmt(sug.original)}</span> · from {sug.suggested_by}
            </div>
            <button onClick={() => dismiss(sug)} aria-label="Dismiss suggestion"
              className="p-1 -m-1 text-[#8A8F96] active:text-[#B03A2E] flex-shrink-0"
              data-testid={`mobile-leave-suggestion-dismiss-${sug.id}`}>
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-1.5">
            {(sug.suggestions || []).map((r) => {
              const key = `${sug.id}:${r.start_date}`;
              return (
                <button key={r.start_date} onClick={() => accept(sug, r)} disabled={!!busy}
                  className="w-full flex items-center justify-between text-xs border border-[#0A4A1E]/30 text-[#0A4A1E] font-semibold px-2.5 py-2 rounded-lg active:bg-[#E4F7E7] disabled:opacity-50"
                  data-testid={`mobile-leave-suggestion-accept-${r.start_date}`}>
                  <span className="font-data">{fmt(r)}</span>
                  <span className="flex items-center gap-1 text-[10px] uppercase tracking-wide">
                    {busy === key ? "Re-submitting…" : <><CheckCircle2 className="w-3.5 h-3.5" /> Use these dates</>}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}

/** Compact team calendar — managers/admins only (endpoint 403s others → hidden).
 *  A count dot per day; tap a day to see who's off. */
function TeamCalendar() {
  const [month, setMonth] = useState(ymNow());
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(todayKey());

  useEffect(() => {
    api.get("/leave/calendar", { params: { month } })
      .then((r) => setData(r.data))
      .catch(() => setData(null));
  }, [month]);

  const dayMap = useMemo(() => (data ? buildDayMap(month, data.leaves) : {}), [data, month]);
  if (!data) return null;

  const n = daysInMonth(month);
  const pad = firstDow(month);
  const cells = [...Array(pad).fill(null), ...Array.from({ length: n }, (_, i) => i + 1)];
  const tKey = todayKey();
  const selLvs = dayMap[sel] || [];

  return (
    <section className="bg-white border border-[#E2DFD6] rounded-xl p-3 space-y-2" data-testid="mobile-leave-calendar">
      <div className="flex items-center gap-2">
        <CalendarDays className="w-4 h-4 text-[#0A4A1E]" />
        <div className="flex-1 text-sm font-semibold text-[#0A4A1E]">Team calendar</div>
        <button onClick={() => setMonth(shiftMonth(month, -1))} className="p-1 rounded-md border border-[#E2DFD6] active:bg-[#F7F6F2]"
                data-testid="mobile-leave-cal-prev" aria-label="Previous month">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="text-[11px] font-semibold w-24 text-center" data-testid="mobile-leave-cal-month">{monthLabel(month)}</span>
        <button onClick={() => setMonth(shiftMonth(month, 1))} className="p-1 rounded-md border border-[#E2DFD6] active:bg-[#F7F6F2]"
                data-testid="mobile-leave-cal-next" aria-label="Next month">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
      <div className="grid grid-cols-7 gap-0.5 text-center">
        {["S", "M", "T", "W", "T2", "F", "S2"].map((d) => (
          <div key={d} className="text-[9px] uppercase text-[#8A8F96] font-semibold py-0.5">{d[0]}</div>
        ))}
        {cells.map((day, i) => {
          if (day === null) return <div key={`p-${i}`} />;
          const key = `${month}-${String(day).padStart(2, "0")}`;
          const count = (dayMap[key] || []).length;
          const isSel = key === sel;
          const isToday = key === tKey;
          return (
            <button key={key} onClick={() => setSel(key)}
                    className={`relative rounded-lg py-1.5 text-[11px] font-data transition-colors ${
                      isSel ? "bg-[#0A4A1E] text-white"
                      : isToday ? "bg-[#E4F7E7] text-[#0A4A1E] font-bold"
                      : "text-[#1A1C1E] active:bg-[#F7F6F2]"}`}
                    data-testid={`mobile-leave-cal-day-${key}`}>
              {day}
              {count > 0 && (
                <span className={`absolute bottom-0.5 left-1/2 -translate-x-1/2 min-w-[13px] h-[13px] px-0.5 rounded-full text-[8px] font-bold grid place-items-center leading-none ${
                  isSel ? "bg-white text-[#0A4A1E]" : "bg-[#D8A31A] text-white"}`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <div className="border-t border-[#F1EEE6] pt-2" data-testid="mobile-leave-cal-detail">
        <div className="text-[10px] uppercase tracking-widest text-[#525860] mb-1.5">
          {new Date(`${sel}T00:00:00`).toLocaleDateString([], { weekday: "long", day: "numeric", month: "short" })}
          {" · "}{selLvs.length} on leave
        </div>
        {selLvs.length === 0 ? (
          <div className="text-[11px] text-[#8A8F96]">Everyone is in.</div>
        ) : (
          <div className="space-y-1">
            {selLvs.map((lv) => (
              <div key={`${lv.id}-${sel}`} className="flex items-center gap-2 text-[11px]"
                   data-testid={`mobile-leave-cal-item-${lv.id}`}>
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${lv.status === "approved" ? "bg-[#17A035]" : "bg-[#D8A31A]"}`} />
                <span className="font-medium">{lv.employee_name}</span>
                <span className="text-[#8A8F96] capitalize ml-auto">{lv.leave_type} · {lv.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function StatusPill({ s }) {
  const spec = STATUS_STYLE[s] || STATUS_STYLE.pending;
  const Icon = spec.icon;
  const label = s === "queued_offline" ? "Saved offline" : s === "needs_attention" ? "Needs attention" : s;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-widest px-2 py-1 rounded-full ${spec.cls}`}>
      <Icon className="w-3 h-3" /> {label}
    </span>
  );
}

function LeaveForm({ onClose, onSaved, employeeId, employee, onQueued }) {
  const [type, setType] = useState("annual");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  // Coverage planner — live branch coverage preview while picking dates
  const [coverage, setCoverage] = useState(null);
  useEffect(() => {
    if (!start || !end || start > end) { setCoverage(null); return; }
    api.get("/leave/coverage-preview", { params: { start_date: start, end_date: end } })
      .then((r) => setCoverage(r.data)).catch(() => setCoverage(null));
  }, [start, end]);

  // Annual leave balance (current year)
  const [balance, setBalance] = useState(null);
  useEffect(() => {
    api.get("/leave/balance").then((r) => setBalance(r.data)).catch(() => setBalance(null));
  }, []);
  const reqDays = start && end && start <= end
    ? Math.floor((new Date(end) - new Date(start)) / 86400000) + 1 : 0;
  const afterLeft = balance ? balance.remaining - (type === "annual" ? reqDays : 0) : null;

  const submit = async (e) => {
    e.preventDefault();
    if (!start || !end) return toast.error("Pick start and end dates");
    if (start > end) return toast.error("End date must be on or after start date");
    const clientRequestId = makeClientRequestId();
    const payload = {
      employee_id: employeeId,
      leave_type: type,
      start_date: start,
      end_date: end,
      reason,
      client_request_id: clientRequestId,
    };
    const saveOffline = () => {
      if (!employeeId) {
        toast.error("Connect while signed in once before saving leave requests offline.");
        return false;
      }
      const fullName = [employee?.first_name, employee?.last_name].filter(Boolean).join(" ") || "You";
      const saved = onQueued({
        ...payload,
        employee_name: fullName,
        days: Math.max(1, reqDays),
        status: "queued_offline",
        is_offline_queue: true,
        created_at: new Date().toISOString(),
      });
      if (!saved) {
        toast.error("Could not save this request on your device. Check available storage and try again.");
        return false;
      }
      toast.success("Saved on this device; it will submit when you reconnect.");
      onSaved();
      return true;
    };

    setBusy(true);
    try {
      if (!navigator.onLine) {
        saveOffline();
        return;
      }
      await api.post("/leave", payload);
      toast.success("Leave request submitted");
      onSaved();
    } catch (err) {
      const status = err?.response?.status;
      if (!err?.response || status >= 500 || !navigator.onLine) {
        saveOffline();
      } else {
        toast.error(err?.response?.data?.detail || "Could not submit");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-end" onClick={onClose} data-testid="mobile-leave-form">
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-t-2xl w-full p-5 space-y-3"
        style={{ paddingBottom: "calc(1.25rem + env(safe-area-inset-bottom, 0px))" }}
      >
        <div className="w-12 h-1 bg-[#E2DFD6] rounded-full mx-auto mb-2"></div>
        <h2 className="text-base font-bold">Request leave</h2>
        <label className="block">
          <span className="text-[11px] uppercase tracking-widest text-[#525860]">Type</span>
          <select value={type} onChange={(e) => setType(e.target.value)}
                  className="w-full mt-1 border border-[#E2DFD6] rounded-lg h-11 px-3 text-sm"
                  data-testid="mobile-leave-form-type">
            <option value="annual">Annual</option>
            <option value="sick">Sick</option>
            <option value="maternity">Maternity</option>
            <option value="paternity">Paternity</option>
            <option value="unpaid">Unpaid</option>
          </select>
        </label>
        {balance && (
          <div data-testid="mobile-leave-balance"
            className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-lg px-3 py-2 text-[11px] flex items-center justify-between gap-2 flex-wrap">
            <span className="text-[#525860]">
              Annual balance {balance.year}: <b className="font-data text-[#1A1C1E]">{balance.remaining}</b>/{balance.entitlement}d left
              {balance.pending > 0 && <span className="text-[#8B6A14]"> · {balance.pending}d pending</span>}
            </span>
            {reqDays > 0 && type === "annual" && (
              <span data-testid="mobile-leave-balance-after"
                className={`font-semibold font-data ${afterLeft < 0 ? "text-[#B03A2E]" : "text-[#17A035]"}`}>
                {afterLeft < 0 ? `Exceeds by ${-afterLeft}d` : `After this: ${afterLeft}d`}
              </span>
            )}
          </div>
        )}
        <div className="grid grid-cols-2 gap-2">
          <label className="block">
            <span className="text-[11px] uppercase tracking-widest text-[#525860]">Start</span>
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)}
                   className="w-full mt-1 border border-[#E2DFD6] rounded-lg h-11 px-3 text-sm"
                   data-testid="mobile-leave-form-start" />
          </label>
          <label className="block">
            <span className="text-[11px] uppercase tracking-widest text-[#525860]">End</span>
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
                   className="w-full mt-1 border border-[#E2DFD6] rounded-lg h-11 px-3 text-sm"
                   data-testid="mobile-leave-form-end" />
          </label>
        </div>
        {coverage && coverage.headcount > 0 && (
          <div data-testid="mobile-leave-coverage"
            className={`rounded-lg border px-3 py-2 text-[11px] ${coverage.warn ? "bg-[#F6EDD8] border-[#EAD9AE]" : "bg-[#E4F7E7] border-[#BFE5C6]"}`}>
            <div className={`flex items-center gap-1 font-semibold ${coverage.warn ? "text-[#8B6A14]" : "text-[#0A4A1E]"}`}>
              {coverage.warn && <AlertTriangle className="w-3 h-3 flex-shrink-0" />}
              {coverage.warn ? "Thin coverage on these days" : "Coverage looks fine"}
              <span className="ml-auto font-normal text-[#525860]">{coverage.headcount} staff · limit {coverage.threshold}</span>
            </div>
            {coverage.warn ? (
              <div className="mt-1 space-y-0.5 max-h-20 overflow-y-auto">
                {coverage.days.filter((d) => d.breach).slice(0, 4).map((d) => (
                  <div key={d.date} data-testid={`mobile-leave-coverage-day-${d.date}`}>
                    <span className="font-data font-semibold">{d.date}</span>
                    <span className="text-[#B03A2E] font-semibold"> — {d.off_count} off</span>
                    {d.already_off.length > 0 && <span className="text-[#8A8F96]"> ({d.already_off.join(", ")})</span>}
                  </div>
                ))}
                <div className="text-[#8B6A14]">You can still submit — your approver sees this too.</div>
                {coverage.suggestions?.length > 0 && (
                  <div className="pt-1 mt-1 border-t border-[#EAD9AE]" data-testid="mobile-leave-coverage-suggestions">
                    <div className="font-semibold text-[#8B6A14] mb-1">Nearby dates with full coverage:</div>
                    <div className="flex flex-wrap gap-1">
                      {coverage.suggestions.map((sug) => (
                        <button type="button" key={sug.start_date}
                          onClick={() => { setStart(sug.start_date); setEnd(sug.end_date); }}
                          className="border border-[#8B6A14]/40 bg-white text-[#8B6A14] font-data px-2 py-1 rounded-md active:bg-[#FDF8EC]"
                          data-testid={`mobile-leave-coverage-suggestion-${sug.start_date}`}>
                          {sug.start_date === sug.end_date ? sug.start_date : `${sug.start_date} → ${sug.end_date}`}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="mt-0.5 text-[#525860]">
                At most {Math.max(...coverage.days.map((d) => d.off_count))} of {coverage.headcount} teammates off on any day.
              </div>
            )}
          </div>
        )}
        <label className="block">
          <span className="text-[11px] uppercase tracking-widest text-[#525860]">Reason (optional)</span>
          <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)}
                    className="w-full mt-1 border border-[#E2DFD6] rounded-lg p-3 text-sm"
                    data-testid="mobile-leave-form-reason" />
        </label>
        <div className="flex gap-2 pt-1">
          <button type="button" onClick={onClose} className="flex-1 border border-[#E2DFD6] text-[#525860] text-sm py-3 rounded-lg">
            Cancel
          </button>
          <button type="submit" disabled={busy}
                  className="flex-1 bg-[#0A4A1E] text-white text-sm py-3 rounded-lg disabled:opacity-50"
                  data-testid="mobile-leave-form-submit">
            {busy ? "Submitting…" : "Submit"}
          </button>
        </div>
      </form>
    </div>
  );
}
