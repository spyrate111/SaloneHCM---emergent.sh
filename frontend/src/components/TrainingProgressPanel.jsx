/**
 * Desktop training-video completion matrix — shown on the Talent → Learning
 * tab for admins/supervisors (backend 403s everyone else → panel hides).
 */
import { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { GraduationCap, CheckCircle2, Minus } from "lucide-react";

export default function TrainingProgressPanel() {
  const [data, setData] = useState(null);
  const [branches, setBranches] = useState([]);
  const [branchId, setBranchId] = useState("");

  useEffect(() => {
    api.get("/training-progress/team", { params: branchId ? { branch_id: branchId } : {} })
      .then((r) => setData(r.data))
      .catch(() => setData(null));
  }, [branchId]);

  useEffect(() => {
    api.get("/branches").then((r) => setBranches(r.data || [])).catch(() => {});
  }, []);

  const rows = useMemo(() => (data?.rows || []).filter((r) => r.has_account), [data]);
  if (!data) return null;

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="training-progress-panel">
      <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center gap-3 flex-wrap">
        <h3 className="font-heading text-lg font-semibold flex items-center gap-2">
          <GraduationCap className="w-4 h-4 text-[#0A4A1E]" /> Video training progress
        </h3>
        <span className="text-[11px] text-[#525860]">{data.total} walkthrough videos · {rows.length} staff with accounts</span>
        <select value={branchId} onChange={(e) => setBranchId(e.target.value)}
          className="ml-auto bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
          data-testid="training-progress-branch-filter">
          <option value="">All branches</option>
          {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="training-progress-table">
          <thead className="bg-[#F7F6F2]">
            <tr>
              <th className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">Employee</th>
              <th className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">Branch</th>
              <th className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">Progress</th>
              {(data.videos || []).map((v, i) => (
                <th key={v.base_slug} title={v.title}
                    className="text-center text-[10px] uppercase tracking-wider text-[#525860] py-3 px-2 font-medium cursor-help">
                  V{i + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const done = new Set(r.completed);
              const pct = data.total ? Math.round((r.completed_count / data.total) * 100) : 0;
              return (
                <tr key={r.employee_id} className="border-t border-[#E2DFD6]" data-testid={`training-progress-row-${r.employee_id}`}>
                  <td className="py-2.5 px-4 font-medium whitespace-nowrap">{r.name}</td>
                  <td className="py-2.5 px-4 text-[#525860] whitespace-nowrap">{r.branch_name || "—"}</td>
                  <td className="py-2.5 px-4 min-w-[140px]">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 rounded-full bg-[#F1EEE6] overflow-hidden">
                        <div className={`h-full rounded-full ${pct === 100 ? "bg-[#17A035]" : "bg-[#0A4A1E]"}`} style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-[11px] font-data text-[#525860] whitespace-nowrap">{r.completed_count}/{data.total}</span>
                    </div>
                  </td>
                  {(data.videos || []).map((v) => (
                    <td key={v.base_slug} className="py-2.5 px-2 text-center" title={v.title}>
                      {done.has(v.base_slug)
                        ? <CheckCircle2 className="w-4 h-4 text-[#17A035] inline" data-testid={`tp-done-${r.employee_id}-${v.base_slug}`} />
                        : <Minus className="w-4 h-4 text-[#D9D6CC] inline" />}
                    </td>
                  ))}
                </tr>
              );
            })}
            {!rows.length && (
              <tr><td colSpan={3 + (data.videos || []).length} className="py-8 text-center text-sm text-[#686D76]">
                No staff with app accounts in this scope.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
