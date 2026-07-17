import { useState } from "react";
import { Save, X } from "lucide-react";

export default function SaveScenarioModal({ rulesCount, onClose, onSave }) {
  const [form, setForm] = useState({ title: "", description: "", approver_email: "" });

  const submit = async (ev) => {
    ev.preventDefault();
    if (!form.title.trim()) return;
    const url = await onSave(form);
    if (url) onClose(url);
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => onClose(null)}>
      <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="bg-white rounded-lg w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-heading text-xl font-semibold flex items-center gap-2"><Save className="w-5 h-5 text-[#0A4A1E]" /> Save scenario</h2>
          <button type="button" onClick={() => onClose(null)} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-4">
          <Field label="Title">
            <input data-testid="save-title" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. 2026 Q2 Engineering raises" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
          </Field>
          <Field label="Notes (optional)">
            <textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Why this scenario, who requested it, etc." className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
          </Field>
          <Field label="Approver email (optional)">
            <input data-testid="save-approver" type="email" value={form.approver_email} onChange={(e) => setForm({ ...form, approver_email: e.target.value })} placeholder="cfo@company.sl — sets status to pending" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
            <div className="text-[11px] text-[#686D76] mt-1">Designating an approver flags the scenario as pending until they approve.</div>
          </Field>
          <div className="text-xs text-[#686D76] bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-3">
            <strong>{rulesCount} rule{rulesCount !== 1 ? "s" : ""}</strong> will be saved. The simulation re-runs against current employee data each time the scenario is loaded.
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button type="button" onClick={() => onClose(null)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
          <button data-testid="save-submit" type="submit" className="px-4 py-2 text-sm bg-[#0A4A1E] hover:bg-[#063514] text-white rounded-md">Save & share</button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  );
}
