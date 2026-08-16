import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { Check, X, Plus, Filter, AlertTriangle } from "lucide-react";
import { DatePicker } from "../components/ui/date-picker";
import LeaveCalendar from "../components/LeaveCalendar";

export default function Leave() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const statusFilter = params.get("status") || "";
  const [list, setList] = useState([]);
  const [emps, setEmps] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ employee_id: "", leave_type: "annual", start_date: "", end_date: "", reason: "" });

  const load = useCallback(() => api.get("/leave").then((r) => setList(r.data)), []);
  useEffect(() => {
    load();
    if (user?.role === "admin") api.get("/employees").then((r) => setEmps(r.data));
  }, [user, load]);

  const submit = async (e) => {
    e.preventDefault();
    await api.post("/leave", form);
    setOpen(false); setForm({ employee_id: "", leave_type: "annual", start_date: "", end_date: "", reason: "" }); load();
  };

  // Coverage planner — live preview of branch coverage while drafting
  const [coverage, setCoverage] = useState(null);
  useEffect(() => {
    const { start_date, end_date, employee_id } = form;
    if (!open || !start_date || !end_date || start_date > end_date) { setCoverage(null); return; }
    if (user?.role === "admin" && !employee_id) { setCoverage(null); return; }
    const params = { start_date, end_date };
    if (user?.role === "admin") params.employee_id = employee_id;
    api.get("/leave/coverage-preview", { params })
      .then((r) => setCoverage(r.data)).catch(() => setCoverage(null));
  }, [open, form, user]);

  // Annual leave balance for the selected employee (self for non-admins)
  const [balance, setBalance] = useState(null);
  useEffect(() => {
    if (!open) { setBalance(null); return; }
    if (user?.role === "admin" && !form.employee_id) { setBalance(null); return; }
    const params = user?.role === "admin" ? { employee_id: form.employee_id } : {};
    api.get("/leave/balance", { params })
      .then((r) => setBalance(r.data)).catch(() => setBalance(null));
  }, [open, form.employee_id, user]);
  const reqDays = form.start_date && form.end_date && form.start_date <= form.end_date
    ? Math.floor((new Date(form.end_date) - new Date(form.start_date)) / 86400000) + 1 : 0;
  const afterLeft = balance ? balance.remaining - (form.leave_type === "annual" ? reqDays : 0) : null;

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
  const doDecide = async (id, status) => { await api.put(`/leave/${id}/decision`, { status }); load(); };
  const decide = async (id, status) => {
    if (status === "approved") {
      try {
        const r = await api.get(`/leave/${id}/conflicts`);
        if (r.data.warn) { setConflict({ lid: id, ...r.data }); return; }
      } catch { /* no access to check — proceed */ }
    }
    await doDecide(id, status);
  };

  const STATUS_BG = { pending: "bg-[#FBF1DE] text-[#8B6A14]", approved: "bg-[#E4F7E7] text-[#17A035]", rejected: "bg-[#E9F2FB] text-[#3A7CB8]" };

  const filtered = statusFilter ? list.filter((l) => l.status === statusFilter) : list;

  return (
    <div className="space-y-6" data-testid="leave-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Leave & Absence</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Leave management</h1>
          <p className="text-[#525860] text-sm mt-1">Employment Act 2023 entitlements — annual, sick, maternity, paternity.</p>
        </div>
        <button data-testid="leave-new-button" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm font-medium px-4 py-2.5 rounded-md">
          <Plus className="w-4 h-4" /> New request
        </button>
      </div>

      {statusFilter && (
        <div data-testid="leave-filter-banner" className="bg-[#E5EEF6] border border-[#26547C]/30 rounded-md px-4 py-2.5 text-sm text-[#26547C] inline-flex items-center gap-2">
          <Filter className="w-3.5 h-3.5" /> Filtered by <strong className="capitalize">{statusFilter}</strong>
          <button data-testid="leave-clear-filter" onClick={() => setParams({})} className="ml-2 text-xs text-[#3A7CB8] hover:underline">clear</button>
        </div>
      )}

      <LeaveCalendar />

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Employee", "Type", "Period", "Days", "Reason", "Status", ""].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {filtered.map((l) => (
              <tr key={l.id} className="border-t border-[#E2DFD6]" data-testid={`leave-row-${l.id}`}>
                <td className="py-3 px-4 font-medium">{l.employee_name}</td>
                <td className="py-3 px-4 capitalize">{l.leave_type}</td>
                <td className="py-3 px-4 font-data text-[#525860]">{l.start_date} → {l.end_date}</td>
                <td className="py-3 px-4 font-data">{l.days}</td>
                <td className="py-3 px-4 text-[#686D76] text-xs max-w-xs truncate">{l.reason || "—"}</td>
                <td className="py-3 px-4"><span className={`text-[11px] font-medium px-2 py-0.5 rounded-full uppercase tracking-wider ${STATUS_BG[l.status]}`}>{l.status}</span></td>
                <td className="py-3 px-4 text-right">
                  {user?.role === "admin" && l.status === "pending" && (
                    <div className="inline-flex gap-1.5">
                      <button data-testid={`approve-${l.id}`} onClick={() => decide(l.id, "approved")} className="p-1.5 rounded bg-[#E4F7E7] text-[#17A035] hover:bg-[#C9EED1]"><Check className="w-3.5 h-3.5" /></button>
                      <button data-testid={`reject-${l.id}`} onClick={() => decide(l.id, "rejected")} className="p-1.5 rounded bg-[#E9F2FB] text-[#3A7CB8] hover:bg-[#D5E5F4]"><X className="w-3.5 h-3.5" /></button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {!list.length && <tr><td colSpan={7} className="py-10 text-center text-sm text-[#686D76]">No leave requests yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {conflict && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setConflict(null)} data-testid="leave-conflict-dialog">
          <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-lg w-full max-w-md overflow-hidden">
            <div className="bg-[#FBF1DE] px-6 py-4 flex items-start gap-3 border-b border-[#EAD9AE]">
              <AlertTriangle className="w-5 h-5 text-[#8B6A14] flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-heading text-lg font-semibold text-[#1A1C1E]">Coverage warning</h3>
                <p className="text-xs text-[#8B6A14] mt-0.5">
                  Approving {conflict.employee_name}'s leave puts {conflict.threshold}+ of {conflict.branch_name}'s {conflict.headcount} staff off the same day.
                </p>
              </div>
            </div>
            <div className="px-6 py-4 max-h-64 overflow-y-auto space-y-2">
              {conflict.days.map((d) => (
                <div key={d.date} className="text-sm" data-testid={`leave-conflict-day-${d.date}`}>
                  <span className="font-data font-semibold">{d.date}</span>
                  <span className="text-[#B03A2E] font-semibold"> — {d.off_count} off</span>
                  {d.already_off.length > 0 && (
                    <div className="text-xs text-[#525860] mt-0.5">Already approved: {d.already_off.join(", ")}</div>
                  )}
                </div>
              ))}
            </div>
            {conflict.suggestions?.length > 0 && (
              <div className="px-6 py-3 border-t border-[#EAD9AE] bg-[#FDF8EC]" data-testid="leave-conflict-suggestions">
                <div className="text-xs font-semibold text-[#8B6A14] mb-1.5">Better-covered nearby dates:</div>
                <div className="flex flex-wrap gap-1.5 mb-2.5">
                  {conflict.suggestions.map((s) => (
                    <span key={s.start_date} className="text-xs font-data border border-[#8B6A14]/40 bg-white text-[#8B6A14] px-2 py-1 rounded-md"
                      data-testid={`leave-conflict-suggestion-${s.start_date}`}>
                      {s.start_date === s.end_date ? s.start_date : `${s.start_date} → ${s.end_date}`}
                    </span>
                  ))}
                </div>
                <button onClick={suggestToEmployee} disabled={suggesting}
                  className="text-xs font-semibold border border-[#8B6A14] text-[#8B6A14] px-3 py-1.5 rounded-md hover:bg-[#8B6A14] hover:text-white disabled:opacity-50"
                  data-testid="leave-conflict-suggest-btn">
                  {suggesting ? "Sending…" : "Suggest these dates to employee"}
                </button>
              </div>
            )}
            <div className="px-6 py-4 border-t border-[#E2DFD6] flex gap-3 justify-end">
              <button onClick={() => setConflict(null)}
                className="text-sm border border-[#E2DFD6] px-4 py-2 rounded-md hover:bg-[#F7F6F2]"
                data-testid="leave-conflict-cancel">Cancel</button>
              <button onClick={async () => { const id = conflict.lid; setConflict(null); await doDecide(id, "approved"); }}
                className="text-sm bg-[#8B6A14] hover:bg-[#6E540F] text-white px-4 py-2 rounded-md"
                data-testid="leave-conflict-approve-anyway">Approve anyway</button>
            </div>
          </div>
        </div>
      )}

      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setOpen(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="bg-white rounded-lg w-full max-w-lg p-6">
            <h2 className="font-heading text-xl font-semibold mb-4">New leave request</h2>
            <div className="space-y-4">
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
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Type</label>
                <select value={form.leave_type} onChange={(e) => setForm({ ...form, leave_type: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                  {["annual", "sick", "maternity", "paternity", "unpaid"].map((o) => <option key={o}>{o}</option>)}
                </select>
              </div>
              {balance && (
                <div data-testid="leave-balance-info"
                  className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2.5 text-xs flex items-center justify-between gap-2 flex-wrap">
                  <span className="text-[#525860]">
                    Annual balance {balance.year}: <b className="font-data text-[#1A1C1E]">{balance.remaining}</b> of {balance.entitlement} days left
                    {balance.pending > 0 && <span className="text-[#8B6A14]"> · {balance.pending}d pending approval</span>}
                  </span>
                  {reqDays > 0 && form.leave_type === "annual" && (
                    <span data-testid="leave-balance-after"
                      className={`font-semibold font-data ${afterLeft < 0 ? "text-[#B03A2E]" : "text-[#17A035]"}`}>
                      {afterLeft < 0 ? `Exceeds balance by ${-afterLeft}d` : `After this: ${afterLeft}d left`}
                    </span>
                  )}
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Start</label>
                  <DatePicker data-testid="leave-start-date" value={form.start_date} onChange={(v) => setForm({ ...form, start_date: v })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">End</label>
                  <DatePicker data-testid="leave-end-date" value={form.end_date} onChange={(v) => setForm({ ...form, end_date: v })} />
                </div>
              </div>
              {coverage && coverage.headcount > 0 && (
                <div data-testid="leave-coverage-preview"
                  className={`rounded-md border px-3 py-2.5 text-xs ${coverage.warn ? "bg-[#FBF1DE] border-[#EAD9AE]" : "bg-[#E4F7E7] border-[#BFE5C6]"}`}>
                  <div className={`flex items-center gap-1.5 font-semibold ${coverage.warn ? "text-[#8B6A14]" : "text-[#17A035]"}`}>
                    <AlertTriangle className={`w-3.5 h-3.5 ${coverage.warn ? "" : "hidden"}`} />
                    {coverage.warn ? "Thin coverage on these days" : "Coverage looks fine"}
                    <span className="ml-auto font-normal text-[#525860]">{coverage.branch_name} · {coverage.headcount} staff · limit {coverage.threshold}</span>
                  </div>
                  {coverage.warn ? (
                    <div className="mt-1.5 space-y-1 max-h-28 overflow-y-auto">
                      {coverage.days.filter((d) => d.breach).slice(0, 7).map((d) => (
                        <div key={d.date} data-testid={`leave-coverage-day-${d.date}`}>
                          <span className="font-data font-semibold">{d.date}</span>
                          <span className="text-[#B03A2E] font-semibold"> — {d.off_count} off</span>
                          {d.already_off.length > 0 && <span className="text-[#525860]"> ({d.already_off.join(", ")})</span>}
                        </div>
                      ))}
                      <div className="text-[#8B6A14]">You can still submit — the approver will see this warning too.</div>
                      {coverage.suggestions?.length > 0 && (
                        <div className="pt-1.5 mt-1 border-t border-[#EAD9AE]" data-testid="leave-coverage-suggestions">
                          <div className="font-semibold text-[#8B6A14] mb-1">Nearby dates with full coverage:</div>
                          <div className="flex flex-wrap gap-1.5">
                            {coverage.suggestions.map((sug) => (
                              <button type="button" key={sug.start_date}
                                onClick={() => setForm({ ...form, start_date: sug.start_date, end_date: sug.end_date })}
                                className="border border-[#8B6A14]/40 bg-white text-[#8B6A14] font-data px-2 py-1 rounded-md hover:bg-[#FDF8EC]"
                                data-testid={`leave-coverage-suggestion-${sug.start_date}`}>
                                {sug.start_date === sug.end_date ? sug.start_date : `${sug.start_date} → ${sug.end_date}`}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="mt-1 text-[#525860]">
                      At most {Math.max(...coverage.days.map((d) => d.off_count))} of {coverage.headcount} teammates off on any requested day.
                    </div>
                  )}
                </div>
              )}
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Reason</label>
                <textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} rows={3} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="leave-submit" type="submit" className="px-4 py-2 text-sm bg-[#0A4A1E] hover:bg-[#063514] text-white rounded-md">Submit</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
