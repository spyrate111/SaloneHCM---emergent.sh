import { useEffect, useState } from "react";
import api, { fmtSLE } from "../lib/api";
import { Plus, Trash2, Play, TrendingUp, TrendingDown, Sparkles } from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";

const blankRule = { name: "", target: "all", department: "", employee_id: "", basic_pct_change: 0, basic_flat_add: 0, allowances_pct_change: 0, allowances_flat_add: 0 };

export default function Simulator() {
  const [employees, setEmployees] = useState([]);
  const [rules, setRules] = useState([{ ...blankRule, name: "Across-the-board 5% raise", basic_pct_change: 5 }]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/employees").then((r) => setEmployees(r.data)); }, []);
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

      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-heading text-lg font-semibold">Scenario rules</h3>
          <div className="flex gap-2">
            <button data-testid="add-rule" onClick={addRule} className="inline-flex items-center gap-1.5 text-sm border border-[#E2DFD6] hover:bg-[#F7F6F2] px-3 py-2 rounded-md"><Plus className="w-3.5 h-3.5" /> Add rule</button>
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
