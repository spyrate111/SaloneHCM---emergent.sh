import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { toast } from "sonner";

export const blankRule = {
  name: "", target: "all", department: "", employee_id: "",
  basic_pct_change: 0, basic_flat_add: 0, allowances_pct_change: 0, allowances_flat_add: 0,
};
export const newRuleId = () => `r_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

const sanitizeRules = (rules) => rules.map((r) => {
  const { _id, ...clean } = r;
  return {
    ...clean,
    basic_pct_change: Number(clean.basic_pct_change) || 0,
    basic_flat_add: Number(clean.basic_flat_add) || 0,
    allowances_pct_change: Number(clean.allowances_pct_change) || 0,
    allowances_flat_add: Number(clean.allowances_flat_add) || 0,
  };
});

/**
 * useSimulator — state + API actions for the What-if Simulator page.
 */
export function useSimulator() {
  const [employees, setEmployees] = useState([]);
  const [rules, setRules] = useState([{ ...blankRule, _id: newRuleId(), name: "Across-the-board 5% raise", basic_pct_change: 5 }]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState([]);
  const [scenario, setScenario] = useState(null);
  const [params, setParams] = useSearchParams();
  const [compareIds, setCompareIds] = useState(new Set());
  const [comparison, setComparison] = useState(null);

  const loadSaved = useCallback(() => api.get("/payroll/scenarios").then((r) => setSaved(r.data)), []);

  useEffect(() => {
    api.get("/employees").then((r) => setEmployees(r.data));
    loadSaved();
  }, [loadSaved]);

  // Load shared scenario via ?id=
  useEffect(() => {
    const id = params.get("id");
    if (!id) { setScenario(null); return; }
    api.get(`/payroll/scenarios/${id}`).then(({ data }) => {
      setRules(data.scenario.rules.map((r, i) => ({ ...blankRule, ...r, _id: newRuleId(), name: r.name || `Rule ${i + 1}` })));
      setResult(data.simulation);
      setScenario(data.scenario);
    }).catch(() => {
      toast.error("Scenario not found");
      setScenario(null);
    });
  }, [params]);

  const refreshScenario = useCallback(async () => {
    const id = params.get("id");
    if (!id) return;
    const { data } = await api.get(`/payroll/scenarios/${id}`);
    setScenario(data.scenario);
    setResult(data.simulation);
  }, [params]);

  const run = useCallback(async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/payroll/simulate", { rules: sanitizeRules(rules) });
      setResult(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Simulation failed");
    } finally { setBusy(false); }
  }, [rules]);

  const decideScenario = useCallback(async (decision) => {
    const id = params.get("id");
    if (!id) return;
    const notes = decision === "rejected" ? (window.prompt("Optional notes for rejection:") || "") : "";
    try {
      await api.patch(`/payroll/scenarios/${id}/decide`, { decision, notes });
      await refreshScenario();
      loadSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Decision failed"); }
  }, [params, refreshScenario, loadSaved]);

  const applyScenario = useCallback(async () => {
    const id = params.get("id");
    if (!id) return;
    if (!window.confirm("This will permanently update employee salaries. Continue?")) return;
    try {
      const { data } = await api.post(`/payroll/scenarios/${id}/apply`);
      toast.success(`Applied — ${data.employees_changed} employee(s) updated`);
      await refreshScenario();
      loadSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Apply failed"); }
  }, [params, refreshScenario, loadSaved]);

  const saveScenario = useCallback(async (form) => {
    try {
      const { data } = await api.post("/payroll/scenarios", { ...form, rules: sanitizeRules(rules) });
      loadSaved();
      return `${window.location.origin}/simulator?id=${data.id}`;
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Save failed");
      return null;
    }
  }, [rules, loadSaved]);

  const deleteScenario = useCallback(async (id) => {
    if (!window.confirm("Delete this scenario?")) return;
    await api.delete(`/payroll/scenarios/${id}`);
    loadSaved();
  }, [loadSaved]);

  const runCompare = useCallback(async () => {
    const ids = Array.from(compareIds);
    if (ids.length < 2) return;
    try {
      const { data } = await api.post("/payroll/scenarios/compare", { scenario_ids: ids });
      setComparison(data);
      setTimeout(() => document.querySelector("[data-testid=comparison-panel]")?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (e) { toast.error(e?.response?.data?.detail || "Compare failed"); }
  }, [compareIds]);

  const toggleCompare = useCallback((id) => {
    setCompareIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
    setComparison(null);
  }, []);

  const loadScenario = useCallback((id) => setParams({ id }), [setParams]);
  const closeScenario = useCallback(() => setParams({}), [setParams]);

  return {
    employees, rules, setRules, result, busy, saved,
    scenario, comparison, compareIds,
    run, saveScenario, deleteScenario, loadScenario, closeScenario,
    decideScenario, applyScenario, toggleCompare, runCompare, setComparison,
  };
}
