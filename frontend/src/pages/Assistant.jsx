import { useState, useRef, useEffect } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Sparkles, Send, Database } from "lucide-react";

const GENERAL_SUGGESTIONS = [
  "How is PAYE calculated in Sierra Leone?",
  "What are the NASSIT contribution rates?",
  "How many days of annual leave under Employment Act 2023?",
  "Explain my payslip — basic SLE 5,000 + allowances SLE 800.",
];

const ADMIN_SUGGESTIONS = [
  "Show me payroll anomalies in our last run.",
  "Which department has the highest leave usage?",
  "Summarize audit activity in the last 7 days.",
  "Who are our top 3 highest-paid employees by gross?",
  "Are there any salary outliers across departments?",
];

export default function Assistant() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sid, setSid] = useState(null);
  const [busy, setBusy] = useState(false);
  const [useContext, setUseContext] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "user", content: q, withCtx: useContext }]);
    setInput(""); setBusy(true);
    try {
      const { data } = await api.post("/assistant/chat", {
        message: q,
        session_id: sid,
        include_context: useContext && isAdmin,
      });
      setSid(data.session_id);
      setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", content: data.reply }]);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", content: `Error: ${typeof d === "string" ? d : "AI is unavailable"}` }]);
    } finally { setBusy(false); }
  };

  const suggestions = isAdmin && useContext ? ADMIN_SUGGESTIONS : GENERAL_SUGGESTIONS;

  return (
    <div className="space-y-6 h-[calc(100vh-160px)] flex flex-col" data-testid="assistant-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">AI Assistant</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1 flex items-center gap-2">SaloneHCM AI <Sparkles className="w-6 h-6 text-[#D1603D]" /></h1>
          <p className="text-[#525860] text-sm mt-1">Ask anything about Sierra Leone payroll, NRA tax, NASSIT, leave, or HR policy.</p>
        </div>
        {isAdmin && (
          <button
            data-testid="assistant-context-toggle"
            type="button"
            onClick={() => setUseContext((v) => !v)}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded-md border text-xs font-medium transition ${
              useContext
                ? "bg-[#133326] border-[#133326] text-white"
                : "bg-white border-[#E2DFD6] text-[#525860] hover:border-[#133326]"
            }`}
            title="Grant AI live read access to your HR data"
          >
            <Database className="w-3.5 h-3.5" strokeWidth={1.5} />
            Use company data {useContext ? "· ON" : "· OFF"}
          </button>
        )}
      </div>

      {isAdmin && useContext && (
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
                {isAdmin && useContext
                  ? "I can see your live HR data — ask about anomalies, top performers, or trends."
                  : "Trained on Sierra Leone HR rules, NRA bands, and NASSIT."}
              </p>
              <div className="grid grid-cols-1 gap-2 mt-5 text-left">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => send(s)} className="text-sm border border-[#E2DFD6] hover:border-[#133326] hover:bg-[#F7F6F2] rounded-md px-3 py-2 transition text-[#1A1C1E]">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[78%] rounded-lg px-4 py-3 text-sm whitespace-pre-wrap ${
                m.role === "user" ? "bg-[#133326] text-white" : "bg-[#F7F6F2] text-[#1A1C1E] border border-[#E2DFD6]"
              }`}>
                {m.withCtx && (
                  <div className="text-[10px] uppercase tracking-wider text-[#D1603D]/80 mb-1 inline-flex items-center gap-1">
                    <Database className="w-2.5 h-2.5" /> with company data
                  </div>
                )}
                {m.content}
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
            placeholder={isAdmin && useContext ? "Ask about your team's data…" : "Ask about PAYE, NASSIT, leave, payroll…"}
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
