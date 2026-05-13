import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Check, X, Plus, Filter } from "lucide-react";
import { DatePicker } from "../components/ui/date-picker";

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

  const decide = async (id, status) => { await api.put(`/leave/${id}/decision`, { status }); load(); };

  const STATUS_BG = { pending: "bg-[#FBF1DE] text-[#8B6A14]", approved: "bg-[#E6F4EC] text-[#2D7A5D]", rejected: "bg-[#FBEAEA] text-[#B83A3A]" };

  const filtered = statusFilter ? list.filter((l) => l.status === statusFilter) : list;

  return (
    <div className="space-y-6" data-testid="leave-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Leave & Absence</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Leave management</h1>
          <p className="text-[#525860] text-sm mt-1">Employment Act 2023 entitlements — annual, sick, maternity, paternity.</p>
        </div>
        <button data-testid="leave-new-button" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white text-sm font-medium px-4 py-2.5 rounded-md">
          <Plus className="w-4 h-4" /> New request
        </button>
      </div>

      {statusFilter && (
        <div data-testid="leave-filter-banner" className="bg-[#E5EEF6] border border-[#26547C]/30 rounded-md px-4 py-2.5 text-sm text-[#26547C] inline-flex items-center gap-2">
          <Filter className="w-3.5 h-3.5" /> Filtered by <strong className="capitalize">{statusFilter}</strong>
          <button data-testid="leave-clear-filter" onClick={() => setParams({})} className="ml-2 text-xs text-[#B83A3A] hover:underline">clear</button>
        </div>
      )}

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
                      <button data-testid={`approve-${l.id}`} onClick={() => decide(l.id, "approved")} className="p-1.5 rounded bg-[#E6F4EC] text-[#2D7A5D] hover:bg-[#d2eadd]"><Check className="w-3.5 h-3.5" /></button>
                      <button data-testid={`reject-${l.id}`} onClick={() => decide(l.id, "rejected")} className="p-1.5 rounded bg-[#FBEAEA] text-[#B83A3A] hover:bg-[#f4d5d5]"><X className="w-3.5 h-3.5" /></button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {!list.length && <tr><td colSpan={7} className="py-10 text-center text-sm text-[#686D76]">No leave requests yet.</td></tr>}
          </tbody>
        </table>
      </div>

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
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Reason</label>
                <textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} rows={3} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="leave-submit" type="submit" className="px-4 py-2 text-sm bg-[#133326] hover:bg-[#0F281E] text-white rounded-md">Submit</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
