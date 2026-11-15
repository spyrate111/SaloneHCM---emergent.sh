import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useDocuments } from "../hooks/useDocuments";
import UploadModal from "../components/documents/UploadModal";
import DocumentsTable from "../components/documents/DocumentsTable";
import { CATEGORIES } from "../components/documents/constants";
import { Upload, Search } from "lucide-react";

export default function Documents() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");

  const {
    docs, employees, summary, submitting,
    filterEmp, setFilterEmp, filterCat, setFilterCat,
    upload, download, remove,
  } = useDocuments({ isAdmin });

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
            className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-4 py-2.5 rounded-md transition"
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
            <DocumentsTable
              docs={filtered}
              isAdmin={isAdmin}
              onDownload={download}
              onDelete={remove}
              hasFilters={!!(q || filterCat || filterEmp)}
            />
          </tbody>
        </table>
      </div>

      {open && isAdmin && (
        <UploadModal
          employees={employees}
          submitting={submitting}
          onClose={() => setOpen(false)}
          onSubmit={upload}
        />
      )}
    </div>
  );
}
