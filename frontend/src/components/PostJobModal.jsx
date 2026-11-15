import { useState } from "react";
import { X } from "lucide-react";
import api from "../lib/api";
import { toast } from "sonner";

/** New job posting modal — extracted from Talent.jsx.
 *  Owns its own form state; parent gets a callback on successful post. */
export default function PostJobModal({ onClose, onPosted }) {
  const [form, setForm] = useState({
    title: "",
    department: "",
    location: "Freetown",
    employment_type: "Full-time",
    salary_min_sle: 0,
    salary_max_sle: 0,
    description: "",
    status: "open",
  });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/talent/postings", {
        ...form,
        salary_min_sle: Number(form.salary_min_sle),
        salary_max_sle: Number(form.salary_max_sle),
      });
      toast.success("Posting created");
      onPosted();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not post job");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4"
      onClick={onClose}
      data-testid="post-job-modal"
    >
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
        className="bg-white rounded-lg w-full max-w-lg p-6"
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-heading text-xl font-semibold">New job posting</h2>
          <button
            type="button"
            onClick={onClose}
            data-testid="post-job-close"
            className="p-1 text-[#686D76]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="space-y-3">
          {[
            ["title", "Title"],
            ["department", "Department"],
            ["location", "Location"],
          ].map(([k, l]) => (
            <div key={k}>
              <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">
                {l}
              </label>
              <input
                required
                data-testid={`post-job-${k}`}
                value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
              />
            </div>
          ))}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">
                Min SLE
              </label>
              <input
                type="number"
                data-testid="post-job-salary-min"
                value={form.salary_min_sle}
                onChange={(e) => setForm({ ...form, salary_min_sle: e.target.value })}
                className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">
                Max SLE
              </label>
              <input
                type="number"
                data-testid="post-job-salary-max"
                value={form.salary_max_sle}
                onChange={(e) => setForm({ ...form, salary_max_sle: e.target.value })}
                className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">
              Description
            </label>
            <textarea
              rows={3}
              data-testid="post-job-description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button
            type="button"
            onClick={onClose}
            data-testid="post-job-cancel"
            className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            data-testid="post-job-submit"
            className="px-4 py-2 text-sm bg-[#D1603D] hover:bg-[#B84F2F] disabled:opacity-60 text-white rounded-md"
          >
            {busy ? "Posting…" : "Post"}
          </button>
        </div>
      </form>
    </div>
  );
}
