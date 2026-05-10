import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import api, { fmtSLE } from "../lib/api";
import { Plus, Trash2, Play, TrendingUp, TrendingDown, Sparkles, Save, Share2, Copy, Check, X, FolderOpen, Trash, BarChart3 } from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";

const blankRule = { name: "", target: "all", department: "", employee_id: "", basic_pct_change: 0, basic_flat_add: 0, allowances_pct_change: 0, allowances_flat_add: 0 };

export default function Simulator() {
  const [employees, setEmployees] = useState([]);
  const [rules, setRules] = useState([{ ...blankRule, name: "Across-the-board 5% raise", basic_pct_change: 5 }]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState([]);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveForm, setSaveForm] = useState({ title: "", description: "", approver_email: "" });
  const [shareUrl, setShareUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const [scenario, setScenario] = useState(null); // currently loaded scenario (with approval state)
  const [params, setParams] = useSearchParams();
  const [compareIds, setCompareIds] = useState(new Set());
  const [comparison, setComparison] = useState(null);

  const loadSaved = useCallback(() => api.get("/payroll/scenarios").then((r) => setSaved(r.data)), []);
  useEffect(() => { api.get("/employees").then((r) => setEmployees(r.data)); loadSaved(); }, [loadSaved]);
  const departments = Array.from(new Set(employees.map((e) => e.department))).sort();

  const addRule = () => setRules([...rules, { ...blankRule, name: `Rule ${rules.length + 1}` }]);
  const removeRule = (i) => setRules(rules.filter((_, idx) => idx !== i));
  const updateRule = (i, patch) => setRules(rules.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  const run = async () => {
    setBusy(true);
    try {
      const payload = rules.map((r) => ({
        ...r,
        basic_pct_change: Number(r.basic_pct_change) || 0,
        basic_flat_add: Number(r.basic_flat_add) || 0,
        allowances_pct_change: Number(r.allowances_pct_change) || 0,
        allowances_flat_add: Number(r.allowances_flat_add) || 0,
      }));
      const { data } = await api.post("/payroll/simulate", { rules: payload });
      setResult(data);
    } catch (e) {
      alert(e?.response?.data?.detail || "Simulation failed");
    } finally { setBusy(false); }
  };

  // Load shared scenario from ?id=
  useEffect(() => {
    const id = params.get("id");
    if (!id) { setScenario(null); return; }
    api.get(`/payroll/scenarios/${id}`).then(({ data }) => {
      setRules(data.scenario.rules.map((r, i) => ({ ...blankRule, ...r, name: r.name || `Rule ${i + 1}` })));
      setResult(data.simulation);
      setScenario(data.scenario);
    }).catch(() => { alert("Scenario not found"); setScenario(null); });
  }, [params]);

  const refreshScenario = useCallback(async () => {
    const id = params.get("id");
    if (!id) return;
    const { data } = await api.get(`/payroll/scenarios/${id}`);
    setScenario(data.scenario);
    setResult(data.simulation);
  }, [params]);

  const decideScenario = async (decision) => {
    const id = params.get("id");
    if (!id) return;
    const notes = decision === "rejected" ? (window.prompt("Optional notes for rejection:") || "") : "";
    try {
      await api.patch(`/payroll/scenarios/${id}/decide`, { decision, notes });
      await refreshScenario();
      loadSaved();
    } catch (e) { alert(e?.response?.data?.detail || "Decision failed"); }
  };

  const applyScenario = async () => {
    const id = params.get("id");
    if (!id) return;
    if (!window.confirm("This will permanently update employee salaries. Continue?")) return;
    try {
      const { data } = await api.post(`/payroll/scenarios/${id}/apply`);
      alert(`Applied: ${data.employees_changed} employee(s) updated.`);
      await refreshScenario();
      loadSaved();
    } catch (e) { alert(e?.response?.data?.detail || "Apply failed"); }
  };

  const saveScenario = async (e) => {
    e.preventDefault();
    if (!saveForm.title.trim()) return;
    const payload = rules.map((r) => ({
      ...r,
      basic_pct_change: Number(r.basic_pct_change) || 0,
      basic_flat_add: Number(r.basic_flat_add) || 0,
      allowances_pct_change: Number(r.allowances_pct_change) || 0,
      allowances_flat_add: Number(r.allowances_flat_add) || 0,
    }));
    try {
      const { data } = await api.post("/payroll/scenarios", { ...saveForm, rules: payload });
      const url = `${window.location.origin}/simulator?id=${data.id}`;
      setShareUrl(url);
      setSaveOpen(false);
      setSaveForm({ title: "", description: "", approver_email: "" });
      loadSaved();
    } catch (err) {
      alert(err?.response?.data?.detail || "Save failed");
    }
  };

  const loadScenario = (id) => { setParams({ id }); };
  const deleteScenario = async (id) => {
    if (!window.confirm("Delete this scenario?")) return;
    await api.delete(`/payroll/scenarios/${id}`);
    loadSaved();
  };
  const copyShare = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = shareUrl;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch { /* ignore */ }
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleCompare = (id) => {
    const next = new Set(compareIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setCompareIds(next);
    setComparison(null);
  };

  const runCompare = async () => {
    const ids = Array.from(compareIds);
    if (ids.length < 2) return;
    try {
      const { data } = await api.post("/payroll/scenarios/compare", { scenario_ids: ids });
      setComparison(data);
      setTimeout(() => document.querySelector("[data-testid=comparison-panel]")?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (e) {
      alert(e?.response?.data?.detail || "Compare failed");
    }
  };

  const positive = (n) => (n ?? 0) >= 0;

  return (
    <div className="space-y-6" data-testid="simulator-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Payroll Engine</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1 flex items-center gap-2">
          What-if simulator <Sparkles className="w-6 h-6 text-[#D1603D]" />
        </h1>
        <p className="text-[#525860] text-sm mt-1 max-w-3xl">Model salary changes, raises, allowances, or one-off bonuses. See current vs projected payroll cost — plus NRA PAYE / NASSIT impact, per-employee deltas, and the annualized employer cost change.</p>
      </div>

      {/* Approval banner — shown when a saved scenario is loaded via ?id */}
      {scenario && (
        <div className={`rounded-lg p-5 border-l-4 ${
          scenario.approval_status === "approved" ? "bg-[#E6F4EC] border-[#2D7A5D]"
          : scenario.approval_status === "rejected" ? "bg-[#FBEAEA] border-[#B83A3A]"
          : scenario.approval_status === "pending" ? "bg-[#FBF1DE] border-[#8B6A14]"
          : "bg-[#F7F6F2] border-[#525860]"
        }`} data-testid="approval-banner">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-0">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Saved scenario · {scenario.approval_status}{scenario.applied ? " · APPLIED" : ""}</div>
              <h2 className="font-heading text-xl font-semibold mt-1">{scenario.title}</h2>
              {scenario.description && <p className="text-sm text-[#525860] mt-1">{scenario.description}</p>}
              <div className="text-xs text-[#686D76] mt-2 space-x-3 font-data">
                <span>Created by {scenario.created_by}</span>
                <span>·</span>
                <span>{new Date(scenario.created_at).toLocaleString()}</span>
                {scenario.approver_email && <><span>·</span><span>Approver: {scenario.approver_email}</span></>}
                {scenario.approved_by && <><span>·</span><span>{scenario.approval_status} by {scenario.approved_by}</span></>}
              </div>
              {scenario.approval_notes && <p className="text-sm italic text-[#525860] mt-2">"{scenario.approval_notes}"</p>}
            </div>
            <div className="flex gap-2 flex-wrap">
              {scenario.approval_status === "pending" && (
                <>
                  <button data-testid="reject-scenario" onClick={() => decideScenario("rejected")} className="inline-flex items-center gap-1.5 text-sm border border-[#B83A3A] text-[#B83A3A] hover:bg-[#FBEAEA] px-3 py-2 rounded-md"><X className="w-3.5 h-3.5" /> Reject</button>
                  <button data-testid="approve-scenario" onClick={() => decideScenario("approved")} className="inline-flex items-center gap-1.5 text-sm bg-[#2D7A5D] hover:bg-[#256449] text-white px-4 py-2 rounded-md"><Check className="w-3.5 h-3.5" /> Approve</button>
                </>
              )}
              {scenario.approval_status === "approved" && !scenario.applied && (
                <button data-testid="apply-scenario" onClick={applyScenario} className="inline-flex items-center gap-1.5 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2 rounded-md font-medium">
                  <Sparkles className="w-3.5 h-3.5" /> Apply changes to employees
                </button>
              )}
              {scenario.applied && (
                <span className="inline-flex items-center gap-1.5 text-sm bg-[#2D7A5D] text-white px-3 py-2 rounded-md">
                  <Check className="w-3.5 h-3.5" /> Applied {scenario.applied_at ? new Date(scenario.applied_at).toLocaleDateString() : ""}
                </span>
              )}
              <button onClick={() => setParams({})} className="inline-flex items-center gap-1.5 text-sm border border-[#E2DFD6] hover:bg-[#F7F6F2] px-3 py-2 rounded-md text-[#525860]"><X className="w-3.5 h-3.5" /> Close</button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h3 className="font-heading text-lg font-semibold">Scenario rules</h3>
          <div className="flex gap-2 flex-wrap">
            {saved.length > 0 && (
              <select
                data-testid="load-scenario"
                onChange={(e) => e.target.value && loadScenario(e.target.value)}
                value=""
                className="text-sm border border-[#E2DFD6] bg-white rounded-md px-3 py-2 cursor-pointer"
              >
                <option value="">Load saved…</option>
                {saved.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
              </select>
            )}
            <button data-testid="add-rule" onClick={addRule} className="inline-flex items-center gap-1.5 text-sm border border-[#E2DFD6] hover:bg-[#F7F6F2] px-3 py-2 rounded-md"><Plus className="w-3.5 h-3.5" /> Add rule</button>
            {result && (
              <button data-testid="save-scenario" onClick={() => setSaveOpen(true)} className="inline-flex items-center gap-1.5 text-sm border border-[#133326] text-[#133326] hover:bg-[#133326] hover:text-white px-3 py-2 rounded-md transition"><Save className="w-3.5 h-3.5" /> Save scenario</button>
            )}
            <button data-testid="run-simulation" onClick={run} disabled={busy || !rules.length} className="inline-flex items-center gap-1.5 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2 rounded-md disabled:opacity-60"><Play className="w-3.5 h-3.5" /> {busy ? "Running…" : "Run simulation"}</button>
          </div>
        </div>
        <div className="space-y-3">
          {rules.map((r, i) => (
            <div key={i} className="border border-[#E2DFD6] rounded-md p-4">
              <div className="flex items-center justify-between mb-3">
                <input value={r.name} onChange={(e) => updateRule(i, { name: e.target.value })} placeholder="Rule label" className="font-heading text-base font-semibold bg-transparent outline-none flex-1" />
                <button onClick={() => removeRule(i)} className="text-[#B83A3A] hover:bg-[#FBEAEA] p-1.5 rounded"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <label className="block text-[10px] uppercase tracking-wider text-[#525860] mb-1">Apply to</label>
                  <select value={r.target} onChange={(e) => updateRule(i, { target: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-2.5 py-2 text-sm">
                    <option value="all">All employees</option>
                    <option value="department">Department</option>
                    <option value="employee">Specific employee</option>
                  </select>
                </div>
                {r.target === "department" && (
                  <div>
                    <label className="block text-[10px] uppercase tracking-wider text-[#525860] mb-1">Department</label>
                    <select value={r.department} onChange={(e) => updateRule(i, { department: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-2.5 py-2 text-sm">
                      <option value="">Select…</option>
                      {departments.map((d) => <option key={d}>{d}</option>)}
                    </select>
                  </div>
                )}
                {r.target === "employee" && (
                  <div>
                    <label className="block text-[10px] uppercase tracking-wider text-[#525860] mb-1">Employee</label>
                    <select value={r.employee_id} onChange={(e) => updateRule(i, { employee_id: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-2.5 py-2 text-sm">
                      <option value="">Select…</option>
                      {employees.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
                    </select>
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mt-3">
                {[
                  ["basic_pct_change", "Basic ±%"],
                  ["basic_flat_add", "Basic SLE flat ±"],
                  ["allowances_pct_change", "Allow. ±%"],
                  ["allowances_flat_add", "Allow. SLE flat ±"],
                ].map(([k, label]) => (
                  <div key={k}>
                    <label className="block text-[10px] uppercase tracking-wider text-[#525860] mb-1">{label}</label>
                    <input type="number" step="0.01" value={r[k]} onChange={(e) => updateRule(i, { [k]: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-2.5 py-2 text-sm font-data" />
                  </div>
                ))}
              </div>
            </div>
          ))}
          {!rules.length && <div className="text-center py-6 text-sm text-[#686D76]">No rules yet — add one to start.</div>}
        </div>
      </div>

      {result && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5" data-testid="sim-results">
            <Card label="Current monthly" sub={`${result.current.employee_count} active employees`} value={fmtSLE(result.current.employer_total_cost)} accent="bg-[#26547C]" />
            <Card label="Projected monthly" sub={`${result.affected_employees_count} affected`} value={fmtSLE(result.projected.employer_total_cost)} accent="bg-[#133326]" />
            <Card
              label="Δ Employer cost"
              sub={`Annualized: ${fmtSLE(result.annualized_delta_employer_cost)}`}
              value={fmtSLE(result.delta.employer_total_cost)}
              accent={positive(result.delta.employer_total_cost) ? "bg-[#D1603D]" : "bg-[#2D7A5D]"}
              icon={positive(result.delta.employer_total_cost) ? TrendingUp : TrendingDown}
            />
          </div>

          <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 min-w-0">
            <h3 className="font-heading text-lg font-semibold mb-4">Department impact</h3>
            <div style={{ width: "100%", height: 280 }}>
              <ResponsiveContainer width="99%" height="99%">
                <BarChart data={result.by_department}>
                  <CartesianGrid stroke="#EBE8E0" vertical={false} />
                  <XAxis dataKey="name" stroke="#686D76" fontSize={11} />
                  <YAxis stroke="#686D76" fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip contentStyle={{ background: "#fff", border: "1px solid #E2DFD6", borderRadius: 8, fontSize: 12 }} formatter={(v) => fmtSLE(v)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="current" fill="#26547C" radius={[4, 4, 0, 0]} name="Current" />
                  <Bar dataKey="projected" fill="#D1603D" radius={[4, 4, 0, 0]} name="Projected" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
            <Mini label="PAYE Δ" value={result.delta.paye} />
            <Mini label="NASSIT employee Δ" value={result.delta.nassit_employee} />
            <Mini label="NASSIT employer Δ" value={result.delta.nassit_employer} />
            <Mini label="Net pay Δ" value={result.delta.net} />
          </div>

          <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-[#E2DFD6]">
              <h3 className="font-heading text-lg font-semibold">Affected employees ({result.employees.length})</h3>
              <p className="text-xs text-[#686D76] mt-0.5">Sorted by largest gross increase</p>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-[#F7F6F2]">
                <tr>{["Employee", "Department", "Current gross", "Projected gross", "Δ Gross", "Δ Net"].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {result.employees.map((e) => (
                  <tr key={e.id} className="border-t border-[#E2DFD6]">
                    <td className="py-3 px-4 font-medium">{e.name}<div className="text-xs text-[#686D76]">{e.job_title}</div></td>
                    <td className="py-3 px-4 text-[#525860]">{e.department}</td>
                    <td className="py-3 px-4 font-data">{fmtSLE(e.current_gross)}</td>
                    <td className="py-3 px-4 font-data">{fmtSLE(e.projected_gross)}</td>
                    <td className={`py-3 px-4 font-data font-semibold ${positive(e.delta_gross) ? "text-[#2D7A5D]" : "text-[#B83A3A]"}`}>{positive(e.delta_gross) ? "+" : ""}{fmtSLE(e.delta_gross)}</td>
                    <td className={`py-3 px-4 font-data font-semibold ${positive(e.delta_net) ? "text-[#2D7A5D]" : "text-[#B83A3A]"}`}>{positive(e.delta_net) ? "+" : ""}{fmtSLE(e.delta_net)}</td>
                  </tr>
                ))}
                {!result.employees.length && <tr><td colSpan={6} className="py-10 text-center text-sm text-[#686D76]">No employees affected by these rules.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Saved scenarios manager */}
      {saved.length > 0 && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="saved-scenarios">
          <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center justify-between flex-wrap gap-3">
            <div>
              <h3 className="font-heading text-lg font-semibold flex items-center gap-2"><FolderOpen className="w-4 h-4" /> Saved scenarios</h3>
              <p className="text-xs text-[#686D76] mt-0.5">Click a row to load. Tick 2+ to compare side-by-side.</p>
            </div>
            {compareIds.size >= 2 && (
              <button data-testid="compare-button" onClick={runCompare} className="inline-flex items-center gap-1.5 text-sm bg-[#26547C] hover:bg-[#1D4363] text-white px-4 py-2 rounded-md">
                <BarChart3 className="w-3.5 h-3.5" /> Compare {compareIds.size} selected
              </button>
            )}
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[#F7F6F2]">
              <tr>{["", "Title", "Status", "Description", "Rules", "Created by", ""].map((h, i) => <th key={`h-${i}-${h}`} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {saved.map((s) => {
                const STATUS_BG = {
                  draft: "bg-[#EBE8E0] text-[#525860]",
                  pending: "bg-[#FBF1DE] text-[#8B6A14]",
                  approved: "bg-[#E6F4EC] text-[#2D7A5D]",
                  rejected: "bg-[#FBEAEA] text-[#B83A3A]",
                };
                const checked = compareIds.has(s.id);
                return (
                  <tr key={s.id} className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB]">
                    <td className="py-3 px-4">
                      <input type="checkbox" data-testid={`compare-${s.id}`} checked={checked} onChange={() => toggleCompare(s.id)} className="w-4 h-4 accent-[#26547C] cursor-pointer" />
                    </td>
                    <td className="py-3 px-4 font-medium cursor-pointer" onClick={() => loadScenario(s.id)}>{s.title}</td>
                    <td className="py-3 px-4">
                      <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STATUS_BG[s.approval_status] || STATUS_BG.draft}`}>
                        {s.approval_status}{s.applied ? " · applied" : ""}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-[#686D76] text-xs max-w-md truncate">{s.description || "—"}</td>
                    <td className="py-3 px-4 font-data text-[#525860]">{s.rules.length}</td>
                    <td className="py-3 px-4 text-xs text-[#686D76]">{s.created_by}</td>
                    <td className="py-3 px-4 text-right">
                      <div className="inline-flex gap-1">
                        <button title="Share" onClick={() => { const url = `${window.location.origin}/simulator?id=${s.id}`; setShareUrl(url); }} className="p-1.5 rounded text-[#26547C] hover:bg-[#E5EEF6]"><Share2 className="w-3.5 h-3.5" /></button>
                        <button title="Load" onClick={() => loadScenario(s.id)} className="p-1.5 rounded text-[#2D7A5D] hover:bg-[#E6F4EC]"><FolderOpen className="w-3.5 h-3.5" /></button>
                        <button title="Delete" onClick={() => deleteScenario(s.id)} className="p-1.5 rounded text-[#B83A3A] hover:bg-[#FBEAEA]"><Trash className="w-3.5 h-3.5" /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Comparison panel */}
      {comparison && (
        <div className="bg-white border-2 border-[#26547C] rounded-lg p-6" data-testid="comparison-panel">
          <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
            <div>
              <div className="text-[10px] uppercase tracking-[0.16em] text-[#26547C]">Scenario comparison</div>
              <h3 className="font-heading text-xl font-semibold mt-1">Ranked by annualized employer cost (cheapest first)</h3>
              <p className="text-xs text-[#686D76] mt-1">Each scenario is freshly re-simulated against the latest employee data.</p>
            </div>
            <button onClick={() => setComparison(null)} className="inline-flex items-center gap-1.5 text-sm border border-[#E2DFD6] hover:bg-[#F7F6F2] px-3 py-2 rounded-md text-[#525860]"><X className="w-3.5 h-3.5" /> Close</button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
            <div className="bg-[#E6F4EC] border border-[#9CC8B1] rounded-md p-3">
              <div className="text-[10px] uppercase tracking-wider text-[#2D7A5D]">💰 Cheapest</div>
              <div className="font-heading text-base font-semibold mt-0.5">{comparison.rows.find((r) => r.scenario.id === comparison.cheapest_id)?.scenario.title}</div>
            </div>
            <div className="bg-[#FBE9DF] border border-[#E8B89C] rounded-md p-3">
              <div className="text-[10px] uppercase tracking-wider text-[#8B3A1C]">🎯 Most targeted</div>
              <div className="font-heading text-base font-semibold mt-0.5">{comparison.rows.find((r) => r.scenario.id === comparison.most_targeted_id)?.scenario.title}</div>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#F7F6F2]">
                <tr>{["#", "Scenario", "Status", "Affected", "Δ Employer/mo", "Annualized", "Δ PAYE", "Δ NASSIT", "Δ Net"].map((h) => (
                  <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {comparison.rows.map((r, i) => {
                  const isWinner = r.scenario.id === comparison.cheapest_id;
                  const isTargeted = r.scenario.id === comparison.most_targeted_id;
                  const positive = r.totals.delta_employer >= 0;
                  return (
                    <tr key={r.scenario.id} className={`border-t border-[#E2DFD6] ${isWinner ? "bg-[#F4FBF5]" : ""}`}>
                      <td className="py-3 px-4 font-data text-[#686D76]">#{i + 1}</td>
                      <td className="py-3 px-4">
                        <div className="font-medium flex items-center gap-1.5">
                          {r.scenario.title}
                          {isWinner && <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#2D7A5D] text-white">Cheapest</span>}
                          {isTargeted && !isWinner && <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#D1603D] text-white">Targeted</span>}
                        </div>
                        <div className="text-xs text-[#686D76]">{r.scenario.rules_count} rule{r.scenario.rules_count !== 1 ? "s" : ""}</div>
                      </td>
                      <td className="py-3 px-4 text-[10px] uppercase tracking-wider text-[#686D76]">{r.scenario.approval_status}</td>
                      <td className="py-3 px-4 font-data">{r.totals.affected}</td>
                      <td className={`py-3 px-4 font-data font-semibold ${positive ? "text-[#B84F2F]" : "text-[#2D7A5D]"}`}>{positive ? "+" : ""}{fmtSLE(r.totals.delta_employer)}</td>
                      <td className={`py-3 px-4 font-data font-semibold ${positive ? "text-[#B84F2F]" : "text-[#2D7A5D]"}`}>{positive ? "+" : ""}{fmtSLE(r.totals.annualized)}</td>
                      <td className="py-3 px-4 font-data text-xs">{fmtSLE(r.totals.paye_delta)}</td>
                      <td className="py-3 px-4 font-data text-xs">{fmtSLE(r.totals.nassit_delta)}</td>
                      <td className="py-3 px-4 font-data text-xs">{fmtSLE(r.totals.net_delta)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Save modal */}
      {saveOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setSaveOpen(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={saveScenario} className="bg-white rounded-lg w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-heading text-xl font-semibold flex items-center gap-2"><Save className="w-5 h-5 text-[#133326]" /> Save scenario</h2>
              <button type="button" onClick={() => setSaveOpen(false)} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Title</label>
                <input data-testid="save-title" required value={saveForm.title} onChange={(e) => setSaveForm({ ...saveForm, title: e.target.value })} placeholder="e.g. 2026 Q2 Engineering raises" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Notes (optional)</label>
                <textarea rows={3} value={saveForm.description} onChange={(e) => setSaveForm({ ...saveForm, description: e.target.value })} placeholder="Why this scenario, who requested it, etc." className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Approver email (optional)</label>
                <input data-testid="save-approver" type="email" value={saveForm.approver_email} onChange={(e) => setSaveForm({ ...saveForm, approver_email: e.target.value })} placeholder="cfo@company.sl — sets status to pending" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
                <div className="text-[11px] text-[#686D76] mt-1">Designating an approver flags the scenario as pending until they approve.</div>
              </div>
              <div className="text-xs text-[#686D76] bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-3">
                <strong>{rules.length} rule{rules.length !== 1 ? "s" : ""}</strong> will be saved. The simulation re-runs against current employee data each time the scenario is loaded.
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" onClick={() => setSaveOpen(false)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="save-submit" type="submit" className="px-4 py-2 text-sm bg-[#133326] hover:bg-[#0F281E] text-white rounded-md">Save & share</button>
            </div>
          </form>
        </div>
      )}

      {/* Share modal */}
      {shareUrl && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setShareUrl("")}>
          <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-lg w-full max-w-md p-6" data-testid="share-modal">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-heading text-xl font-semibold flex items-center gap-2"><Share2 className="w-5 h-5 text-[#26547C]" /> Shareable link</h2>
              <button onClick={() => setShareUrl("")} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-sm text-[#525860] mb-4">Send this URL to anyone with admin access — they'll see the same scenario re-run against the latest employee data.</p>
            <div className="flex gap-2">
              <input readOnly value={shareUrl} onClick={(e) => e.target.select()} className="flex-1 bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-mono text-xs" />
              <button data-testid="copy-share" onClick={copyShare} className={`inline-flex items-center gap-1.5 px-4 py-2 text-sm rounded-md ${copied ? "bg-[#2D7A5D] text-white" : "bg-[#26547C] hover:bg-[#1D4363] text-white"}`}>
                {copied ? <><Check className="w-3.5 h-3.5" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Card({ label, sub, value, accent, icon: Icon }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{label}</div>
          <div className="font-heading text-2xl font-bold mt-2 font-data">{value}</div>
          {sub && <div className="text-xs text-[#686D76] mt-1">{sub}</div>}
        </div>
        <div className={`w-9 h-9 rounded-md ${accent} grid place-items-center`}>
          {Icon ? <Icon className="w-[18px] h-[18px] text-white" strokeWidth={1.5} /> : <span className="text-white text-xs font-bold">SLE</span>}
        </div>
      </div>
    </div>
  );
}

function Mini({ label, value }) {
  const positive = (value ?? 0) >= 0;
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-md p-3">
      <div className="text-[10px] uppercase tracking-wider text-[#525860]">{label}</div>
      <div className={`font-data font-semibold mt-1 ${positive ? "text-[#2D7A5D]" : "text-[#B83A3A]"}`}>
        {positive ? "+" : ""}{fmtSLE(value)}
      </div>
    </div>
  );
}
