import { fmtSLE } from "../lib/api";
import { Wand2, Check, X, AlertCircle, FlaskConical, TrendingUp, TrendingDown } from "lucide-react";

const STEP_LABELS = {
  leave_decision: "Leave decision",
  payroll_run: "Run payroll",
  attendance_log: "Log attendance",
  leave_create: "Create leave request",
  payroll_simulate: "Simulate payroll scenario",
  scenario_apply: "Apply scenario",
};

export function SimResultCard({ sim, title }) {
  const positive = (sim.delta?.employer_total_cost ?? 0) >= 0;
  const TrendIcon = positive ? TrendingUp : TrendingDown;
  return (
    <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-4 mt-2">
      <div className="flex items-center gap-2 mb-3">
        <FlaskConical className="w-4 h-4 text-[#D1603D]" strokeWidth={1.5} />
        <span className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Simulation result</span>
        {title && <span className="text-xs text-[#1A1C1E] font-medium">· {title}</span>}
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <Stat label="Current/mo" value={fmtSLE(sim.current.employer_total_cost)} />
        <Stat label="Projected/mo" value={fmtSLE(sim.projected.employer_total_cost)} />
        <div className={`rounded p-2 ${positive ? "bg-[#FBE9DF]" : "bg-[#E4F7E7]"}`}>
          <div className="text-[10px] uppercase tracking-wider text-[#525860] inline-flex items-center gap-1">
            <TrendIcon className="w-3 h-3" /> Δ employer
          </div>
          <div className={`font-data font-semibold ${positive ? "text-[#B84F2F]" : "text-[#17A035]"}`}>
            {positive ? "+" : ""}{fmtSLE(sim.delta.employer_total_cost)}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
        <div className="bg-white border border-[#E2DFD6] rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-[#525860]">Annualized</div>
          <div className={`font-data font-semibold ${positive ? "text-[#B84F2F]" : "text-[#17A035]"}`}>
            {positive ? "+" : ""}{fmtSLE(sim.annualized_delta_employer_cost)}/yr
          </div>
        </div>
        <Stat label="Affected" value={`${sim.affected_employees_count} employees`} />
      </div>
      {sim.employees?.length > 0 && (
        <details className="mt-3">
          <summary className="text-xs text-[#525860] cursor-pointer hover:text-[#1A1C1E]">View top 5 affected</summary>
          <div className="mt-2 space-y-1 text-xs font-data">
            {sim.employees.slice(0, 5).map((e) => (
              <div key={e.id} className="flex justify-between">
                <span>{e.name} <span className="text-[#686D76]">· {e.department}</span></span>
                <span className={e.delta_gross >= 0 ? "text-[#17A035]" : "text-[#3A7CB8]"}>
                  {e.delta_gross >= 0 ? "+" : ""}{fmtSLE(e.delta_gross)}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded p-2">
      <div className="text-[10px] uppercase tracking-wider text-[#525860]">{label}</div>
      <div className="font-data font-semibold text-[#1A1C1E]">{value}</div>
    </div>
  );
}

function StepRow({ step, index, result }) {
  const status = result?.status;
  return (
    <li className={`text-sm border rounded-md px-3 py-2 ${
      status === "ok" ? "border-[#90D8A0] bg-[#E4F7E7]"
      : status === "error" ? "border-[#A1C3E1] bg-[#E9F2FB]"
      : "border-[#E2DFD6] bg-[#F7F6F2]"
    }`}>
      <div className="flex items-start gap-2">
        <span className="font-data text-xs text-[#525860] mt-0.5">{index + 1}.</span>
        <div className="flex-1">
          <div className="font-medium text-[#1A1C1E]">{STEP_LABELS[step.type] || step.type}</div>
          <pre className="font-mono text-[11px] text-[#525860] mt-0.5 overflow-x-auto">
            {JSON.stringify({ ...step, type: undefined }, null, 0).slice(1, -1) || "—"}
          </pre>
          {result && (
            <div className={`text-xs mt-1 ${status === "ok" ? "text-[#17A035]" : status === "error" ? "text-[#3A7CB8]" : "text-[#525860]"}`}>
              {status === "ok" ? "✓ " : status === "error" ? "✗ " : "• "}{result.detail}
            </div>
          )}
          {result?.simulation && <SimResultCard sim={result.simulation} title={step.title} />}
        </div>
      </div>
    </li>
  );
}

export default function PlanCard({ plan, onConfirm, onCancel, busy, results }) {
  const finished = results?.length > 0;
  return (
    <div className="bg-white border-2 border-[#D1603D] rounded-lg p-5 my-2 shadow-sm" data-testid="action-plan">
      <div className="flex items-start gap-3 mb-3">
        <div className="w-8 h-8 rounded-md bg-[#D1603D] grid place-items-center shrink-0">
          <Wand2 className="w-4 h-4 text-white" strokeWidth={1.5} />
        </div>
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#D1603D]">Proposed action plan</div>
          <h4 className="font-heading text-lg font-semibold text-[#1A1C1E] mt-0.5">{plan.title || "Action plan"}</h4>
          {plan.rationale && <p className="text-sm text-[#525860] mt-1">{plan.rationale}</p>}
        </div>
      </div>
      <ol className="space-y-2 mt-3">
        {plan.steps.map((step, i) => (
          <StepRow key={`${step.type}-${i}`} step={step} index={i} result={results?.[i]} />
        ))}
      </ol>
      {!finished ? (
        <div className="flex items-center justify-between gap-3 mt-4 pt-3 border-t border-[#F1EEE6]">
          <div className="flex items-center gap-1.5 text-xs text-[#8B6A14]">
            <AlertCircle className="w-3.5 h-3.5" />
            Review carefully — every step will be audit-logged.
          </div>
          <div className="flex gap-2">
            <button
              data-testid="plan-cancel"
              onClick={onCancel}
              disabled={busy}
              className="inline-flex items-center gap-1 px-3 py-2 text-sm border border-[#E2DFD6] rounded-md hover:bg-[#F7F6F2] disabled:opacity-60"
            >
              <X className="w-3.5 h-3.5" /> Cancel
            </button>
            <button
              data-testid="plan-confirm"
              onClick={onConfirm}
              disabled={busy}
              className="inline-flex items-center gap-1 px-4 py-2 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white rounded-md disabled:opacity-60"
            >
              <Check className="w-3.5 h-3.5" /> {busy ? "Executing…" : "Confirm & execute"}
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4 pt-3 border-t border-[#F1EEE6] text-xs text-[#525860]">
          ✓ Plan executed — {results.filter((r) => r.status === "ok").length} of {results.length} steps succeeded.
        </div>
      )}
    </div>
  );
}
