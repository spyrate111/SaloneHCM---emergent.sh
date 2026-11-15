/**
 * Alert snooze rules — admins mute out-of-zone alerts for approved field
 * assignments. Table + create/edit modal + delete. Hides itself on 403.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "../lib/api";
import { BellOff, Plus, Pencil, Trash2, X } from "lucide-react";

export default function OozSnoozePanel() {
  const [rows, setRows] = useState(null); // null = no access
  const [emps, setEmps] = useState([]);
  const [modal, setModal] = useState(null); // {} for new, row for edit

  const load = () =>
    api.get("/mobile/ooz-snoozes").then((r) => setRows(r.data)).catch(() => setRows(null));

  useEffect(() => {
    load();
    api.get("/employees").then((r) => setEmps(r.data || [])).catch(() => {});
  }, []);

  const remove = async (row) => {
    if (!window.confirm(`Remove the snooze for ${row.employee_name}? Out-of-zone alerts will fire again immediately.`)) return;
    try {
      await api.delete(`/mobile/ooz-snoozes/${row.id}`);
      toast.success(`Snooze removed for ${row.employee_name}`);
      load();
    } catch {
      toast.error("Could not delete snooze rule");
    }
  };

  if (!rows) return null;

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="ooz-snooze-panel">
      <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center gap-3 flex-wrap">
        <h3 className="font-heading text-lg font-semibold flex items-center gap-2">
          <BellOff className="w-4 h-4 text-[#0A4A1E]" /> Alert snooze rules
        </h3>
        <span className="text-[11px] text-[#525860]">
          Mute out-of-zone alerts for approved field assignments — punches still show red on the map, logged as snoozed.
        </span>
        <button onClick={() => setModal({})}
          className="ml-auto inline-flex items-center gap-1.5 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-3 py-2 rounded-md"
          data-testid="ooz-snooze-add">
          <Plus className="w-4 h-4" /> New snooze
        </button>
      </div>
      <table className="w-full text-sm" data-testid="ooz-snooze-table">
        <thead className="bg-[#F7F6F2]">
          <tr>{["Employee", "From", "To", "Reason", "Status", ""].map((h, i) => (
            <th key={i} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-4 font-medium">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-[#E2DFD6]" data-testid={`ooz-snooze-row-${r.id}`}>
              <td className="py-2.5 px-4 font-medium">{r.employee_name}</td>
              <td className="py-2.5 px-4 font-data text-xs">{r.start_date}</td>
              <td className="py-2.5 px-4 font-data text-xs">{r.end_date}</td>
              <td className="py-2.5 px-4 text-[#525860]">{r.reason}</td>
              <td className="py-2.5 px-4">
                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                  r.active ? "bg-[#E4F7E7] text-[#0A4A1E]"
                  : r.end_date < new Date().toISOString().split("T")[0]
                    ? "bg-[#F7F6F2] text-[#8A8F96]" : "bg-[#E9F2FB] text-[#3A7CB8]"}`}>
                  {r.active ? "Active" : r.end_date < new Date().toISOString().split("T")[0] ? "Expired" : "Scheduled"}
                </span>
              </td>
              <td className="py-2.5 px-4 text-right whitespace-nowrap">
                <button onClick={() => setModal(r)} className="p-1.5 rounded-md border border-[#E2DFD6] hover:bg-[#F7F6F2] mr-1.5"
                        data-testid={`ooz-snooze-edit-${r.id}`} aria-label="Edit">
                  <Pencil className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => remove(r)} className="p-1.5 rounded-md border border-[#E2DFD6] hover:bg-[#FBE9E9] text-[#B03A2E]"
                        data-testid={`ooz-snooze-delete-${r.id}`} aria-label="Delete">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </td>
            </tr>
          ))}
          {!rows.length && (
            <tr><td colSpan={6} className="py-8 text-center text-sm text-[#686D76]" data-testid="ooz-snooze-empty">
              No snooze rules — every out-of-zone punch alerts the supervisor and admins.
            </td></tr>
          )}
        </tbody>
      </table>
      {modal && (
        <SnoozeModal row={modal.id ? modal : null} emps={emps}
                     onClose={() => setModal(null)}
                     onSaved={() => { setModal(null); load(); }} />
      )}
    </div>
  );
}

function SnoozeModal({ row, emps, onClose, onSaved }) {
  const [form, setForm] = useState({
    employee_id: row?.employee_id || "",
    start_date: row?.start_date || new Date().toISOString().split("T")[0],
    end_date: row?.end_date || "",
    reason: row?.reason || "",
  });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = async (e) => {
    e.preventDefault();
    try {
      if (row) {
        const { employee_id, ...patch } = form;
        await api.patch(`/mobile/ooz-snoozes/${row.id}`, patch);
      } else {
        await api.post("/mobile/ooz-snoozes", form);
      }
      toast.success(row ? "Snooze updated" : "Snooze created");
      onSaved();
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Could not save snooze rule");
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose} data-testid="ooz-snooze-modal">
      <form onSubmit={save} onClick={(e) => e.stopPropagation()} className="bg-white rounded-lg w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-heading text-lg font-semibold">{row ? "Edit snooze rule" : "New snooze rule"}</h3>
          <button type="button" onClick={onClose} aria-label="Close"><X className="w-4 h-4" /></button>
        </div>
        <label className="block">
          <span className="text-[11px] uppercase tracking-wider text-[#525860]">Employee</span>
          <select required disabled={!!row} value={form.employee_id} onChange={set("employee_id")}
            className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm disabled:bg-[#F7F6F2]"
            data-testid="ooz-snooze-employee">
            <option value="">Select employee…</option>
            {emps.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-[11px] uppercase tracking-wider text-[#525860]">From</span>
            <input required type="date" value={form.start_date} onChange={set("start_date")}
              className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data"
              data-testid="ooz-snooze-start" />
          </label>
          <label className="block">
            <span className="text-[11px] uppercase tracking-wider text-[#525860]">To</span>
            <input required type="date" value={form.end_date} onChange={set("end_date")}
              className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data"
              data-testid="ooz-snooze-end" />
          </label>
        </div>
        <label className="block">
          <span className="text-[11px] uppercase tracking-wider text-[#525860]">Reason</span>
          <input required minLength={3} maxLength={200} value={form.reason} onChange={set("reason")}
            placeholder="Field assignment in Bo"
            className="mt-1 w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
            data-testid="ooz-snooze-reason" />
        </label>
        <button type="submit" className="w-full bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm font-medium py-2.5 rounded-md"
                data-testid="ooz-snooze-save">
          {row ? "Save changes" : "Create snooze"}
        </button>
      </form>
    </div>
  );
}
