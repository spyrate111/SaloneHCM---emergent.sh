import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import {
  MessageSquare, ArrowLeft, Search, Check, AlertCircle, SkipForward, Send,
  Clock, FlaskConical, Download, Mail,
} from "lucide-react";

const STATUS_PILL = {
  sent: { color: "bg-[#E4F7E7] text-[#17A035]", icon: Check, label: "Sent" },
  would_send: { color: "bg-[#E5EEF6] text-[#26547C]", icon: Send, label: "Would send" },
  failed: { color: "bg-[#E9F2FB] text-[#3A7CB8]", icon: AlertCircle, label: "Failed" },
  skipped: { color: "bg-[#FBF1DE] text-[#8B6A14]", icon: SkipForward, label: "Skipped" },
};

const STATUS_FILTERS = ["", "sent", "would_send", "failed", "skipped"];

export default function SmsLogs() {
  const [summary, setSummary] = useState(null);
  const [batches, setBatches] = useState([]);
  const [logs, setLogs] = useState([]);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [filterStatus, setFilterStatus] = useState("");
  const [filterPeriod, setFilterPeriod] = useState("");
  const [q, setQ] = useState("");

  const loadAggregate = useCallback(async () => {
    const [s, b] = await Promise.all([
      api.get("/payroll/sms/summary"),
      api.get("/payroll/sms/batches"),
    ]);
    setSummary(s.data);
    setBatches(b.data);
  }, []);

  const loadLogs = useCallback(async (batchId = null) => {
    const params = {};
    if (batchId) params.batch_id = batchId;
    if (filterStatus && !batchId) params.status = filterStatus;
    if (filterPeriod && !batchId) params.period = filterPeriod;
    const r = await api.get("/payroll/sms/logs", { params });
    setLogs(r.data);
  }, [filterStatus, filterPeriod]);

  useEffect(() => { loadAggregate(); }, [loadAggregate]);
  useEffect(() => {
    if (selectedBatch) loadLogs(selectedBatch);
    else loadLogs();
  }, [selectedBatch, loadLogs]);

  const periods = Array.from(new Set(batches.map((b) => b.period))).sort().reverse();

  const downloadCsv = async () => {
    const params = {};
    if (selectedBatch) params.batch_id = selectedBatch;
    else {
      if (filterStatus) params.status = filterStatus;
      if (filterPeriod) params.period = filterPeriod;
    }
    try {
      const resp = await api.get("/payroll/sms/logs.csv", { params, responseType: "blob" });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url; a.download = "salonehcm-sms-audit.csv"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "CSV export failed");
    }
  };

  const emailCsv = async () => {
    const body = {};
    if (selectedBatch) body.batch_id = selectedBatch;
    else {
      if (filterStatus) body.status = filterStatus;
      if (filterPeriod) body.period = filterPeriod;
    }
    try {
      const { data } = await api.post("/payroll/sms/logs.csv/email", body);
      if (data?.ok) {
        toast.success(`CSV emailed to ${data.to} (${data.rows} rows)`);
      } else {
        toast.error(data?.error || "Email failed");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Email failed");
    }
  };

  const visibleLogs = logs.filter((l) => {
    if (!q) return true;
    const t = q.toLowerCase();
    return (
      l.employee_name?.toLowerCase().includes(t)
      || l.to?.toLowerCase().includes(t)
      || l.reason?.toLowerCase().includes(t)
      || l.sid?.toLowerCase().includes(t)
    );
  });

  return (
    <div className="space-y-6" data-testid="sms-logs-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Compliance & Audit</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1 flex items-center gap-2">
            SMS audit log <MessageSquare className="w-6 h-6 text-[#D1603D]" />
          </h1>
          <p className="text-[#525860] text-sm mt-1.5 max-w-2xl">
            Forensic record of every payslip SMS dispatched from this tenant. Filter by batch, status, period — every entry is tied to its payroll run and operator.
          </p>
        </div>
        {summary && summary.total_messages > 0 && (
          <div className="flex items-center gap-2">
            <button
              data-testid="email-csv"
              onClick={emailCsv}
              className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-4 py-2.5 rounded-md transition"
              title="Email the filtered audit CSV to your inbox"
            >
              <Mail className="w-4 h-4" strokeWidth={1.5} /> Email me the CSV
            </button>
            <button
              data-testid="export-csv"
              onClick={downloadCsv}
              className="inline-flex items-center gap-2 bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-[#0A4A1E] text-sm px-4 py-2.5 rounded-md transition"
            >
              <Download className="w-4 h-4" strokeWidth={1.5} /> Export CSV
            </button>
          </div>
        )}
      </div>

      {summary && summary.total_messages > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="sms-summary-kpis">
          <KPI icon={MessageSquare} label="Total messages" value={summary.total_messages} accent="bg-[#26547C]" />
          <KPI icon={Check} label="Delivered" value={summary.by_status.sent || 0} accent="bg-[#17A035]" />
          <KPI icon={AlertCircle} label="Failed" value={summary.by_status.failed || 0} accent="bg-[#3A7CB8]" />
          <KPI icon={Clock} label="Batches" value={summary.batch_count} accent="bg-[#D1603D]"
               sub={summary.last_sent_at ? `Last: ${new Date(summary.last_sent_at).toLocaleString()}` : ""} />
        </div>
      )}

      {!summary || summary.total_messages === 0 ? (
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-12 text-center">
          <MessageSquare className="w-12 h-12 mx-auto text-[#A1A5AB] mb-3" strokeWidth={1.3} />
          <h3 className="font-heading text-lg font-semibold text-[#1A1C1E]">No SMS sent yet</h3>
          <p className="text-sm text-[#525860] mt-1 max-w-md mx-auto">
            Once you send payslip SMS from the Payroll Engine page, every recipient delivery will be recorded here.
          </p>
        </div>
      ) : (
        <>
          <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="sms-batches">
            <div className="px-6 py-4 border-b border-[#E2DFD6]">
              <h3 className="font-heading text-lg font-semibold flex items-center gap-2">
                Batches <span className="text-xs text-[#686D76] font-normal">— {batches.length} recorded</span>
              </h3>
              <p className="text-xs text-[#686D76] mt-0.5">Click a batch to drill into its per-recipient deliveries.</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#F7F6F2]">
                  <tr>{["When", "Period", "Operator", "Mode", "Sent", "Would send", "Failed", "Skipped", "Total"].map((h) => (
                    <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {batches.map((b) => (
                    <BatchRow key={b.batch_id} b={b} onSelect={() => setSelectedBatch(b.batch_id)} active={selectedBatch === b.batch_id} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-[#E2DFD6] flex flex-wrap items-center gap-3">
              {selectedBatch && (
                <button
                  data-testid="back-to-all"
                  onClick={() => setSelectedBatch(null)}
                  className="inline-flex items-center gap-1 text-xs border border-[#E2DFD6] hover:bg-[#F7F6F2] px-2.5 py-1.5 rounded text-[#525860]"
                >
                  <ArrowLeft className="w-3.5 h-3.5" /> All batches
                </button>
              )}
              <h3 className="font-heading text-base font-semibold flex items-center gap-2">
                {selectedBatch ? `Recipients in this batch` : "All recipients"}
                <span className="text-xs text-[#686D76] font-normal">— {visibleLogs.length} of {logs.length}</span>
              </h3>
              <div className="flex-1" />
              <div className="relative max-w-xs flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A5AB]" strokeWidth={1.5} />
                <input
                  data-testid="sms-search"
                  placeholder="Name, phone, SID, reason…"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  className="w-full bg-[#F7F6F2] border border-[#E2DFD6] rounded-md pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#26547C]"
                />
              </div>
              {!selectedBatch && (
                <>
                  <select
                    data-testid="filter-status"
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
                  >
                    {STATUS_FILTERS.map((s) => <option key={s || "all"} value={s}>{s ? STATUS_PILL[s].label : "All statuses"}</option>)}
                  </select>
                  <select
                    data-testid="filter-period"
                    value={filterPeriod}
                    onChange={(e) => setFilterPeriod(e.target.value)}
                    className="bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm"
                  >
                    <option value="">All periods</option>
                    {periods.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#F7F6F2]">
                  <tr>{["Recipient", "Phone", "Period", "Status", "Twilio SID / Reason", "Sent at"].map((h) => (
                    <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {visibleLogs.map((l) => (
                    <RecipientRow key={l.id} l={l} />
                  ))}
                  {!visibleLogs.length && (
                    <tr><td colSpan={6} className="py-10 text-center text-sm text-[#686D76]">
                      {q || filterStatus || filterPeriod ? "No log entries match your filters." : "No log entries."}
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BatchRow({ b, onSelect, active }) {
  return (
    <tr
      data-testid={`batch-row-${b.batch_id}`}
      onClick={onSelect}
      className={`border-t border-[#E2DFD6] cursor-pointer hover:bg-[#FDFCFB] ${active ? "bg-[#F2FBF3]" : ""}`}
    >
      <td className="py-3 px-4">
        <div className="font-data text-[13px]">{new Date(b.sent_at).toLocaleString()}</div>
        <div className="text-[10px] uppercase tracking-wider text-[#686D76] font-data mt-0.5">{b.batch_id.slice(0, 8)}…</div>
      </td>
      <td className="py-3 px-4 font-data">{b.period}</td>
      <td className="py-3 px-4 text-[#525860] text-xs">{b.sent_by}</td>
      <td className="py-3 px-4">
        {b.dry_run
          ? <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-[#FBF1DE] text-[#8B6A14]"><FlaskConical className="w-3 h-3" /> Dry run</span>
          : <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-[#E4F7E7] text-[#17A035]"><Send className="w-3 h-3" /> Live</span>}
      </td>
      <td className="py-3 px-4 font-data text-[#17A035] font-semibold">{b.sent}</td>
      <td className="py-3 px-4 font-data text-[#26547C]">{b.would_send}</td>
      <td className="py-3 px-4 font-data text-[#3A7CB8]">{b.failed}</td>
      <td className="py-3 px-4 font-data text-[#8B6A14]">{b.skipped}</td>
      <td className="py-3 px-4 font-data text-[#1A1C1E] font-semibold">{b.total}</td>
    </tr>
  );
}

function RecipientRow({ l }) {
  const pill = STATUS_PILL[l.status] || STATUS_PILL.skipped;
  const Icon = pill.icon;
  return (
    <tr className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB]">
      <td className="py-3 px-4 font-medium">{l.employee_name || "—"}</td>
      <td className="py-3 px-4 font-data text-xs">{l.to || "—"}</td>
      <td className="py-3 px-4 font-data">{l.period}</td>
      <td className="py-3 px-4">
        <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-full ${pill.color}`}>
          <Icon className="w-3 h-3" /> {pill.label}
        </span>
      </td>
      <td className="py-3 px-4 text-xs text-[#686D76] font-data">{l.sid || l.reason || "—"}</td>
      <td className="py-3 px-4 text-xs text-[#686D76] font-data">{new Date(l.sent_at).toLocaleString()}</td>
    </tr>
  );
}

function KPI({ icon: Icon, label, value, sub, accent }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-4 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{label}</div>
        <div className="font-heading text-2xl font-bold mt-1 font-data">{value}</div>
        {sub && <div className="text-[10px] text-[#686D76] mt-0.5 truncate">{sub}</div>}
      </div>
      <div className={`w-9 h-9 rounded-md ${accent} grid place-items-center shrink-0`}>
        <Icon className="w-[18px] h-[18px] text-white" strokeWidth={1.5} />
      </div>
    </div>
  );
}
