import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import {
  FolderArchive, Upload, Download, Trash2, X, FileText, Image as ImageIcon,
  FileSignature, Award, Receipt, IdCard, Folder, Search,
} from "lucide-react";

const CATEGORIES = [
  { id: "contract", label: "Contract", icon: FileSignature, color: "bg-[#E6F4EC] text-[#2D7A5D]" },
  { id: "certificate", label: "Certificate", icon: Award, color: "bg-[#FBF1DE] text-[#8B6A14]" },
  { id: "p9_form", label: "P9 / Tax Form", icon: Receipt, color: "bg-[#E5EEF6] text-[#26547C]" },
  { id: "payslip", label: "Payslip", icon: FileText, color: "bg-[#FBE9DF] text-[#B84F2F]" },
  { id: "id_document", label: "ID Document", icon: IdCard, color: "bg-[#F7E5EC] text-[#9A2A52]" },
  { id: "other", label: "Other", icon: Folder, color: "bg-[#EBE8E0] text-[#525860]" },
];
const CAT_BY_ID = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]));

const fmtBytes = (n) => {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
};

const ACCEPT = ".pdf,.docx,.doc,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export default function Documents() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [docs, setDocs] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [filterEmp, setFilterEmp] = useState("");
  const [filterCat, setFilterCat] = useState("");
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [summary, setSummary] = useState({ total: 0, by_category: [] });
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    const params = {};
    if (isAdmin && filterEmp) params.employee_id = filterEmp;
    if (filterCat) params.category = filterCat;
    const r = await api.get("/documents", { params });
    setDocs(r.data);
    if (isAdmin) {
      try {
        const s = await api.get("/documents/stats/summary");
        setSummary(s.data);
      } catch (e) {
        console.warn("documents stats summary failed", e);
      }
    }
  }, [isAdmin, filterEmp, filterCat]);

  useEffect(() => {
    load();
    if (isAdmin) api.get("/employees").then((r) => setEmployees(r.data)).catch(() => {});
  }, [load, isAdmin]);

  const onUpload = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.currentTarget);
    setSubmitting(true);
    try {
      await api.post("/documents/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Document uploaded");
      setOpen(false);
      load();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Upload failed");
    } finally { setSubmitting(false); }
  };

  const onDownload = async (doc) => {
    try {
      const resp = await api.get(`/documents/${doc.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url; a.download = doc.original_filename; a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Download failed");
    }
  };

  const onDelete = async (doc) => {
    if (!window.confirm(`Delete "${doc.original_filename}"?`)) return;
    try {
      await api.delete(`/documents/${doc.id}`);
      toast.success("Document deleted");
      load();
    } catch {
      toast.error("Delete failed");
    }
  };

  const filtered = docs.filter((d) => {
    if (!q) return true;
    const t = q.toLowerCase();
    return (
      d.original_filename?.toLowerCase().includes(t) ||
      d.employee_name?.toLowerCase().includes(t) ||
      d.description?.toLowerCase().includes(t)
    );
  });

  return (
    <div className="space-y-6" data-testid="documents-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Document Vault</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">
            {isAdmin ? "Employee documents" : "My documents"}
          </h1>
          <p className="text-[#525860] text-sm mt-1.5 max-w-xl">
            {isAdmin
              ? "Securely store contracts, certificates, P9 forms and payslips. Files are encrypted at rest and access is audit-logged."
              : "Contracts, payslips and certificates uploaded by HR are available here for download."}
          </p>
        </div>
        {isAdmin && (
          <button
            data-testid="documents-upload-open"
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white text-sm px-4 py-2.5 rounded-md transition"
          >
            <Upload className="w-4 h-4" strokeWidth={1.5} /> Upload document
          </button>
        )}
      </div>

      {isAdmin && summary.total > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3" data-testid="documents-summary">
          {CATEGORIES.map((c) => {
            const stat = summary.by_category.find((x) => x.category === c.id);
            const count = stat?.count || 0;
            const Icon = c.icon;
            return (
              <div key={c.id} className="bg-white border border-[#E2DFD6] rounded-lg px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className={`w-7 h-7 rounded-md grid place-items-center ${c.color}`}>
                    <Icon className="w-3.5 h-3.5" strokeWidth={1.7} />
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-[#525860]">{c.label}</div>
                </div>
                <div className="font-heading text-xl font-bold mt-2 font-data">{count}</div>
              </div>
            );
          })}
        </div>
      )}

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-5 py-4 border-b border-[#E2DFD6] flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A5AB]" strokeWidth={1.5} />
            <input
              data-testid="documents-search"
              placeholder="Search filename, employee, description…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="w-full bg-[#F7F6F2] border border-[#E2DFD6] rounded-md pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#26547C]"
            />
          </div>
          <select
            data-testid="documents-filter-category"
            value={filterCat}
            onChange={(e) => setFilterCat(e.target.value)}
            className="bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
          >
            <option value="">All categories</option>
            {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
          {isAdmin && (
            <select
              data-testid="documents-filter-employee"
              value={filterEmp}
              onChange={(e) => setFilterEmp(e.target.value)}
              className="bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm max-w-[220px]"
            >
              <option value="">All employees</option>
              {employees.map((e) => (
                <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>
              ))}
            </select>
          )}
        </div>

        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>
              {["Document", isAdmin ? "Employee" : "Uploaded by", "Category", "Size", "Uploaded", ""].map((h) => (
                <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((d) => {
              const cat = CAT_BY_ID[d.category] || CAT_BY_ID.other;
              const Icon = (d.content_type || "").startsWith("image/") ? ImageIcon : FileText;
              return (
                <tr key={d.id} className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB]" data-testid={`doc-row-${d.id}`}>
                  <td className="py-3 px-4">
                    <div className="flex items-start gap-2.5">
                      <div className="w-8 h-8 rounded-md bg-[#F7F6F2] border border-[#E2DFD6] grid place-items-center text-[#525860]">
                        <Icon className="w-4 h-4" strokeWidth={1.5} />
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium truncate max-w-[260px]" title={d.original_filename}>{d.original_filename}</div>
                        {d.description && <div className="text-xs text-[#686D76] truncate max-w-[260px]">{d.description}</div>}
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-[#525860]">{isAdmin ? d.employee_name : d.uploaded_by}</td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider px-2 py-0.5 rounded-full ${cat.color}`}>
                      <cat.icon className="w-3 h-3" strokeWidth={1.7} /> {cat.label}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-data text-[#525860] text-xs">{fmtBytes(d.size)}</td>
                  <td className="py-3 px-4 font-data text-[#686D76] text-xs">{new Date(d.uploaded_at).toLocaleDateString()}</td>
                  <td className="py-3 px-4 text-right">
                    <div className="inline-flex items-center gap-1">
                      <button
                        data-testid={`doc-download-${d.id}`}
                        onClick={() => onDownload(d)}
                        className="p-1.5 rounded hover:bg-[#F1EEE6] text-[#26547C]"
                        title="Download"
                      >
                        <Download className="w-4 h-4" strokeWidth={1.5} />
                      </button>
                      {isAdmin && (
                        <button
                          data-testid={`doc-delete-${d.id}`}
                          onClick={() => onDelete(d)}
                          className="p-1.5 rounded hover:bg-[#FBEAEA] text-[#B83A3A]"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" strokeWidth={1.5} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {!filtered.length && (
              <tr><td colSpan={6} className="py-12 text-center text-sm text-[#686D76]">
                <FolderArchive className="w-8 h-8 mx-auto mb-2 text-[#A1A5AB]" strokeWidth={1.3} />
                {q || filterCat || filterEmp ? "No documents match these filters." : (isAdmin ? "No documents yet — upload the first one." : "No documents have been shared with you yet.")}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {open && isAdmin && (
        <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4" data-testid="documents-upload-modal">
          <form
            onSubmit={onUpload}
            className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-md p-6 space-y-4"
            encType="multipart/form-data"
          >
            <div className="flex items-center justify-between">
              <h3 className="font-heading text-lg font-semibold">Upload document</h3>
              <button type="button" onClick={() => setOpen(false)} className="text-[#525860] hover:text-[#1A1C1E]">
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
                className="w-full text-sm file:bg-[#F7F6F2] file:border-0 file:rounded-md file:px-3 file:py-2 file:mr-3 file:text-xs file:font-medium file:text-[#133326]"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button type="button" onClick={() => setOpen(false)} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6] hover:bg-[#F7F6F2]">Cancel</button>
              <button
                type="submit"
                disabled={submitting}
                data-testid="upload-submit"
                className="inline-flex items-center gap-2 text-sm bg-[#133326] hover:bg-[#0F281E] text-white px-4 py-2 rounded-md disabled:opacity-60"
              >
                <Upload className="w-4 h-4" strokeWidth={1.5} /> {submitting ? "Uploading…" : "Upload"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
