import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { setToken } from "../lib/api";
import { TIER_COLORS, TIER_DESCRIPTIONS } from "../lib/features";
import { toast } from "sonner";
import { Building2, Plus, X, ArrowRightLeft, Crown, Sparkles, ShieldAlert, ShieldCheck, RefreshCw } from "lucide-react";
import TwilioTestButton from "../components/TwilioTestButton";

const TIER_OPTIONS = [
  { value: "lite", label: "Salone HCM Lite" },
  { value: "professional", label: "Salone HCM Professional" },
  { value: "enterprise", label: "Salone HCM Enterprise" },
  { value: "gov", label: "Salone HCM Gov" },
];

export default function Companies() {
  const { user, refetch } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [open, setOpen] = useState(false);
  const [drift, setDrift] = useState(null);
  const [driftDetail, setDriftDetail] = useState(false);
  const [resyncing, setResyncing] = useState(false);

  const load = useCallback(async () => {
    const r = await api.get("/admin/companies");
    setCompanies(r.data);
  }, []);

  const loadDrift = useCallback(async () => {
    try {
      const r = await api.get("/admin/companies/drift-check");
      setDrift(r.data);
    } catch (e) {
      console.warn("[Companies] drift check failed:", e?.message || e);
    }
  }, []);

  useEffect(() => { load(); loadDrift(); }, [load, loadDrift]);

  const onResync = async () => {
    setResyncing(true);
    try {
      const r = await api.post("/admin/companies/drift-resync");
      toast.success(`Resynced ${r.data.fixed_count} tenant${r.data.fixed_count === 1 ? "" : "s"}`);
      await Promise.all([load(), loadDrift()]);
      setDriftDetail(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Resync failed");
    } finally {
      setResyncing(false);
    }
  };

  const onCreate = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.currentTarget);
    try {
      await api.post("/admin/companies", Object.fromEntries(fd.entries()));
      toast.success("Company created");
      setOpen(false);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Create failed");
    }
  };

  const onTierChange = async (c, tier) => {
    if (c.tier === tier) return;
    try {
      await api.patch(`/admin/companies/${c.id}/tier`, { tier });
      toast.success(`${c.name} → ${tier}`);
      load();
      loadDrift();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Tier update failed");
    }
  };

  const onSwitch = async (c) => {
    try {
      const r = await api.post(`/admin/companies/${c.id}/switch`);
      setToken(r.data.token);
      toast.success(`Switched into ${c.name}`);
      // refresh user via /me
      if (refetch) await refetch();
      else window.location.assign("/dashboard");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Switch failed");
    }
  };

  return (
    <div className="space-y-6" data-testid="companies-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Super-admin</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Tenants</h1>
          <p className="text-[#525860] text-sm mt-1.5 max-w-2xl">
            Provision new SaloneHCM customer tenants, change their tier, or switch into any tenant to operate as their admin.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <TwilioTestButton />
          <button
            data-testid="company-create-open"
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-4 py-2.5 rounded-md transition"
          >
            <Plus className="w-4 h-4" strokeWidth={1.5} /> Create tenant
          </button>
        </div>
      </div>

      {/* Tier drift monitor */}
      {drift && (
        <div
          data-testid="drift-monitor"
          className={`border rounded-lg p-4 ${
            drift.ok
              ? "border-[#BFEBC8] bg-[#EDF8EE]"
              : "border-[#F1C3A1] bg-[#FBEBDF]"
          }`}
        >
          <div className="flex items-start gap-3 flex-wrap">
            {drift.ok ? (
              <ShieldCheck className="w-5 h-5 text-[#17A035] mt-0.5" strokeWidth={1.5} />
            ) : (
              <ShieldAlert className="w-5 h-5 text-[#B84F2F] mt-0.5" strokeWidth={1.5} />
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-heading text-base font-semibold">
                  Tier-features drift monitor
                </h3>
                <span
                  data-testid="drift-badge"
                  className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full ${
                    drift.ok
                      ? "bg-[#17A035] text-white"
                      : "bg-[#B84F2F] text-white"
                  }`}
                >
                  {drift.ok ? "All in sync" : `${drift.drifted_count} drifted`}
                </span>
              </div>
              <p className="text-xs text-[#525860] mt-1 leading-relaxed">
                Verifies every tenant&rsquo;s <code className="bg-white px-1 py-0.5 rounded text-[#1A1C1E]">features</code> array matches its <code className="bg-white px-1 py-0.5 rounded text-[#1A1C1E]">tier</code>. Drift causes 402 errors on tier-gated routes. The boot-time seeder auto-heals on every restart; this lets you fix it in-process.
              </p>
              {!drift.ok && (
                <button
                  type="button"
                  onClick={() => setDriftDetail((v) => !v)}
                  className="mt-2 text-xs font-semibold text-[#B84F2F] hover:underline"
                  data-testid="drift-toggle-detail"
                >
                  {driftDetail ? "Hide" : "Show"} affected tenants ({drift.drifted_count})
                </button>
              )}
              {driftDetail && !drift.ok && (
                <div className="mt-3 space-y-2" data-testid="drift-detail">
                  {drift.drifted.map((d) => (
                    <div key={d.id} className="bg-white border border-[#F1C3A1] rounded-md px-3 py-2 text-xs">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-[#1A1C1E]">{d.name}</span>
                        <span className="text-[10px] uppercase tracking-wider bg-[#F1EEE6] px-1.5 py-0.5 rounded">{d.tier}</span>
                      </div>
                      {d.missing.length > 0 && (
                        <div className="mt-1 text-[#B84F2F]">
                          <span className="font-semibold">Missing:</span> {d.missing.join(", ")}
                        </div>
                      )}
                      {d.extra.length > 0 && (
                        <div className="mt-0.5 text-[#8C7000]">
                          <span className="font-semibold">Extra:</span> {d.extra.join(", ")}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {!drift.ok && (
              <button
                type="button"
                onClick={onResync}
                disabled={resyncing}
                className="inline-flex items-center gap-1.5 bg-[#B84F2F] hover:bg-[#9c4127] disabled:opacity-60 text-white text-xs px-3 py-2 rounded-md"
                data-testid="drift-resync-button"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${resyncing ? "animate-spin" : ""}`} strokeWidth={1.7} />
                {resyncing ? "Resyncing…" : "Resync now"}
              </button>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {companies.map((c) => {
          const isMine = c.id === user?.company_id;
          return (
            <div key={c.id} data-testid={`company-card-${c.id}`} className={`bg-white border rounded-lg p-5 ${isMine ? "border-[#0A4A1E] shadow-sm" : "border-[#E2DFD6]"}`}>
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-md bg-[#F1EEE6] grid place-items-center text-[#0A4A1E]">
                  <Building2 className="w-5 h-5" strokeWidth={1.5} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-heading font-semibold text-lg truncate">{c.name}</h3>
                    {isMine && (
                      <span className="text-[9px] uppercase tracking-widest font-semibold bg-[#0A4A1E] text-white px-1.5 py-0.5 rounded-full">
                        Active
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-[#686D76] font-data mt-0.5">{c.tin || "No TIN"} · {c.country}</div>
                </div>
              </div>

              <div className="mt-4 flex items-center gap-2">
                <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${TIER_COLORS[c.tier]}`}>
                  <Sparkles className="w-3 h-3" strokeWidth={1.7} /> {c.label || c.tier}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 mt-4 text-xs">
                <Stat label="Active employees" value={c.active_headcount} />
                <Stat label="User accounts" value={c.user_count} />
              </div>

              <div className="mt-4 flex items-center gap-2 flex-wrap">
                <select
                  data-testid={`company-tier-${c.id}`}
                  value={c.tier}
                  onChange={(e) => onTierChange(c, e.target.value)}
                  className="text-xs border border-[#E2DFD6] rounded-md px-2 py-1.5"
                  title="Change tier"
                >
                  {TIER_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                {!isMine && (
                  <button
                    data-testid={`company-switch-${c.id}`}
                    onClick={() => onSwitch(c)}
                    className="inline-flex items-center gap-1.5 text-xs bg-[#26547C] hover:bg-[#1f4565] text-white px-3 py-1.5 rounded-md"
                  >
                    <ArrowRightLeft className="w-3.5 h-3.5" strokeWidth={1.7} /> Switch in
                  </button>
                )}
                {isMine && (
                  <span className="inline-flex items-center gap-1.5 text-xs text-[#17A035] px-2">
                    <Crown className="w-3.5 h-3.5" /> You are operating here
                  </span>
                )}
              </div>

              <p className="text-[11px] text-[#686D76] mt-3 leading-relaxed">{TIER_DESCRIPTIONS[c.tier]}</p>
            </div>
          );
        })}
      </div>

      {open && (
        <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4" data-testid="company-create-modal">
          <form onSubmit={onCreate} className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-lg p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-heading text-lg font-semibold">Provision new tenant</h3>
              <button type="button" onClick={() => setOpen(false)} className="text-[#525860]"><X className="w-4 h-4" /></button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Company name" colSpan="col-span-2">
                <input data-testid="new-company-name" required name="name" placeholder="Bo Town Council" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </Field>
              <Field label="TIN"><input name="tin" placeholder="TIN-..." className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" /></Field>
              <Field label="NASSIT employer"><input name="nassit_employer" placeholder="NS-EMP-..." className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" /></Field>
              <Field label="Tier" colSpan="col-span-2">
                <select data-testid="new-company-tier" required name="tier" defaultValue="professional" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                  {TIER_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </Field>
            </div>
            <div className="border-t border-[#F1EEE6] pt-4">
              <div className="text-[11px] uppercase tracking-wider text-[#525860] mb-2">Initial admin account</div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Admin email" colSpan="col-span-2">
                  <input data-testid="new-company-admin-email" required type="email" name="admin_email" placeholder="admin@company.sl" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
                </Field>
                <Field label="Admin name"><input data-testid="new-company-admin-name" required name="admin_name" placeholder="Jane Doe" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
                <Field label="Initial password"><input data-testid="new-company-admin-password" required name="admin_password" type="password" minLength={8} placeholder="8+ chars" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" /></Field>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2">
              <button type="button" onClick={() => setOpen(false)} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]">Cancel</button>
              <button type="submit" data-testid="new-company-submit" className="inline-flex items-center gap-2 text-sm bg-[#0A4A1E] text-white px-4 py-2 rounded-md">
                <Plus className="w-4 h-4" strokeWidth={1.5} /> Create
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="bg-[#F7F6F2] rounded-md px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-[#525860]">{label}</div>
      <div className="font-data font-semibold text-[#1A1C1E] mt-0.5">{value ?? 0}</div>
    </div>
  );
}

function Field({ label, children, colSpan = "" }) {
  return (
    <div className={colSpan}>
      <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">{label}</label>
      {children}
    </div>
  );
}
