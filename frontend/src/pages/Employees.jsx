import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { Plus, Search, X } from "lucide-react";
import { Link } from "react-router-dom";
import { DatePicker } from "../components/ui/date-picker";

const empty = {
  first_name: "", last_name: "", email: "", phone: "",
  job_title: "", department: "", location: "Freetown",
  employment_type: "Full-time", basic_salary_sle: 0, allowances_sle: 0,
  nassit_no: "", tin: "", bank_name: "Sierra Leone Commercial Bank", bank_account: "",
  hire_date: "2025-01-01", status: "active",
};

export default function Employees() {
  const [list, setList] = useState([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.get("/employees").then((r) => setList(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const filtered = list.filter((e) => {
    const s = `${e.first_name} ${e.last_name} ${e.email} ${e.department} ${e.job_title}`.toLowerCase();
    return s.includes(q.toLowerCase());
  });

  const submit = async (ev) => {
    ev.preventDefault();
    setBusy(true);
    try {
      await api.post("/employees", { ...form, basic_salary_sle: Number(form.basic_salary_sle), allowances_sle: Number(form.allowances_sle) });
      setOpen(false); setForm(empty); load();
    } catch (e) {
      alert(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Failed to create employee");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6" data-testid="employees-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">HR Management</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold text-[#1A1C1E] mt-1">Employees</h1>
          <p className="text-[#525860] text-sm mt-1">Manage records, contracts, and compensation across your organization.</p>
        </div>
        <button
          data-testid="add-employee-button"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm font-medium px-4 py-2.5 rounded-md transition"
        >
          <Plus className="w-4 h-4" strokeWidth={1.5} /> Add employee
        </button>
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="p-4 border-b border-[#E2DFD6] flex items-center gap-3">
          <Search className="w-4 h-4 text-[#A1A5AB]" strokeWidth={1.5} />
          <input
            data-testid="employees-search-input"
            value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Search by name, email, department…"
            className="flex-1 bg-transparent outline-none text-sm"
          />
          <span className="text-xs text-[#686D76]">{filtered.length} of {list.length}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F7F6F2]">
              <tr>
                {["Name", "Department", "Job Title", "Location", "Status", "Basic (SLE)", ""].map((h) => (
                  <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <tr key={e.id} className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB] transition" data-testid={`employee-row-${e.id}`}>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#EBE8E0] grid place-items-center text-xs font-medium text-[#1A1C1E]">
                        {e.first_name?.[0]}{e.last_name?.[0]}
                      </div>
                      <div>
                        <div className="font-medium text-[#1A1C1E]">{e.first_name} {e.last_name}</div>
                        <div className="text-xs text-[#686D76]">{e.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-[#525860]">{e.department}</td>
                  <td className="py-3 px-4 text-[#525860]">{e.job_title}</td>
                  <td className="py-3 px-4 text-[#525860]">{e.location}</td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full ${
                      e.status === "active" ? "bg-[#E4F7E7] text-[#17A035]" : e.status === "on_leave" ? "bg-[#FBF1DE] text-[#8B6A14]" : "bg-[#E9F2FB] text-[#3A7CB8]"
                    }`}>
                      <span className="w-1.5 h-1.5 rounded-full bg-current" /> {e.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-data text-[#1A1C1E]">{fmtSLE(e.basic_salary_sle)}</td>
                  <td className="py-3 px-4 text-right">
                    <Link to={`/employees/${e.id}`} className="text-xs text-[#26547C] hover:underline">View</Link>
                  </td>
                </tr>
              ))}
              {!filtered.length && (
                <tr><td colSpan={7} className="text-center py-12 text-[#686D76] text-sm">No employees match your search.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setOpen(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="bg-white rounded-lg w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto" data-testid="employee-form">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-heading text-xl font-semibold">New employee</h2>
              <button type="button" onClick={() => setOpen(false)} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {[
                ["first_name", "First name", "text"],
                ["last_name", "Last name", "text"],
                ["email", "Email", "email"],
                ["phone", "Phone", "text"],
                ["job_title", "Job title", "text"],
                ["department", "Department", "text"],
                ["location", "Location", "text"],
                ["nassit_no", "NASSIT No.", "text"],
                ["tin", "TIN", "text"],
                ["bank_name", "Bank name", "text"],
                ["bank_account", "Bank account", "text"],
                ["basic_salary_sle", "Basic salary (SLE)", "number"],
                ["allowances_sle", "Allowances (SLE)", "number"],
              ].map(([k, label, type]) => (
                <div key={k}>
                  <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">{label}</label>
                  <input data-testid={`emp-${k}`} required={["first_name", "last_name", "email", "job_title", "department", "basic_salary_sle"].includes(k)} type={type} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                    className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#26547C]" />
                </div>
              ))}
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Hire date</label>
                <DatePicker data-testid="emp-hire_date" value={form.hire_date} onChange={(v) => setForm({ ...form, hire_date: v })} />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Employment type</label>
                <select value={form.employment_type} onChange={(e) => setForm({ ...form, employment_type: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                  {["Full-time", "Part-time", "Contract", "Intern"].map((o) => <option key={o}>{o}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Status</label>
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                  {["active", "on_leave", "terminated"].map((o) => <option key={o}>{o}</option>)}
                </select>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-6">
              <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="emp-submit" disabled={busy} type="submit" className="px-4 py-2 text-sm bg-[#0A4A1E] hover:bg-[#063514] text-white rounded-md disabled:opacity-60">{busy ? "Saving…" : "Save employee"}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
