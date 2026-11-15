import { Plus, Trash2, Play, Save } from "lucide-react";
import { blankRule, newRuleId } from "../../hooks/useSimulator";

const NUMERIC_FIELDS = [
  ["basic_pct_change", "Basic ±%"],
  ["basic_flat_add", "Basic SLE flat ±"],
  ["allowances_pct_change", "Allow. ±%"],
  ["allowances_flat_add", "Allow. SLE flat ±"],
];

export default function RulesEditor({
  rules, setRules, employees, departments,
  saved, loadScenario, hasResult, onSaveOpen, onRun, busy,
}) {
  const addRule = () => setRules([...rules, { ...blankRule, _id: newRuleId(), name: `Rule ${rules.length + 1}` }]);
  const removeRule = (i) => setRules(rules.filter((_, idx) => idx !== i));
  const updateRule = (i, patch) => setRules(rules.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  return (
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
          <button data-testid="add-rule" onClick={addRule} className="inline-flex items-center gap-1.5 text-sm border border-[#E2DFD6] hover:bg-[#F7F6F2] px-3 py-2 rounded-md">
            <Plus className="w-3.5 h-3.5" /> Add rule
          </button>
          {hasResult && (
            <button data-testid="save-scenario" onClick={onSaveOpen} className="inline-flex items-center gap-1.5 text-sm border border-[#0A4A1E] text-[#0A4A1E] hover:bg-[#0A4A1E] hover:text-white px-3 py-2 rounded-md transition">
              <Save className="w-3.5 h-3.5" /> Save scenario
            </button>
          )}
          <button data-testid="run-simulation" onClick={onRun} disabled={busy || !rules.length} className="inline-flex items-center gap-1.5 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2 rounded-md disabled:opacity-60">
            <Play className="w-3.5 h-3.5" /> {busy ? "Running…" : "Run simulation"}
          </button>
        </div>
      </div>
      <div className="space-y-3">
        {rules.map((r, i) => (
          <div key={r._id} className="border border-[#E2DFD6] rounded-md p-4">
            <div className="flex items-center justify-between mb-3">
              <input value={r.name} onChange={(e) => updateRule(i, { name: e.target.value })} placeholder="Rule label" className="font-heading text-base font-semibold bg-transparent outline-none flex-1" />
              <button onClick={() => removeRule(i)} className="text-[#3A7CB8] hover:bg-[#E9F2FB] p-1.5 rounded"><Trash2 className="w-3.5 h-3.5" /></button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
              <Select label="Apply to" value={r.target} onChange={(v) => updateRule(i, { target: v })}>
                <option value="all">All employees</option>
                <option value="department">Department</option>
                <option value="employee">Specific employee</option>
              </Select>
              {r.target === "department" && (
                <Select label="Department" value={r.department} onChange={(v) => updateRule(i, { department: v })}>
                  <option value="">Select…</option>
                  {departments.map((d) => <option key={d}>{d}</option>)}
                </Select>
              )}
              {r.target === "employee" && (
                <Select label="Employee" value={r.employee_id} onChange={(v) => updateRule(i, { employee_id: v })}>
                  <option value="">Select…</option>
                  {employees.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
                </Select>
              )}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mt-3">
              {NUMERIC_FIELDS.map(([k, label]) => (
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
  );
}

function Select({ label, value, onChange, children }) {
  return (
    <div>
      <label className="block text-[10px] uppercase tracking-wider text-[#525860] mb-1">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="w-full bg-white border border-[#E2DFD6] rounded-md px-2.5 py-2 text-sm">
        {children}
      </select>
    </div>
  );
}
