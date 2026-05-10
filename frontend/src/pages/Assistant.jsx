import { useState, useRef, useEffect } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Sparkles, Send, Database, Wand2, Check, X, AlertCircle, FlaskConical, TrendingUp, TrendingDown } from "lucide-react";

import { fmtSLE } from "../lib/api";

const GENERAL_SUGGESTIONS = [
  "How is PAYE calculated in Sierra Leone?",
  "What are the NASSIT contribution rates?",
  "How many days of annual leave under Employment Act 2023?",
  "Explain my payslip — basic SLE 5,000 + allowances SLE 800.",
];

const CONTEXT_SUGGESTIONS = [
  "Show me payroll anomalies in our last run.",
  "Which department has the highest leave usage?",
  "Summarize audit activity in the last 7 days.",
  "Who are our top 3 highest-paid employees by gross?",
];

const ACTION_SUGGESTIONS = [
  "Approve all pending leave requests.",
  "Run payroll for next month.",
  "Reject any leave request longer than 14 days.",
  "Simulate a 10% raise for the Engineering department.",
  "What if we add a SLE 200 transport allowance for everyone?",
];

const STEP_LABELS = {
  leave_decision: "Leave decision",
  payroll_run: "Run payroll",
  attendance_log: "Log attendance",
  leave_create: "Create leave request",
  payroll_simulate: "Simulate payroll scenario",
};

function SimResultCard({ sim, title }) {
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
        <div className="bg-white border border-[#E2DFD6] rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-[#525860]">Current/mo</div>
          <div className="font-data font-semibold text-[#1A1C1E]">{fmtSLE(sim.current.employer_total_cost)}</div>
        </div>
        <div className="bg-white border border-[#E2DFD6] rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-[#525860]">Projected/mo</div>
          <div className="font-data font-semibold text-[#1A1C1E]">{fmtSLE(sim.projected.employer_total_cost)}</div>
        </div>
        <div className={`rounded p-2 ${positive ? "bg-[#FBE9DF]" : "bg-[#E6F4EC]"}`}>
          <div className="text-[10px] uppercase tracking-wider text-[#525860] inline-flex items-center gap-1">
            <TrendIcon className="w-3 h-3" /> Δ employer
          </div>
          <div className={`font-data font-semibold ${positive ? "text-[#B84F2F]" : "text-[#2D7A5D]"}`}>
            {positive ? "+" : ""}{fmtSLE(sim.delta.employer_total_cost)}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
        <div className="bg-white border border-[#E2DFD6] rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-[#525860]">Annualized</div>
          <div className={`font-data font-semibold ${positive ? "text-[#B84F2F]" : "text-[#2D7A5D]"}`}>
            {positive ? "+" : ""}{fmtSLE(sim.annualized_delta_employer_cost)}/yr
          </div>
        </div>
        <div className="bg-white border border-[#E2DFD6] rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-[#525860]">Affected</div>
          <div className="font-data font-semibold text-[#1A1C1E]">{sim.affected_employees_count} employees</div>
        </div>
      </div>
      {sim.employees?.length > 0 && (
        <details className="mt-3">
          <summary className="text-xs text-[#525860] cursor-pointer hover:text-[#1A1C1E]">View top 5 affected</summary>
          <div className="mt-2 space-y-1 text-xs font-data">
            {sim.employees.slice(0, 5).map((e) => (
              <div key={e.id} className="flex justify-between">
                <span>{e.name} <span className="text-[#686D76]">· {e.department}</span></span>
                <span className={e.delta_gross >= 0 ? "text-[#2D7A5D]" : "text-[#B83A3A]"}>
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

function PlanCard({ plan, onConfirm, onCancel, busy, results }) {
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
        {plan.steps.map((step, i) => {
          const result = results?.[i];
          const status = result?.status;
          return (
            <li key={`${step.type}-${i}`} className={`text-sm border rounded-md px-3 py-2 ${
              status === "ok" ? "border-[#9CC8B1] bg-[#E6F4EC]"
              : status === "error" ? "border-[#E1A1A1] bg-[#FBEAEA]"
              : "border-[#E2DFD6] bg-[#F7F6F2]"
            }`}>
              <div className="flex items-start gap-2">
                <span className="font-data text-xs text-[#525860] mt-0.5">{i + 1}.</span>
                <div className="flex-1">
                  <div className="font-medium text-[#1A1C1E]">{STEP_LABELS[step.type] || step.type}</div>
                  <pre className="font-mono text-[11px] text-[#525860] mt-0.5 overflow-x-auto">
                    {JSON.stringify({ ...step, type: undefined }, null, 0).slice(1, -1) || "—"}
                  </pre>
                  {result && (
                    <div className={`text-xs mt-1 ${status === "ok" ? "text-[#2D7A5D]" : status === "error" ? "text-[#B83A3A]" : "text-[#525860]"}`}>
                      {status === "ok" ? "✓ " : status === "error" ? "✗ " : "• "}{result.detail}
                    </div>
                  )}
                  {result?.simulation && <SimResultCard sim={result.simulation} title={step.title} />}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      {!finished && (
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
      )}
      {finished && (
        <div className="mt-4 pt-3 border-t border-[#F1EEE6] text-xs text-[#525860]">
          ✓ Plan executed — {results.filter((r) => r.status === "ok").length} of {results.length} steps succeeded.
        </div>
      )}
    </div>
  );
}

export default function Assistant() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sid, setSid] = useState(null);
  const [busy, setBusy] = useState(false);
  const [useContext, setUseContext] = useState(false);
  const [actionMode, setActionMode] = useState(false);
  const [executing, setExecuting] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Action mode requires context
  useEffect(() => { if (actionMode && !useContext) setUseContext(true); }, [actionMode, useContext]);

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    const msgId = crypto.randomUUID();
    setMessages((m) => [...m, { id: msgId, role: "user", content: q, withCtx: useContext, withAction: actionMode }]);
    setInput(""); setBusy(true);
    try {
      const { data } = await api.post("/assistant/chat", {
        message: q,
        session_id: sid,
        include_context: useContext && isAdmin,
        action_mode: actionMode && isAdmin,
      });
      setSid(data.session_id);
      setMessages((m) => [
        ...m,
        { id: crypto.randomUUID(), role: "assistant", content: data.reply, plan: data.plan },
      ]);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", content: `Error: ${typeof d === "string" ? d : "AI is unavailable"}` }]);
    } finally { setBusy(false); }
  };

  const executePlan = async (msgId, plan) => {
    setExecuting(msgId);
    try {
      const { data } = await api.post("/assistant/action/execute", { plan, session_id: sid });
      setMessages((m) => m.map((mm) => (mm.id === msgId ? { ...mm, results: data.results } : mm)));
    } catch (e) {
      const d = e?.response?.data?.detail;
      setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", content: `Execution failed: ${typeof d === "string" ? d : "unknown"}` }]);
    } finally { setExecuting(null); }
  };

  const cancelPlan = (msgId) => {
    setMessages((m) => m.map((mm) => (mm.id === msgId ? { ...mm, plan: null, cancelled: true } : mm)));
  };

  const suggestions = isAdmin && actionMode ? ACTION_SUGGESTIONS : isAdmin && useContext ? CONTEXT_SUGGESTIONS : GENERAL_SUGGESTIONS;
  // Strip the json fence from displayed text when a plan is parsed (or was cancelled — fence still in raw reply)
  const cleanContent = (m) => ((m.plan || m.cancelled) ? m.content.replace(/```(?:json)?\s*\{[\s\S]*?\}\s*```/g, "").trim() : m.content);

  return (
    <div className="space-y-6 h-[calc(100vh-160px)] flex flex-col" data-testid="assistant-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">AI Assistant</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1 flex items-center gap-2">SaloneHCM AI <Sparkles className="w-6 h-6 text-[#D1603D]" /></h1>
          <p className="text-[#525860] text-sm mt-1">Ask anything about Sierra Leone payroll — or instruct the AI to take action with confirmation.</p>
        </div>
        {isAdmin && (
          <div className="flex items-center gap-2">
            <button
              data-testid="assistant-context-toggle"
              type="button"
              onClick={() => setUseContext((v) => !v)}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded-md border text-xs font-medium transition ${
                useContext ? "bg-[#133326] border-[#133326] text-white" : "bg-white border-[#E2DFD6] text-[#525860] hover:border-[#133326]"
              }`}
            >
              <Database className="w-3.5 h-3.5" strokeWidth={1.5} />
              Use company data {useContext ? "· ON" : "· OFF"}
            </button>
            <button
              data-testid="assistant-action-toggle"
              type="button"
              onClick={() => setActionMode((v) => !v)}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded-md border text-xs font-medium transition ${
                actionMode ? "bg-[#D1603D] border-[#D1603D] text-white" : "bg-white border-[#E2DFD6] text-[#525860] hover:border-[#D1603D]"
              }`}
            >
              <Wand2 className="w-3.5 h-3.5" strokeWidth={1.5} />
              Action mode {actionMode ? "· ON" : "· OFF"}
            </button>
          </div>
        )}
      </div>

      {isAdmin && actionMode && (
        <div className="bg-[#FBE9DF] border border-[#E8B89C] rounded-md px-4 py-2.5 text-xs text-[#8B3A1C] flex items-center gap-2">
          <Wand2 className="w-3.5 h-3.5" />
          Action mode is ON — the AI will propose plans you must confirm before any change is made. Every step is audit-logged.
        </div>
      )}
      {isAdmin && useContext && !actionMode && (
        <div className="bg-[#FBF1DE] border border-[#E8D8AE] rounded-md px-4 py-2.5 text-xs text-[#8B6A14] flex items-center gap-2">
          <Database className="w-3.5 h-3.5" />
          The AI now has read access to employees, salaries, payroll runs, leave, attendance, and audit log.
        </div>
      )}

      <div className="flex-1 bg-white border border-[#E2DFD6] rounded-lg flex flex-col overflow-hidden">
        <div ref={ref} className="flex-1 overflow-y-auto p-6 space-y-4" data-testid="assistant-messages">
          {!messages.length && (
            <div className="max-w-md mx-auto text-center pt-10">
              <div className="w-12 h-12 rounded-full bg-[#FBE9DF] grid place-items-center mx-auto mb-3">
                <Sparkles className="w-5 h-5 text-[#D1603D]" />
              </div>
              <h3 className="font-heading text-lg font-semibold">How can I help?</h3>
              <p className="text-sm text-[#686D76] mt-1">
                {isAdmin && actionMode ? "Tell me what to do — I'll draft a plan for you to confirm."
                : isAdmin && useContext ? "I can see your live HR data — ask about anomalies, top performers, or trends."
                : "Trained on Sierra Leone HR rules, NRA bands, and NASSIT."}
              </p>
              <div className="grid grid-cols-1 gap-2 mt-5 text-left">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => send(s)} className="text-sm border border-[#E2DFD6] hover:border-[#133326] hover:bg-[#F7F6F2] rounded-md px-3 py-2 transition text-[#1A1C1E]">{s}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[78%] ${m.plan ? "w-full max-w-[78%]" : ""}`}>
                {m.role === "assistant" ? (
                  <>
                    {cleanContent(m) && (
                      <div className="bg-[#F7F6F2] text-[#1A1C1E] border border-[#E2DFD6] rounded-lg px-4 py-3 text-sm whitespace-pre-wrap">
                        {cleanContent(m)}
                      </div>
                    )}
                    {m.plan && !m.cancelled && (
                      <PlanCard
                        plan={m.plan}
                        results={m.results}
                        busy={executing === m.id}
                        onConfirm={() => executePlan(m.id, m.plan)}
                        onCancel={() => cancelPlan(m.id)}
                      />
                    )}
                    {m.cancelled && <div className="text-xs text-[#686D76] mt-1 italic">Plan cancelled.</div>}
                  </>
                ) : (
                  <div className="bg-[#133326] text-white rounded-lg px-4 py-3 text-sm whitespace-pre-wrap">
                    {m.withAction && <div className="text-[10px] uppercase tracking-wider text-[#D1603D] mb-1 inline-flex items-center gap-1"><Wand2 className="w-2.5 h-2.5" /> action request</div>}
                    {m.withCtx && !m.withAction && <div className="text-[10px] uppercase tracking-wider text-[#D1603D]/80 mb-1 inline-flex items-center gap-1"><Database className="w-2.5 h-2.5" /> with company data</div>}
                    {m.content}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex justify-start">
              <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-lg px-4 py-3 text-sm text-[#686D76]">Thinking…</div>
            </div>
          )}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); send(); }} className="border-t border-[#E2DFD6] p-3 flex gap-2">
          <input
            data-testid="assistant-input"
            value={input} onChange={(e) => setInput(e.target.value)}
            placeholder={isAdmin && actionMode ? "Tell me what to do…" : isAdmin && useContext ? "Ask about your team's data…" : "Ask about PAYE, NASSIT, leave, payroll…"}
            className="flex-1 bg-white border border-[#E2DFD6] rounded-md px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#26547C]"
          />
          <button data-testid="assistant-send" disabled={busy} className="inline-flex items-center gap-1.5 bg-[#D1603D] hover:bg-[#B84F2F] text-white px-4 py-2.5 rounded-md text-sm font-medium disabled:opacity-60">
            <Send className="w-4 h-4" /> Send
          </button>
        </form>
      </div>
    </div>
  );
}
