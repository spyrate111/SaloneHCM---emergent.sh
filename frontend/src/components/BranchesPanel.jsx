import { useEffect, useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { Plus, X, Pencil, Trash2, Users, Building2 } from "lucide-react";

const errMsg = (e) => {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : d?.message || "Action failed";
};

export default function BranchesPanel({ branches, onChanged }) {
  const [editing, setEditing] = useState(null); // null | {} (new) | branch
  const [assigning, setAssigning] = useState(null);

  const del = async (b) => {
    if (!window.confirm(`Delete branch ${b.name}? Employees will be unassigned.`)) return;
    try {
      await api.delete(`/branches/${b.id}`);
      toast.success("Branch deleted");
      onChanged();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="branches-panel">
      <div className="px-5 py-3 border-b border-[#E2DFD6] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-[#26547C]" />
          <h3 className="font-heading text-sm font-semibold">Branches & Offices · {branches.length}</h3>
        </div>
        <button data-testid="branch-new" onClick={() => setEditing({})}
          className="inline-flex items-center gap-1.5 text-sm bg-[#0A4A1E] text-white px-3 py-1.5 rounded-md">
          <Plus className="w-4 h-4" /> New branch
        </button>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-[#F7F6F2]">
          <tr>
            {["Code", "Name", "Region", "Ministry / MDA", "Supervisor", "Employees", ""].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {branches.map((b) => (
            <tr key={b.id} className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB]" data-testid={`branch-row-${b.id}`}>
              <td className="py-3 px-4 font-data font-medium">{b.code}</td>
              <td className="py-3 px-4">{b.name}</td>
              <td className="py-3 px-4 text-[#525860]">{b.region || "—"}</td>
              <td className="py-3 px-4 text-[#525860]">{b.ministry || "—"}</td>
              <td className="py-3 px-4 text-[#525860]">{b.supervisor_name || <span className="text-[#3A7CB8] text-xs">No supervisor</span>}</td>
              <td className="py-3 px-4 font-data">{b.employee_count}</td>
              <td className="py-3 px-4 text-right">
                <div className="inline-flex items-center gap-1">
                  <button data-testid={`branch-assign-${b.id}`} onClick={() => setAssigning(b)} title="Assign employees"
                    className="p-1.5 rounded hover:bg-[#F1EEE6] text-[#26547C]"><Users className="w-4 h-4" /></button>
                  <button data-testid={`branch-edit-${b.id}`} onClick={() => setEditing(b)} title="Edit"
                    className="p-1.5 rounded hover:bg-[#F1EEE6] text-[#26547C]"><Pencil className="w-4 h-4" /></button>
                  <button data-testid={`branch-delete-${b.id}`} onClick={() => del(b)} title="Delete"
                    className="p-1.5 rounded hover:bg-[#E9F2FB] text-[#3A7CB8]"><Trash2 className="w-4 h-4" /></button>
                </div>
              </td>
            </tr>
          ))}
          {!branches.length && (
            <tr><td colSpan={7} className="py-10 text-center text-sm text-[#686D76]">No branches yet — create the first office.</td></tr>
          )}
        </tbody>
      </table>

      {editing !== null && (
        <BranchModal branch={editing.id ? editing : null} onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); onChanged(); }} />
      )}
      {assigning && (
        <AssignModal branch={assigning} onClose={() => setAssigning(null)}
          onSaved={() => { setAssigning(null); onChanged(); }} />
      )}
    </div>
  );
}

function BranchModal({ branch, onClose, onSaved }) {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({
    name: branch?.name || "", code: branch?.code || "", region: branch?.region || "",
    ministry: branch?.ministry || "", supervisor_user_id: branch?.supervisor_user_id || "",
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/users").then((r) => setUsers(r.data)).catch(() => setUsers([]));
  }, []);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = { ...form, supervisor_user_id: form.supervisor_user_id || null };
      if (branch) {
        delete payload.code;
        await api.patch(`/branches/${branch.id}`, payload);
        toast.success("Branch updated");
      } else {
        await api.post("/branches", payload);
        toast.success("Branch created");
      }
      onSaved();
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="fixed inset-0 z-50 bg-black/40 grid place-items-center p-4" data-testid="branch-modal">
      <form onSubmit={save} className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-heading text-lg font-semibold">{branch ? "Edit branch" : "New branch / office"}</h3>
          <button type="button" onClick={onClose} className="text-[#525860]"><X className="w-4 h-4" /></button>
        </div>
        <Field label="Name"><input data-testid="branch-name" required minLength={2} value={form.name} onChange={set("name")} placeholder="Bo District Office" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
        <Field label="Code (unique, immutable)">
          <input data-testid="branch-code" required minLength={2} disabled={!!branch} value={form.code} onChange={set("code")} placeholder="BO-01"
            className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data uppercase disabled:bg-[#F7F6F2] disabled:text-[#A1A5AB]" />
        </Field>
        <Field label="Region"><input data-testid="branch-region" value={form.region} onChange={set("region")} placeholder="Bo" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
        <Field label="Ministry / MDA (optional link)"><input data-testid="branch-ministry" value={form.ministry} onChange={set("ministry")} placeholder="Ministry of Finance" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
        <Field label="Branch supervisor (approves vouchers before central submission)">
          <select data-testid="branch-supervisor" value={form.supervisor_user_id} onChange={set("supervisor_user_id")}
            className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
            <option value="">— None —</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.name} · {u.email}</option>)}
          </select>
        </Field>
        <div className="flex items-center justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]">Cancel</button>
          <button type="submit" data-testid="branch-save" disabled={busy} className="text-sm bg-[#0A4A1E] text-white px-4 py-2 rounded-md disabled:opacity-50">Save</button>
        </div>
      </form>
    </div>
  );
}

function AssignModal({ branch, onClose, onSaved }) {
  const [employees, setEmployees] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/employees").then((r) => {
      setEmployees(r.data);
      setSelected(new Set(r.data.filter((e) => e.branch_id === branch.id).map((e) => e.id)));
    });
  }, [branch.id]);

  const toggle = (id) => setSelected((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  const save = async () => {
    setBusy(true);
    try {
      const current = new Set(employees.filter((e) => e.branch_id === branch.id).map((e) => e.id));
      const toAdd = [...selected].filter((id) => !current.has(id));
      const toRemove = [...current].filter((id) => !selected.has(id));
      if (toAdd.length) await api.post(`/branches/${branch.id}/assign`, { employee_ids: toAdd });
      if (toRemove.length) await api.post(`/branches/${branch.id}/assign`, { employee_ids: toRemove, unassign: true });
      toast.success("Assignments saved");
      onSaved();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 grid place-items-center p-4" data-testid="assign-modal">
      <div className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-lg p-6 space-y-4 max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between">
          <h3 className="font-heading text-lg font-semibold">Assign employees · {branch.name}</h3>
          <button onClick={onClose} className="text-[#525860]"><X className="w-4 h-4" /></button>
        </div>
        <div className="overflow-y-auto border border-[#E2DFD6] rounded-md divide-y divide-[#E2DFD6]">
          {employees.map((e) => (
            <label key={e.id} data-testid={`assign-emp-${e.id}`}
              className="flex items-center gap-3 px-4 py-2.5 text-sm cursor-pointer hover:bg-[#FDFCFB]">
              <input type="checkbox" checked={selected.has(e.id)} onChange={() => toggle(e.id)} className="accent-[#0A4A1E]" />
              <span className="flex-1">{e.first_name} {e.last_name}</span>
              <span className="text-xs text-[#686D76]">{e.department}</span>
              {e.branch_id && e.branch_id !== branch.id && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#FBF3D9] text-[#8B6A14]">Other branch</span>
              )}
            </label>
          ))}
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-[#686D76] font-data">{selected.size} selected</span>
          <div className="flex gap-2">
            <button onClick={onClose} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]">Cancel</button>
            <button data-testid="assign-save" disabled={busy} onClick={save} className="text-sm bg-[#0A4A1E] text-white px-4 py-2 rounded-md disabled:opacity-50">Save</button>
          </div>
        </div>
      </div>
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
