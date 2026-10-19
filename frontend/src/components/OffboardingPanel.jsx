import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { LogOut, CheckCircle2, Circle } from "lucide-react";

const ROLE_LABEL = { payroll: "Payroll Officer", hr: "HR Admin", admin: "Admin" };
const STATUS_CLS = {
  in_progress: "bg-[#F6EDD8] text-[#8B6A14]",
  completed: "bg-[#E4F7E7] text-[#0A4A1E]",
};

/** Employee-profile offboarding panel: start exit, role-gated checklist sign-offs. */
export default function OffboardingPanel({ employee, onChanged }) {
  const { user } = useAuth();
  const role = user?.role;
  const isAdmin = ["admin", "superadmin"].includes(role);
  const isHr = isAdmin || role === "hr";
  const [ob, setOb] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get(`/offboarding/employee/${employee.id}`)
      .then((r) => setOb(r.data))
      .catch(() => setOb(null))
      .finally(() => setLoaded(true));
  }, [employee.id]);
  useEffect(load, [load]);

  const start = async () => {
    if (!window.confirm(`Start offboarding for ${employee.first_name} ${employee.last_name}? This marks them as exiting and opens the exit checklist.`)) return;
    setBusy(true);
    try {
      await api.post(`/offboarding/${employee.id}/start`);
      toast.success("Offboarding started");
      load(); onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not start offboarding");
    } finally { setBusy(false); }
  };

  const complete = async (item) => {
    setBusy(true);
    try {
      const r = await api.put(`/offboarding/${ob.id}/items/${item.key}/complete`);
      if (r.data.all_complete) {
        toast.success("Offboarding complete — employee account deactivated");
      } else {
        toast.success(`${item.label} marked complete`);
      }
      load(); onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not complete item");
    } finally { setBusy(false); }
  };

  const cancel = async () => {
    if (!window.confirm("Cancel this offboarding and restore the employee to active?")) return;
    setBusy(true);
    try {
      await api.delete(`/offboarding/${ob.id}`);
      toast.success("Offboarding cancelled");
      load(); onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not cancel");
    } finally { setBusy(false); }
  };

  if (!loaded) return null;

  if (!ob) {
    if (!isHr) return null;
    return (
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 flex items-center justify-between flex-wrap gap-3"
        data-testid="offboarding-panel">
        <div>
          <h3 className="font-heading text-lg font-semibold inline-flex items-center gap-2">
            <LogOut className="w-5 h-5 text-[#B03A2E]" strokeWidth={1.5} /> Offboarding
          </h3>
          <p className="text-sm text-[#525860] mt-1">
            Mark this employee as exiting to open the exit checklist: final settlement, document handover, equipment return and access revocation.
          </p>
        </div>
        <button onClick={start} disabled={busy} data-testid="offboarding-start-btn"
          className="inline-flex items-center gap-2 border border-[#B03A2E] text-[#B03A2E] hover:bg-[#FBE9E9] text-sm font-medium px-4 py-2.5 rounded-md disabled:opacity-50">
          <LogOut className="w-4 h-4" /> Start offboarding
        </button>
      </div>
    );
  }

  const done = ob.items.filter((i) => i.completed).length;
  const mayComplete = (item) => !item.completed && ob.status === "in_progress" &&
    (isAdmin || (item.responsible_role !== "admin" && role === item.responsible_role));

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 space-y-4" data-testid="offboarding-panel">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-heading text-lg font-semibold inline-flex items-center gap-2">
          <LogOut className="w-5 h-5 text-[#B03A2E]" strokeWidth={1.5} /> Offboarding
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#525860] font-data">{done} / {ob.items.length} complete</span>
          <span className={`text-[10px] uppercase tracking-wide px-2 py-1 rounded-full ${STATUS_CLS[ob.status] || "bg-[#F1EEE6] text-[#525860]"}`}
            data-testid="offboarding-status-badge">
            {ob.status.replace("_", " ")}
          </span>
        </div>
      </div>

      <div className="space-y-1">
        {ob.items.map((item) => (
          <div key={item.key} className="flex items-center justify-between gap-3 border-b border-[#F0EEE8] last:border-0 py-2.5"
            data-testid={`offboarding-item-${item.key}`}>
            <div className="flex items-center gap-3 min-w-0">
              {item.completed
                ? <CheckCircle2 className="w-5 h-5 text-[#17A035] shrink-0" strokeWidth={1.7} />
                : <Circle className="w-5 h-5 text-[#C9CCD1] shrink-0" strokeWidth={1.7} />}
              <div className="min-w-0">
                <div className={`text-sm font-medium ${item.completed ? "text-[#686D76] line-through" : "text-[#1A1C1E]"}`}>{item.label}</div>
                <div className="text-[11px] text-[#8A8F96]">
                  {item.completed
                    ? `Signed off by ${item.completed_by} · ${(item.completed_at || "").slice(0, 10)}`
                    : `Responsible: ${ROLE_LABEL[item.responsible_role] || item.responsible_role}`}
                </div>
              </div>
            </div>
            {mayComplete(item) && (
              <button onClick={() => complete(item)} disabled={busy} data-testid={`offboarding-complete-${item.key}`}
                className="text-xs bg-[#0A4A1E] hover:bg-[#063514] text-white px-3 py-1.5 rounded-md disabled:opacity-50 shrink-0">
                Mark complete
              </button>
            )}
          </div>
        ))}
      </div>

      {ob.status === "completed" && (
        <div className="text-sm text-[#0A4A1E] bg-[#E4F7E7] rounded-md px-3 py-2" data-testid="offboarding-completed-note">
          All checklist items signed off on {(ob.completed_at || "").slice(0, 10)} — the employee&rsquo;s account has been deactivated.
        </div>
      )}
      {ob.status === "in_progress" && isHr && (
        <button onClick={cancel} disabled={busy} data-testid="offboarding-cancel-btn"
          className="text-xs border border-[#E2DFD6] text-[#525860] hover:bg-[#F7F6F2] px-3 py-1.5 rounded-md disabled:opacity-50">
          Cancel offboarding
        </button>
      )}
    </div>
  );
}
