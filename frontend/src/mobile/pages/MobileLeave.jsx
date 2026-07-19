/**
 * Mobile leave — mine + reports queue (if I'm a manager). Employees can
 * submit a new request via a bottom-sheet modal.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "../../lib/api";
import { CalendarDays, Plus, CheckCircle2, XCircle, Clock } from "lucide-react";

const CACHE_KEY = "salonehcm_m_leave";

const STATUS_STYLE = {
  pending:  { cls: "bg-[#F6EDD8] text-[#8B6A14]", icon: Clock },
  approved: { cls: "bg-[#E4F7E7] text-[#0A4A1E]", icon: CheckCircle2 },
  rejected: { cls: "bg-[#FBE9E9] text-[#B03A2E]", icon: XCircle },
};

export default function MobileLeave() {
  const [rows, setRows] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY) || "[]"); } catch { return []; }
  });
  const [showForm, setShowForm] = useState(false);
  const [me, setMe] = useState(null);

  const refresh = () => {
    api.get("/leave").then((r) => {
      const data = r.data || [];
      setRows(data);
      try { localStorage.setItem(CACHE_KEY, JSON.stringify(data)); } catch { /* noop */ }
    }).catch(() => { /* keep cache */ });
    api.get("/auth/me").then((r) => setMe(r.data)).catch(() => {});
  };
  useEffect(refresh, []);

  const mine = rows.filter((r) => r.employee_id === me?.employee_id);
  const reports = rows.filter((r) => r.employee_id !== me?.employee_id);

  const decide = async (id, status) => {
    try {
      await api.put(`/leave/${id}/decision`, { status });
      toast.success(`Leave ${status}`);
      refresh();
    } catch (e) {
      toast.error("Could not update — check your connection");
    }
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

      {reports.length > 0 && (
        <section data-testid="mobile-leave-reports">
          <div className="text-[10px] uppercase tracking-widest text-[#8B6A14] mb-2">Waiting on you</div>
          <div className="space-y-2">
            {reports.map((lv) => (
              <div key={lv.id} className="bg-white border border-[#E2DFD6] rounded-xl p-3">
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
                <StatusPill s={lv.status} />
              </div>
            ))}
          </div>
        )}
      </section>

      {showForm && <LeaveForm onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); refresh(); }} />}
    </div>
  );
}

function StatusPill({ s }) {
  const spec = STATUS_STYLE[s] || STATUS_STYLE.pending;
  const Icon = spec.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-widest px-2 py-1 rounded-full ${spec.cls}`}>
      <Icon className="w-3 h-3" /> {s}
    </span>
  );
}

function LeaveForm({ onClose, onSaved }) {
  const [type, setType] = useState("annual");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!start || !end) return toast.error("Pick start and end dates");
    setBusy(true);
    try {
      await api.post("/leave", { leave_type: type, start_date: start, end_date: end, reason });
      toast.success("Leave request submitted");
      onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not submit");
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
