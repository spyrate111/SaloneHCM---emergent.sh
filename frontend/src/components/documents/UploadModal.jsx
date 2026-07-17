import { Upload, X } from "lucide-react";
import { CATEGORIES, ACCEPT } from "./constants";

export default function UploadModal({ employees, submitting, onClose, onSubmit }) {
  const handleSubmit = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.currentTarget);
    const ok = await onSubmit(fd);
    if (ok) onClose();
  };

  return (
    <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4" data-testid="documents-upload-modal">
      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-md p-6 space-y-4"
        encType="multipart/form-data"
      >
        <div className="flex items-center justify-between">
          <h3 className="font-heading text-lg font-semibold">Upload document</h3>
          <button type="button" onClick={onClose} className="text-[#525860] hover:text-[#1A1C1E]">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div>
          <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Employee</label>
          <select required name="employee_id" data-testid="upload-employee-select" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
            <option value="">Select employee…</option>
            {employees.map((e) => (
              <option key={e.id} value={e.id}>{e.first_name} {e.last_name} · {e.department}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Category</label>
          <select required name="category" data-testid="upload-category-select" defaultValue="contract" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
            {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Description (optional)</label>
          <input
            name="description"
            data-testid="upload-description-input"
            placeholder="e.g. Employment contract — 2026"
            className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">File · PDF, DOCX, JPG, PNG · max 10MB</label>
          <input
            required
            name="file"
            type="file"
            accept={ACCEPT}
            data-testid="upload-file-input"
            className="w-full text-sm file:bg-[#F7F6F2] file:border-0 file:rounded-md file:px-3 file:py-2 file:mr-3 file:text-xs file:font-medium file:text-[#0A4A1E]"
          />
        </div>

        <div className="flex items-center justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6] hover:bg-[#F7F6F2]">Cancel</button>
          <button
            type="submit"
            disabled={submitting}
            data-testid="upload-submit"
            className="inline-flex items-center gap-2 text-sm bg-[#0A4A1E] hover:bg-[#063514] text-white px-4 py-2 rounded-md disabled:opacity-60"
          >
            <Upload className="w-4 h-4" strokeWidth={1.5} /> {submitting ? "Uploading…" : "Upload"}
          </button>
        </div>
      </form>
    </div>
  );
}
