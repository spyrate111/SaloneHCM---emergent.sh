import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Clock, ExternalLink, Plus, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";

const newCurrencyRow = (currency = "", rate = "") => ({ currency, rate });

function canManageFx(user) {
  return ["admin", "superadmin", "payroll"].includes(user?.role) || !!user?.finance_officer;
}

function localDateString() {
  const now = new Date();
  return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
}

function formatRate(value) {
  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 4,
    maximumFractionDigits: 8,
  });
}

export default function FxRates() {
  const { user } = useAuth();
  const canManage = canManageFx(user);
  const [sets, setSets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(null);
  const [publicationDate, setPublicationDate] = useState(localDateString);
  const [sourceType, setSourceType] = useState("bsl_reference");
  const [sourceUrl, setSourceUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [revision, setRevision] = useState("1");
  const [currencies, setCurrencies] = useState([
    newCurrencyRow("USD"),
    newCurrencyRow("GBP"),
    newCurrencyRow("EUR"),
  ]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get("/fx-rates");
      setSets(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not load FX reference rates");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const setCurrency = (index, key, value) => {
    setCurrencies((current) => current.map((row, i) => i === index ? { ...row, [key]: value } : row));
  };

  const addCurrency = () => setCurrencies((current) => [...current, newCurrencyRow()]);
  const removeCurrency = (index) => setCurrencies((current) => current.filter((_, i) => i !== index));

  const submit = async (event) => {
    event.preventDefault();
    const rates = {};
    for (const row of currencies) {
      const code = row.currency.trim().toUpperCase();
      if (!code && !row.rate) continue;
      if (!/^[A-Z]{3}$/.test(code) || !row.rate || !Number.isFinite(Number(row.rate)) || Number(row.rate) <= 0) {
        toast.error("Enter a three-letter currency code and a positive rate for every completed row.");
        return;
      }
      if (rates[code] !== undefined) {
        toast.error(`Currency ${code} appears more than once.`);
        return;
      }
      rates[code] = Number(row.rate);
    }
    if (Object.keys(rates).length === 0) {
      toast.error("Add at least one foreign-currency rate.");
      return;
    }
    setSaving(true);
    try {
      await api.post("/fx-rates", {
        publication_date: publicationDate,
        source_type: sourceType,
        source_url: sourceUrl,
        rates_sle_per_unit: rates,
        notes,
        revision: Number(revision),
      });
      toast.success("Rate set saved for separate finance approval.");
      setSourceUrl("");
      setNotes("");
      setRevision("1");
      await refresh();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not save FX rate set");
    } finally {
      setSaving(false);
    }
  };

  const approve = async (rateSetId) => {
    setApproving(rateSetId);
    try {
      await api.post(`/fx-rates/${rateSetId}/approve`);
      toast.success("FX rate set approved");
      await refresh();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not approve FX rate set");
    } finally {
      setApproving(null);
    }
  };

  return (
    <div className="space-y-6" data-testid="fx-rates-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Finance controls</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">FX reference rates</h1>
        <p className="text-[#525860] text-sm mt-1 max-w-3xl">
          Record SLE reference rates with their publication date and source document. Each rate set needs approval from a different finance user.
        </p>
      </div>

      <div className="flex items-start gap-3 rounded-lg border border-[#EAD9AE] bg-[#FDF8EC] p-4" role="note">
        <AlertTriangle className="w-5 h-5 text-[#8B6A14] flex-shrink-0 mt-0.5" />
        <div className="text-sm text-[#6C5415]">
          Reference rates only. These values do not convert payroll, PAYE, NASSIT, expenses, or mobile-money payouts. Finance must approve the accounting FX policy before conversion is enabled.
        </div>
      </div>

      {canManage && (
        <form onSubmit={submit} className="bg-white border border-[#E2DFD6] rounded-lg p-5 space-y-4" data-testid="fx-rate-create">
          <div>
            <h2 className="font-heading text-xl font-semibold">Record a rate set</h2>
            <p className="text-xs text-[#686D76] mt-1">Transcribe the published values from the source PDF. Use SLE per one unit of foreign currency.</p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <label className="text-xs text-[#525860]">
              Publication date
              <input type="date" required value={publicationDate} onChange={(event) => setPublicationDate(event.target.value)}
                className="block w-full mt-1 border border-[#E2DFD6] rounded-md px-3 py-2 text-sm text-[#1A1C1E]" />
            </label>
            <label className="text-xs text-[#525860]">
              Source type
              <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}
                className="block w-full mt-1 border border-[#E2DFD6] rounded-md px-3 py-2 text-sm text-[#1A1C1E]">
                <option value="bsl_reference">BSL reference rate</option>
                <option value="manual_override">Manual override</option>
              </select>
            </label>
            <label className="text-xs text-[#525860]">
              Revision
              <input type="number" min="1" max="100" required value={revision} onChange={(event) => setRevision(event.target.value)}
                className="block w-full mt-1 border border-[#E2DFD6] rounded-md px-3 py-2 text-sm text-[#1A1C1E]" />
            </label>
            <label className="text-xs text-[#525860] sm:col-span-2 lg:col-span-1">
              Source document URL
              <input type="url" required value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)}
                placeholder={sourceType === "bsl_reference" ? "https://bsl.gov.sl/…pdf" : "https://…"}
                className="block w-full mt-1 border border-[#E2DFD6] rounded-md px-3 py-2 text-sm text-[#1A1C1E]" />
            </label>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">Rates (SLE per one foreign-currency unit)</h3>
              <button type="button" onClick={addCurrency} className="inline-flex items-center gap-1 text-xs text-[#26547C] hover:underline">
                <Plus className="w-3.5 h-3.5" /> Add currency
              </button>
            </div>
            <div className="space-y-2">
              {currencies.map((row, index) => (
                <div key={index} className="grid grid-cols-[1fr_1fr_auto] gap-2 max-w-xl">
                  <input aria-label={`Currency code ${index + 1}`} value={row.currency} maxLength={3}
                    onChange={(event) => setCurrency(index, "currency", event.target.value.toUpperCase())}
                    placeholder="USD" className="border border-[#E2DFD6] rounded-md px-3 py-2 text-sm uppercase" />
                  <input aria-label={`SLE rate for currency ${index + 1}`} type="number" min="0" step="any" value={row.rate}
                    onChange={(event) => setCurrency(index, "rate", event.target.value)}
                    placeholder="22.8661" className="border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
                  <button type="button" onClick={() => removeCurrency(index)} aria-label={`Remove currency row ${index + 1}`}
                    className="p-2 text-[#686D76] hover:text-[#B03A2E]"><Trash2 className="w-4 h-4" /></button>
                </div>
              ))}
            </div>
          </div>

          <label className="block text-xs text-[#525860]">
            Notes {sourceType === "manual_override" && <span className="text-[#B03A2E]">· required for an override</span>}
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={500} rows={2}
              className="block w-full mt-1 border border-[#E2DFD6] rounded-md px-3 py-2 text-sm text-[#1A1C1E]"
              placeholder="Reason for the override or source context" />
          </label>
          <button type="submit" disabled={saving} className="inline-flex items-center gap-2 bg-[#0A4A1E] text-white px-4 py-2.5 rounded-md text-sm font-medium disabled:opacity-60">
            <Plus className="w-4 h-4" /> {saving ? "Saving…" : "Save pending approval"}
          </button>
        </form>
      )}

      <section className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="fx-rate-history">
        <div className="flex items-center justify-between gap-3 p-4 border-b border-[#E2DFD6]">
          <div>
            <h2 className="font-heading text-xl font-semibold">Rate history</h2>
            <p className="text-xs text-[#686D76] mt-1">Approved and pending entries are retained with their source and approval record.</p>
          </div>
          <button type="button" onClick={refresh} disabled={loading} aria-label="Refresh FX rates"
            className="p-2 border border-[#E2DFD6] rounded-md text-[#525860] disabled:opacity-50">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {loading ? <div className="p-6 text-sm text-[#525860]">Loading rate history…</div>
          : sets.length === 0 ? <div className="p-6 text-sm text-[#686D76]">No rate sets recorded for this organization.</div>
          : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[950px] text-sm">
                <thead className="bg-[#F7F6F2]">
                  <tr>{["Date", "Revision", "Type", "Rates (SLE per foreign unit)", "Source", "Status", "Approval"].map((label) =>
                    <th key={label} className="text-left px-3 py-2 text-[10px] uppercase tracking-wider text-[#686D76] font-medium">{label}</th>)}</tr>
                </thead>
                <tbody>
                  {sets.map((row) => (
                    <tr key={row.id} className="border-t border-[#F1EEE6] align-top">
                      <td className="px-3 py-3 font-data">{row.publication_date}</td>
                      <td className="px-3 py-3 font-data">{row.revision}</td>
                      <td className="px-3 py-3">{row.source_type === "bsl_reference" ? "BSL reference" : "Manual override"}</td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-x-3 gap-y-1">
                          {Object.entries(row.rates_sle_per_unit || {}).map(([code, rate]) =>
                            <span key={code} className="font-data"><b>{code}</b> {formatRate(rate)}</span>)}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <a href={row.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[#26547C] hover:underline">
                          Source document <ExternalLink className="w-3 h-3" />
                        </a>
                        <div className="text-[10px] text-[#686D76] mt-1">Recorded {row.retrieved_at}</div>
                        {row.notes && <div className="text-[11px] text-[#525860] mt-1 max-w-xs">{row.notes}</div>}
                      </td>
                      <td className="px-3 py-3">
                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10px] uppercase ${row.status === "approved" ? "bg-[#E4F7E7] text-[#0A4A1E]" : "bg-[#F6EDD8] text-[#8B6A14]"}`}>
                          {row.status === "approved" ? <Check className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                          {row.status}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        {row.status === "approved"
                          ? <div className="text-xs text-[#525860]">{row.approved_by || "Finance user"}<div className="text-[10px]">{row.approved_at}</div></div>
                          : canManage && row.created_by_user_id !== user?.id
                            ? <button type="button" onClick={() => approve(row.id)} disabled={approving === row.id}
                                className="inline-flex items-center gap-1 bg-[#26547C] text-white px-2.5 py-1.5 rounded text-xs disabled:opacity-50">
                                <Check className="w-3 h-3" /> {approving === row.id ? "Approving…" : "Approve"}
                              </button>
                            : <span className="text-xs text-[#8A8F96]">Second-person approval required</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </section>
    </div>
  );
}
