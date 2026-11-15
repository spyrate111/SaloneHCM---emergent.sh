import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2, RefreshCw, CheckCircle2, FolderKanban } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";
import { useFeatures } from "../lib/features";

const thisMonth = () => {
  const now = new Date();
  return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0")].join("-");
};
const sle = (value) => value == null ? "—" : `SLE ${Number(value).toLocaleString("en", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const errorMessage = (error, fallback) =>
  typeof error?.response?.data?.detail === "string" ? error.response.data.detail : fallback;

export default function ProjectCosting() {
  const { has } = useFeatures();
  const [period, setPeriod] = useState(thisMonth);
  const [projects, setProjects] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [budgetSet, setBudgetSet] = useState(null);
  const [allocationSet, setAllocationSet] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [projectForm, setProjectForm] = useState({
    code: "", name: "", funder: "", start_period: thisMonth(), end_period: "",
  });
  const [budgetDraft, setBudgetDraft] = useState({});
  const [allocationDraft, setAllocationDraft] = useState([
    { employee_id: "", project_id: "", percentage: "" },
  ]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [p, e, b, a, r] = await Promise.all([
        api.get("/project-costing/projects"),
        api.get("/project-costing/employees"),
        api.get("/project-costing/budget-sets", { params: { period } }),
        api.get("/project-costing/allocation-sets", { params: { period } }),
        api.get("/project-costing/report", { params: { period } }),
      ]);
      setProjects(p.data || []);
      setEmployees(e.data || []);
      setBudgetSet(b.data || null);
      setAllocationSet(a.data || null);
      setReport(r.data || null);
      const nextBudget = {};
      (b.data?.rows || []).forEach((row) => { nextBudget[row.project_id] = String(row.budget_sle); });
      setBudgetDraft(nextBudget);
      setAllocationDraft(
        (a.data?.allocations || []).map((row) => ({
          employee_id: row.employee_id,
          project_id: row.project_id,
          percentage: String(row.percentage),
        })).concat((a.data?.allocations || []).length ? [] : [{ employee_id: "", project_id: "", percentage: "" }]),
      );
    } catch (error) {
      toast.error(errorMessage(error, "Could not load project costing"));
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    if (has("project_costing")) refresh();
  }, [has, refresh]);

  const saveProject = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await api.post("/project-costing/projects", {
        ...projectForm,
        end_period: projectForm.end_period || null,
      });
      toast.success("Project added");
      setProjectForm({ code: "", name: "", funder: "", start_period: period, end_period: "" });
      await refresh();
    } catch (error) {
      toast.error(errorMessage(error, "Could not add project"));
    } finally {
      setSaving(false);
    }
  };

  const toggleProject = async (project) => {
    setSaving(true);
    try {
      await api.patch(`/project-costing/projects/${project.id}`, {
        status: project.status === "active" ? "closed" : "active",
      });
      toast.success(project.status === "active" ? "Project closed" : "Project reopened");
      await refresh();
    } catch (error) {
      toast.error(errorMessage(error, "Could not update project"));
    } finally {
      setSaving(false);
    }
  };

  const saveBudgets = async () => {
    const rows = projects
      .filter((project) => budgetDraft[project.id] !== undefined && budgetDraft[project.id] !== "")
      .map((project) => ({ project_id: project.id, budget_sle: Number(budgetDraft[project.id]) }));
    setSaving(true);
    try {
      await api.post("/project-costing/budget-sets", { period, rows });
      toast.success("Budget draft saved");
      await refresh();
    } catch (error) {
      toast.error(errorMessage(error, "Could not save budget draft"));
    } finally {
      setSaving(false);
    }
  };

  const approveBudgets = async () => {
    if (!budgetSet?.id) return;
    setSaving(true);
    try {
      await api.post(`/project-costing/budget-sets/${budgetSet.id}/approve`);
      toast.success("Budget approved");
      await refresh();
    } catch (error) {
      toast.error(errorMessage(error, "Could not approve budget"));
    } finally {
      setSaving(false);
    }
  };

  const saveAllocations = async () => {
    const allocations = allocationDraft
      .filter((row) => row.employee_id && row.project_id && row.percentage !== "")
      .map((row) => ({
        employee_id: row.employee_id,
        project_id: row.project_id,
        percentage: Number(row.percentage),
      }));
    setSaving(true);
    try {
      await api.post("/project-costing/allocation-sets", { period, allocations });
      toast.success("Allocation draft saved");
      await refresh();
    } catch (error) {
      toast.error(errorMessage(error, "Could not save employee allocations"));
    } finally {
      setSaving(false);
    }
  };

  const approveAllocations = async () => {
    if (!allocationSet?.id) return;
    setSaving(true);
    try {
      await api.post(`/project-costing/allocation-sets/${allocationSet.id}/approve`);
      toast.success("Employee allocations approved");
      await refresh();
    } catch (error) {
      toast.error(errorMessage(error, "Could not approve employee allocations"));
    } finally {
      setSaving(false);
    }
  };

  if (!has("project_costing")) {
    return <div className="p-8 text-sm text-[#525860]">Project costing is not enabled for this organization.</div>;
  }

  const activeProjects = projects.filter((project) => project.status === "active");

  return (
    <div className="min-h-full bg-[#F8F7F2] p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[#0A4A1E]">
            <FolderKanban className="w-5 h-5" />
            <span className="text-[11px] uppercase tracking-[0.16em] font-semibold">Finance · Donor funded teams</span>
          </div>
          <h1 className="font-heading text-2xl mt-2">Project payroll costing</h1>
          <p className="text-sm text-[#686D76] mt-1 max-w-3xl">
            Compare approved project budgets with payroll gross plus employer NASSIT. All amounts are SLE.
            Approved budgets and employee allocations are snapshotted into each payroll run.
          </p>
        </div>
        <div className="flex items-end gap-2">
          <label className="text-[10px] uppercase tracking-wider text-[#525860]">
            Payroll period
            <input aria-label="Payroll period" type="month" value={period}
              onChange={(event) => setPeriod(event.target.value)}
              className="mt-1 block rounded-md border border-[#D9D6CC] bg-white px-3 py-2 text-sm" />
          </label>
          <button type="button" onClick={refresh} disabled={loading}
            className="rounded-md border border-[#D9D6CC] bg-white p-2 text-[#26547C] disabled:opacity-50"
            aria-label="Refresh project costing">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      {report && (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric title="Approved project budget" value={sle(report.totals.approved_budget_sle)} />
          <Metric title="Employer payroll cost" value={sle(report.totals.actual_employer_cost_sle)} />
          <Metric title="Variance" value={sle(report.totals.variance_sle)} />
          <Metric title="Unallocated payroll" value={report.totals.unallocated_employer_cost_sle == null
            ? "—" : `${sle(report.totals.unallocated_employer_cost_sle)} · ${report.totals.unallocated_headcount || 0} staff`} />
        </section>
      )}

      <section className="rounded-lg border border-[#E2DFD6] bg-white p-4 md:p-6">
        <SectionHeading title="Projects" subtitle="Create SLE project cost centres and keep historical labels intact in approved workpapers." />
        <form onSubmit={saveProject} className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <Input label="Project code" required value={projectForm.code}
            onChange={(value) => setProjectForm({ ...projectForm, code: value })} />
          <Input label="Project name" required value={projectForm.name}
            onChange={(value) => setProjectForm({ ...projectForm, name: value })} />
          <Input label="Funder / donor" value={projectForm.funder}
            onChange={(value) => setProjectForm({ ...projectForm, funder: value })} />
          <Input label="Start month" required type="month" value={projectForm.start_period}
            onChange={(value) => setProjectForm({ ...projectForm, start_period: value })} />
          <Input label="End month" type="month" value={projectForm.end_period}
            onChange={(value) => setProjectForm({ ...projectForm, end_period: value })} />
          <button disabled={saving} className="self-end inline-flex items-center justify-center gap-2 rounded-md bg-[#0A4A1E] px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
            <Plus className="h-4 w-4" /> Add project
          </button>
        </form>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[620px] text-sm">
            <thead><tr className="border-b border-[#E2DFD6] text-left text-[10px] uppercase tracking-wider text-[#686D76]">
              <th className="py-2">Code</th><th>Name</th><th>Funder</th><th>Period</th><th>Status</th><th />
            </tr></thead>
            <tbody>
              {projects.map((project) => (
                <tr key={project.id} className="border-b border-[#F1EEE6]">
                  <td className="py-2 font-mono">{project.code}</td>
                  <td>{project.name}</td><td>{project.funder || "—"}</td>
                  <td>{project.start_period}{project.end_period ? ` to ${project.end_period}` : " onward"}</td>
                  <td><Status status={project.status} /></td>
                  <td className="text-right">
                    <button type="button" disabled={saving} onClick={() => toggleProject(project)}
                      className="text-xs text-[#26547C] underline disabled:opacity-50">
                      {project.status === "active" ? "Close" : "Reopen"}
                    </button>
                  </td>
                </tr>
              ))}
              {!projects.length && <tr><td colSpan="6" className="py-5 text-center text-sm text-[#686D76]">No projects yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-lg border border-[#E2DFD6] bg-white p-4 md:p-6">
          <SectionHeading title="Monthly project budgets" subtitle="Save a draft, then ask another HR or payroll user to approve it." status={budgetSet?.status} revision={budgetSet?.revision} />
          <div className="mt-4 space-y-2">
            {activeProjects.map((project) => (
              <label key={project.id} className="grid grid-cols-[1fr_170px] items-center gap-3 border-b border-[#F1EEE6] py-2 text-sm">
                <span><span className="font-mono text-xs text-[#686D76]">{project.code}</span> · {project.name}</span>
                <input type="number" min="0" step="0.01" value={budgetDraft[project.id] ?? ""}
                  onChange={(event) => setBudgetDraft({ ...budgetDraft, [project.id]: event.target.value })}
                  aria-label={`Budget for ${project.name} in SLE`}
                  className="rounded-md border border-[#D9D6CC] px-3 py-2 text-right font-mono text-sm" />
              </label>
            ))}
            {!activeProjects.length && <p className="text-sm text-[#686D76]">Add an active project before setting its budget.</p>}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <ActionButton disabled={saving || !activeProjects.length} onClick={saveBudgets}>Save budget draft</ActionButton>
            {budgetSet?.status === "draft" && <ActionButton secondary disabled={saving} onClick={approveBudgets}>Approve as checker</ActionButton>}
          </div>
        </section>

        <section className="rounded-lg border border-[#E2DFD6] bg-white p-4 md:p-6">
          <SectionHeading title="Employee project allocations" subtitle="Percentages apply to gross pay and employer NASSIT; any remaining share stays unallocated." status={allocationSet?.status} revision={allocationSet?.revision} />
          <div className="mt-4 space-y-2">
            {allocationDraft.map((row, index) => (
              <div key={index} className="grid gap-2 border-b border-[#F1EEE6] pb-3 sm:grid-cols-[1.3fr_1fr_105px_40px] sm:items-end">
                <label className="text-[10px] uppercase tracking-wider text-[#686D76]">
                  Employee
                  <select value={row.employee_id} onChange={(event) => setAllocationDraft(allocationDraft.map((item, i) => i === index ? { ...item, employee_id: event.target.value } : item))}
                    className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-2 py-2 text-sm normal-case tracking-normal">
                    <option value="">Select employee</option>
                    {employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}{employee.employee_number ? ` · ${employee.employee_number}` : ""}</option>)}
                  </select>
                </label>
                <label className="text-[10px] uppercase tracking-wider text-[#686D76]">
                  Project
                  <select value={row.project_id} onChange={(event) => setAllocationDraft(allocationDraft.map((item, i) => i === index ? { ...item, project_id: event.target.value } : item))}
                    className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-2 py-2 text-sm normal-case tracking-normal">
                    <option value="">Select project</option>
                    {activeProjects.map((project) => <option key={project.id} value={project.id}>{project.code} · {project.name}</option>)}
                  </select>
                </label>
                <label className="text-[10px] uppercase tracking-wider text-[#686D76]">
                  Share %
                  <input type="number" min="0.01" max="100" step="0.01" value={row.percentage}
                    onChange={(event) => setAllocationDraft(allocationDraft.map((item, i) => i === index ? { ...item, percentage: event.target.value } : item))}
                    className="mt-1 block w-full rounded-md border border-[#D9D6CC] px-2 py-2 text-right font-mono text-sm" />
                </label>
                <button type="button" aria-label="Remove allocation row" onClick={() => setAllocationDraft(allocationDraft.filter((_, i) => i !== index))}
                  className="mb-1 rounded-md p-2 text-[#686D76] hover:bg-[#F8F7F2]"><Trash2 className="h-4 w-4" /></button>
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <ActionButton secondary disabled={saving} onClick={() => setAllocationDraft([...allocationDraft, { employee_id: "", project_id: "", percentage: "" }])}>
              <Plus className="h-4 w-4" /> Add allocation
            </ActionButton>
            <ActionButton disabled={saving} onClick={saveAllocations}>Save allocation draft</ActionButton>
            {allocationSet?.status === "draft" && <ActionButton secondary disabled={saving} onClick={approveAllocations}>Approve as checker</ActionButton>}
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-[#E2DFD6] bg-white p-4 md:p-6">
        <SectionHeading title="Budget versus actual" subtitle={report?.actuals_available
          ? `Payroll run ${report.payroll_run_id} · actuals are from the completed run`
          : "No completed payroll run exists for this period yet."} />
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead><tr className="border-b border-[#E2DFD6] text-left text-[10px] uppercase tracking-wider text-[#686D76]">
              <th className="py-2">Project</th><th>Funder</th><th>Staff</th><th>Approved budget</th><th>Gross</th><th>Employer NASSIT</th><th>Total employer cost</th><th>Variance</th>
            </tr></thead>
            <tbody>
              {(report?.by_project || []).map((row) => (
                <tr key={row.project_id} className="border-b border-[#F1EEE6]">
                  <td className="py-2"><span className="font-mono text-xs">{row.project_code}</span> · {row.project_name}</td>
                  <td>{row.funder || "—"}</td><td>{row.employees}</td>
                  <td className="font-mono">{sle(row.budget_sle)}</td><td className="font-mono">{report.actuals_available ? sle(row.gross_sle) : "—"}</td>
                  <td className="font-mono">{report.actuals_available ? sle(row.employer_nassit_sle) : "—"}</td>
                  <td className="font-mono">{report.actuals_available ? sle(row.employer_cost_sle) : "—"}</td>
                  <td className="font-mono">{report.actuals_available ? sle(row.variance_sle) : "—"}</td>
                </tr>
              ))}
              {report?.actuals_available && (
                <tr className="font-semibold">
                  <td className="py-3" colSpan="6">Unallocated payroll cost</td>
                  <td className="font-mono">{sle(report.totals.unallocated_employer_cost_sle)}</td><td />
                </tr>
              )}
              {!report?.by_project?.length && <tr><td colSpan="8" className="py-5 text-center text-sm text-[#686D76]">No approved project budget or allocation is recorded for this period.</td></tr>}
            </tbody>
          </table>
        </div>
        {report?.actuals_available && report.totals.unallocated_headcount > 0 && (
          <p className="mt-3 text-xs text-[#8B6A14]">
            {report.totals.unallocated_headcount} employee(s) have an unallocated share. Review the approved allocation set before the next payroll run.
          </p>
        )}
      </section>
    </div>
  );
}

function Metric({ title, value }) {
  return <div className="rounded-lg border border-[#E2DFD6] bg-white p-4">
    <div className="text-[10px] uppercase tracking-wider text-[#686D76]">{title}</div>
    <div className="mt-2 font-heading text-xl">{value}</div>
  </div>;
}

function SectionHeading({ title, subtitle, status, revision }) {
  return <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
    <div><h2 className="font-heading text-lg">{title}</h2><p className="mt-1 text-xs text-[#686D76]">{subtitle}</p></div>
    {status && <Status status={status} revision={revision} />}
  </div>;
}

function Status({ status, revision }) {
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10px] uppercase tracking-wider ${status === "approved" || status === "active" ? "bg-[#E4F7E7] text-[#0A4A1E]" : "bg-[#F1EEE6] text-[#686D76]"}`}>
    {status === "approved" && <CheckCircle2 className="h-3 w-3" />}
    {status}{revision ? ` · v${revision}` : ""}
  </span>;
}

function Input({ label, value, onChange, required, type = "text" }) {
  return <label className="text-[10px] uppercase tracking-wider text-[#686D76]">
    {label}
    <input required={required} type={type} value={value}
      onChange={(event) => onChange(event.target.value)}
      className="mt-1 block w-full rounded-md border border-[#D9D6CC] bg-white px-3 py-2 text-sm normal-case tracking-normal" />
  </label>;
}

function ActionButton({ children, onClick, disabled, secondary = false }) {
  return <button type="button" onClick={onClick} disabled={disabled}
    className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 ${secondary ? "border border-[#D9D6CC] bg-white text-[#26547C]" : "bg-[#0A4A1E] text-white"}`}>
    {children}
  </button>;
}
