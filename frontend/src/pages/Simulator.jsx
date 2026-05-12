import { useMemo, useState } from "react";
import { Sparkles } from "lucide-react";
import { useSimulator } from "../hooks/useSimulator";
import ApprovalBanner from "../components/simulator/ApprovalBanner";
import RulesEditor from "../components/simulator/RulesEditor";
import SimulationResults from "../components/simulator/SimulationResults";
import SavedScenariosTable from "../components/simulator/SavedScenariosTable";
import ComparisonPanel from "../components/simulator/ComparisonPanel";
import SaveScenarioModal from "../components/simulator/SaveScenarioModal";
import ShareLinkModal from "../components/simulator/ShareLinkModal";

export default function Simulator() {
  const {
    employees, rules, setRules, result, busy, saved,
    scenario, comparison, compareIds,
    run, saveScenario, deleteScenario, loadScenario, closeScenario,
    decideScenario, applyScenario, toggleCompare, runCompare, setComparison,
  } = useSimulator();

  const [saveOpen, setSaveOpen] = useState(false);
  const [shareUrl, setShareUrl] = useState("");

  const departments = useMemo(
    () => Array.from(new Set(employees.map((e) => e.department))).sort(),
    [employees]
  );

  const handleSave = async (form) => saveScenario(form);

  const handleSavedClosed = (url) => {
    setSaveOpen(false);
    if (url) setShareUrl(url);
  };

  return (
    <div className="space-y-6" data-testid="simulator-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Payroll Engine</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1 flex items-center gap-2">
          What-if simulator <Sparkles className="w-6 h-6 text-[#D1603D]" />
        </h1>
        <p className="text-[#525860] text-sm mt-1 max-w-3xl">
          Model salary changes, raises, allowances, or one-off bonuses. See current vs projected payroll cost — plus NRA PAYE / NASSIT impact, per-employee deltas, and the annualized employer cost change.
        </p>
      </div>

      {scenario && (
        <ApprovalBanner
          scenario={scenario}
          onDecide={decideScenario}
          onApply={applyScenario}
          onClose={closeScenario}
        />
      )}

      <RulesEditor
        rules={rules}
        setRules={setRules}
        employees={employees}
        departments={departments}
        saved={saved}
        loadScenario={loadScenario}
        hasResult={!!result}
        onSaveOpen={() => setSaveOpen(true)}
        onRun={run}
        busy={busy}
      />

      {result && <SimulationResults result={result} />}

      <SavedScenariosTable
        saved={saved}
        compareIds={compareIds}
        toggleCompare={toggleCompare}
        runCompare={runCompare}
        loadScenario={loadScenario}
        deleteScenario={deleteScenario}
        onShare={(id) => setShareUrl(`${window.location.origin}/simulator?id=${id}`)}
      />

      {comparison && (
        <ComparisonPanel comparison={comparison} onClose={() => setComparison(null)} />
      )}

      {saveOpen && (
        <SaveScenarioModal
          rulesCount={rules.length}
          onClose={handleSavedClosed}
          onSave={handleSave}
        />
      )}

      {shareUrl && <ShareLinkModal url={shareUrl} onClose={() => setShareUrl("")} />}
    </div>
  );
}
