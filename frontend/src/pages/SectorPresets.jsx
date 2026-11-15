import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { useFeatures } from "../lib/features";
import { toast } from "sonner";
import { Briefcase, Pickaxe, Building2, Radio, Layers, Check, Lock, Users } from "lucide-react";

const ICON_MAP = {
  ngo: Briefcase, mining: Pickaxe, banking: Building2, telecom: Radio, general: Layers,
};

const COLOR_MAP = {
  ngo: { bg: "bg-[#E5EEF6]", border: "border-[#26547C]", text: "text-[#26547C]" },
  mining: { bg: "bg-[#FBF1DE]", border: "border-[#8B6A14]", text: "text-[#8B6A14]" },
  banking: { bg: "bg-[#E4F7E7]", border: "border-[#17A035]", text: "text-[#17A035]" },
  telecom: { bg: "bg-[#EBE3F4]", border: "border-[#6A4FA0]", text: "text-[#6A4FA0]" },
  general: { bg: "bg-[#EBE8E0]", border: "border-[#525860]", text: "text-[#525860]" },
};

export default function SectorPresets() {
  const { has } = useFeatures();
  const [catalog, setCatalog] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [selectedPreset, setSelectedPreset] = useState(null);
  const [target, setTarget] = useState({ mode: "single", employee_id: "", department: "" });
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!has("sector_presets")) return;
    const [c, e] = await Promise.all([api.get("/sector-presets/catalog"), api.get("/employees")]);
    setCatalog(c.data.presets);
    setEmployees(e.data);
  }, [has]);

  useEffect(() => { refresh(); }, [refresh]);

  if (!has("sector_presets")) {
    return (
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-10 text-center">
        <Lock className="w-10 h-10 text-[#A1A5AB] mx-auto mb-3" strokeWidth={1.4} />
        <h3 className="font-heading text-xl">Sector Allowance Presets</h3>
        <p className="text-sm text-[#525860] mt-2 max-w-md mx-auto">Available on Professional, Enterprise, and Government tiers.</p>
      </div>
    );
  }

  const apply = async () => {
    if (!selectedPreset) return toast.error("Pick a preset first");
    setBusy(true);
    try {
      if (target.mode === "single") {
        if (!target.employee_id) return toast.error("Pick an employee");
        await api.post(`/sector-presets/apply/${target.employee_id}`, { preset_id: selectedPreset });
        toast.success("Preset applied");
      } else if (target.mode === "department") {
        if (!target.department) return toast.error("Pick a department");
        const { data } = await api.post(`/sector-presets/apply-bulk`, {
          preset_id: selectedPreset, department: target.department,
        });
        toast.success(`Applied to ${data.applied_to} employees`);
      }
      setSelectedPreset(null);
    } catch (e) { toast.error(e?.response?.data?.detail || "Apply failed"); }
    finally { setBusy(false); }
  };

  const departments = Array.from(new Set(employees.map((e) => e.department).filter(Boolean))).sort();

  return (
    <div className="space-y-6" data-testid="sector-presets-page">
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
        <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Compensation</div>
        <h1 className="font-heading text-3xl font-bold mt-1">Sector Allowance Presets</h1>
        <p className="text-sm text-[#525860] mt-1 max-w-2xl">
          One-click industry templates that bundle the standard allowances expected in Sierra Leone for each sector.
          Pick a preset, choose who it applies to, and the next payroll run picks it up automatically.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
        {catalog.map((p) => {
          const Icon = ICON_MAP[p.id] || Layers;
          const c = COLOR_MAP[p.id] || COLOR_MAP.general;
          const isSelected = selectedPreset === p.id;
          return (
            <button
              key={p.id} data-testid={`preset-${p.id}`} onClick={() => setSelectedPreset(p.id)}
              className={`text-left p-4 rounded-md border transition ${isSelected ? `${c.bg} ${c.border} ring-2 ring-offset-1 ring-[#1A1C1E]` : "border-[#E2DFD6] hover:bg-[#F7F6F2]"}`}
            >
              <Icon className={`w-6 h-6 mb-2 ${c.text}`} strokeWidth={1.5} />
              <div className="font-heading font-semibold">{p.label}</div>
              <div className="text-xs text-[#525860] mt-1">{p.description}</div>
              <div className="font-data text-lg font-bold mt-2">{fmtSLE(p.total_monthly_sle)}<span className="text-xs text-[#686D76]">/mo</span></div>
              <div className="text-[10px] text-[#686D76] mt-1">{p.allowances.length} allowances</div>
            </button>
          );
        })}
      </div>

      {selectedPreset && (
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="apply-panel">
          <h2 className="font-heading text-xl mb-3">Apply {catalog.find((p) => p.id === selectedPreset)?.label}</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-[#525860] mb-1">Allowance details</div>
              <ul className="text-sm divide-y divide-[#F1EEE6]">
                {catalog.find((p) => p.id === selectedPreset)?.allowances.map((a) => (
                  <li key={a.label} className="py-1.5 flex justify-between">
                    <span>{a.label}{!a.taxable && <span className="ml-1 text-[9px] uppercase tracking-wider text-[#17A035]">tax-free</span>}</span>
                    <span className="font-data">{fmtSLE(a.amount_sle)}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="space-y-3">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[#525860] mb-1">Apply to</div>
                <div className="flex gap-2 flex-wrap">
                  <button data-testid="mode-single" onClick={() => setTarget({ mode: "single", employee_id: "", department: "" })}
                          className={`text-xs px-3 py-1.5 rounded border ${target.mode === "single" ? "bg-[#0A4A1E] text-white border-[#0A4A1E]" : "border-[#E2DFD6]"}`}>
                    <Users className="w-3.5 h-3.5 inline mr-1" /> One employee
                  </button>
                  <button data-testid="mode-department" onClick={() => setTarget({ mode: "department", employee_id: "", department: "" })}
                          className={`text-xs px-3 py-1.5 rounded border ${target.mode === "department" ? "bg-[#0A4A1E] text-white border-[#0A4A1E]" : "border-[#E2DFD6]"}`}>
                    Whole department
                  </button>
                </div>
              </div>
              {target.mode === "single" && (
                <select data-testid="target-employee" value={target.employee_id}
                        onChange={(e) => setTarget({ ...target, employee_id: e.target.value })}
                        className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                  <option value="">Choose…</option>
                  {employees.map((e) => (
                    <option key={e.id} value={e.id}>{`${e.first_name} ${e.last_name} — ${e.department || "—"}`}</option>
                  ))}
                </select>
              )}
              {target.mode === "department" && (
                <select data-testid="target-department" value={target.department}
                        onChange={(e) => setTarget({ ...target, department: e.target.value })}
                        className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                  <option value="">Choose…</option>
                  {departments.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              )}
              <div className="flex gap-2 pt-2">
                <button onClick={() => setSelectedPreset(null)} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Cancel</button>
                <button data-testid="apply-btn" disabled={busy} onClick={apply} className="text-sm bg-[#0A4A1E] hover:bg-[#063514] text-white px-4 py-2 rounded-md disabled:opacity-60 inline-flex items-center gap-1">
                  <Check className="w-3.5 h-3.5" /> {busy ? "Applying…" : "Apply preset"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
