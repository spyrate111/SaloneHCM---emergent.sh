import { useEffect, useState } from "react";
import api from "../lib/api";
import { ScrollText, User } from "lucide-react";

const ACTION_COLORS = {
  create: "bg-[#E6F4EC] text-[#2D7A5D]",
  update: "bg-[#E5EEF6] text-[#26547C]",
  delete: "bg-[#FBEAEA] text-[#B83A3A]",
  payroll_run: "bg-[#FBE9DF] text-[#B84F2F]",
  leave_approved: "bg-[#E6F4EC] text-[#2D7A5D]",
  leave_rejected: "bg-[#FBEAEA] text-[#B83A3A]",
  export_bank_file: "bg-[#FBF1DE] text-[#8B6A14]",
};

export default function AuditLog() {
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState("");

  useEffect(() => { api.get("/audit").then((r) => setRows(r.data)); }, []);

  const filtered = rows.filter((r) => {
    if (!filter) return true;
    return `${r.action} ${r.resource} ${r.user_email}`.toLowerCase().includes(filter.toLowerCase());
  });

  return (
    <div className="space-y-6" data-testid="audit-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Audit & Activity</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Audit log</h1>
        <p className="text-[#525860] text-sm mt-1">Every mutation across employees, payroll, leave, and exports — with actor and timestamp.</p>
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center gap-3">
          <ScrollText className="w-4 h-4 text-[#525860]" strokeWidth={1.5} />
          <input
            data-testid="audit-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by action, resource, or user…"
            className="flex-1 bg-transparent outline-none text-sm"
          />
          <span className="text-xs text-[#686D76] font-data">{filtered.length} of {rows.length}</span>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Time", "User", "Action", "Resource", "Details"].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.id} className="border-t border-[#E2DFD6]" data-testid={`audit-row-${r.id}`}>
                <td className="py-3 px-4 font-data text-xs text-[#525860]">{new Date(r.ts).toLocaleString()}</td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <User className="w-3.5 h-3.5 text-[#A1A5AB]" strokeWidth={1.5} />
                    <span>{r.user_email}</span>
                    <span className="text-[10px] uppercase tracking-wider text-[#686D76]">{r.user_role}</span>
                  </div>
                </td>
                <td className="py-3 px-4">
                  <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${ACTION_COLORS[r.action] || "bg-[#EBE8E0] text-[#525860]"}`}>
                    {r.action.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="py-3 px-4 font-mono text-xs text-[#525860]">{r.resource}</td>
                <td className="py-3 px-4 text-xs text-[#686D76]">
                  {r.meta && Object.keys(r.meta).length > 0
                    ? Object.entries(r.meta).map(([k, v]) => `${k}: ${v}`).join(" · ")
                    : "—"}
                </td>
              </tr>
            ))}
            {!filtered.length && <tr><td colSpan={5} className="py-12 text-center text-sm text-[#686D76]">No audit events match.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
