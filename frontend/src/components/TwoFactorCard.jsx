import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { ShieldCheck, ShieldOff, Smartphone, Copy, Check, AlertCircle } from "lucide-react";

export default function TwoFactorCard() {
  const { refetch } = useAuth();
  const [policy, setPolicy] = useState(null);
  const [setup, setSetup] = useState(null);
  const [busy, setBusy] = useState(false);
  const [disabling, setDisabling] = useState(false);

  const load = useCallback(() => api.get("/auth/2fa/policy").then((r) => setPolicy(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const refreshAfter = async () => {
    await load();
    if (refetch) await refetch();
  };

  const beginSetup = async () => {
    setBusy(true);
    try {
      const r = await api.post("/auth/2fa/setup");
      setSetup(r.data);
    } catch {
      toast.error("Could not start 2FA setup");
    } finally {
      setBusy(false);
    }
  };

  if (!policy) return null;
  const { enabled, required } = policy;

  return (
    <section data-testid="twofa-card" className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden">
      <TwoFactorHeader enabled={enabled} required={required} role={policy.role} />
      <div className="px-7 py-6">
        {!enabled && !setup && (
          <button
            data-testid="twofa-begin"
            disabled={busy}
            onClick={beginSetup}
            className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-4 py-2.5 rounded-md disabled:opacity-60"
          >
            <Smartphone className="w-4 h-4" strokeWidth={1.5} /> Begin setup
          </button>
        )}
        {!enabled && setup && (
          <SetupPanel
            setup={setup}
            busy={busy}
            setBusy={setBusy}
            onCancel={() => setSetup(null)}
            onEnabled={async () => { setSetup(null); await refreshAfter(); }}
          />
        )}
        {enabled && !disabling && (
          <EnabledPanel required={required} onDisable={() => setDisabling(true)} />
        )}
        {enabled && disabling && (
          <DisablePanel
            busy={busy}
            setBusy={setBusy}
            onCancel={() => setDisabling(false)}
            onDisabled={async () => { setDisabling(false); await refreshAfter(); }}
          />
        )}
      </div>
    </section>
  );
}

function TwoFactorHeader({ enabled, required, role }) {
  return (
    <div className="px-7 py-6 border-b border-[#F1EEE6]">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Security</div>
          <h2 className="font-heading text-2xl font-bold mt-1 flex items-center gap-2">
            Two-factor authentication
            {enabled ? (
              <span className="text-[10px] uppercase tracking-wider font-medium px-2 py-1 rounded-full bg-[#E4F7E7] text-[#17A035] inline-flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" /> Enabled
              </span>
            ) : (
              <span className="text-[10px] uppercase tracking-wider font-medium px-2 py-1 rounded-full bg-[#EBE8E0] text-[#525860] inline-flex items-center gap-1">
                <ShieldOff className="w-3 h-3" /> Disabled
              </span>
            )}
          </h2>
          <p className="text-sm text-[#525860] mt-2 max-w-2xl">
            Add a second login step with a time-based code from Google Authenticator, 1Password, Authy, or any RFC-6238-compatible app.
          </p>
        </div>
        {required && !enabled && (
          <div className="text-xs bg-[#FBE9DF] border border-[#E8B89C] text-[#8B3A1C] rounded-md px-3 py-2 inline-flex items-center gap-1.5 max-w-sm">
            <AlertCircle className="w-4 h-4" />
            Required for {role} role — enable to protect your tenant.
          </div>
        )}
      </div>
    </div>
  );
}

function SetupPanel({ setup, busy, setBusy, onCancel, onEnabled }) {
  const [code, setCode] = useState("");
  const [copied, setCopied] = useState(false);

  const copySecret = async () => {
    if (!setup?.secret) return;
    try {
      await navigator.clipboard.writeText(setup.secret);
    } catch (e) {
      if (typeof console !== "undefined") console.warn("Clipboard write failed; secret shown in UI", e);
      toast.error("Could not copy automatically — select and copy the secret manually.");
      return;
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const enable2fa = async (ev) => {
    ev.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/2fa/enable", { code });
      toast.success("2FA enabled — keep your authenticator app safe!");
      setCode("");
      await onEnabled();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Invalid code");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6" data-testid="twofa-setup">
      <div>
        <div className="text-[11px] uppercase tracking-wider text-[#525860] mb-2">1. Scan in your authenticator app</div>
        <div className="inline-block bg-white border border-[#E2DFD6] rounded-md p-3">
          <img src={setup.qr_png_data_url} alt="2FA QR" className="w-44 h-44" />
        </div>
        <div className="mt-3 text-[11px] uppercase tracking-wider text-[#525860]">…or paste the secret manually</div>
        <div className="mt-1 inline-flex items-center gap-2">
          <code data-testid="twofa-secret" className="bg-[#F7F6F2] border border-[#E2DFD6] rounded px-2.5 py-1.5 font-data text-sm">{setup.secret}</code>
          <button onClick={copySecret} className="p-1.5 rounded hover:bg-[#F1EEE6] text-[#26547C]" title="Copy secret">
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>
      <form onSubmit={enable2fa} className="space-y-3">
        <div className="text-[11px] uppercase tracking-wider text-[#525860]">2. Enter the 6-digit code shown</div>
        <input
          data-testid="twofa-code-input"
          required
          inputMode="numeric"
          pattern="\d{6}"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          placeholder="123 456"
          className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2.5 text-base font-data tracking-widest focus:outline-none focus:ring-2 focus:ring-[#26547C]"
        />
        <button
          data-testid="twofa-enable"
          type="submit"
          disabled={busy || code.length !== 6}
          className="w-full inline-flex items-center justify-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-4 py-2.5 rounded-md disabled:opacity-60"
        >
          <ShieldCheck className="w-4 h-4" /> Enable 2FA
        </button>
        <button
          type="button"
          onClick={() => { setCode(""); onCancel(); }}
          className="w-full text-xs text-[#525860] hover:text-[#1A1C1E]"
        >
          Cancel setup
        </button>
      </form>
    </div>
  );
}

function EnabledPanel({ required, onDisable }) {
  return (
    <div className="flex items-center justify-between gap-4 flex-wrap">
      <p className="text-sm text-[#525860]">
        Your account is protected. You&rsquo;ll be asked for a 6-digit code at every sign-in.
      </p>
      {required ? (
        <span className="text-xs text-[#525860]">2FA is required for your role and cannot be disabled.</span>
      ) : (
        <button
          data-testid="twofa-disable-open"
          onClick={onDisable}
          className="text-sm text-[#3A7CB8] hover:bg-[#E9F2FB] border border-[#E2DFD6] rounded-md px-3 py-2"
        >
          Disable 2FA
        </button>
      )}
    </div>
  );
}

function DisablePanel({ busy, setBusy, onCancel, onDisabled }) {
  const [pwd, setPwd] = useState("");
  const [code, setCode] = useState("");

  const submit = async (ev) => {
    ev.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/2fa/disable", { password: pwd, code });
      toast.success("2FA disabled");
      setPwd(""); setCode("");
      await onDisabled();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not disable 2FA");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3 max-w-md" data-testid="twofa-disable-form">
      <p className="text-sm text-[#525860]">Confirm your password and a current 2FA code to disable.</p>
      <input
        required type="password" value={pwd} onChange={(e) => setPwd(e.target.value)}
        placeholder="Current password"
        className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2.5 text-sm font-data"
      />
      <input
        required inputMode="numeric" pattern="\d{6}" maxLength={6} value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
        placeholder="6-digit code"
        className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2.5 text-sm font-data tracking-widest"
      />
      <div className="flex gap-2">
        <button type="button" onClick={onCancel} className="text-sm px-4 py-2 border border-[#E2DFD6] rounded-md">Cancel</button>
        <button type="submit" disabled={busy} className="text-sm bg-[#3A7CB8] hover:bg-[#34689A] text-white px-4 py-2 rounded-md disabled:opacity-60">Disable</button>
      </div>
    </form>
  );
}
