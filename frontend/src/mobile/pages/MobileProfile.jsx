/**
 * Mobile profile — push notifications toggle, biometric (WebAuthn) enrolment,
 * device list, app version. Uses existing /api/push and /api/auth/webauthn.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "../../lib/api";
import { Bell, BellOff, Fingerprint, Smartphone, Trash2, Info, LogOut } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

const REGISTRATION_KEY = "salonehcm_push_endpoint";

function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const base64Full = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64Full);
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

// WebAuthn helpers — encode ArrayBuffer to base64url and back for JSON transit
const b64uEnc = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)))
  .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const b64uDec = (s) => {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const base = (s + pad).replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(base);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
};

export default function MobileProfile() {
  const { user, logout } = useAuth();
  const [pushOn, setPushOn] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [creds, setCreds] = useState([]);
  const [bioBusy, setBioBusy] = useState(false);

  const refresh = () => {
    api.get("/push/status").then((r) => setPushOn(r.data?.subscription_count > 0)).catch(() => {});
    api.get("/auth/webauthn/credentials").then((r) => setCreds(r.data || [])).catch(() => {});
  };
  useEffect(refresh, []);

  const enablePush = async () => {
    setPushBusy(true);
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window))
        throw new Error("Push not supported on this browser");
      const perm = await Notification.requestPermission();
      if (perm !== "granted") throw new Error("Notification permission denied");
      const reg = await navigator.serviceWorker.ready;
      const key = await api.get("/push/public-key");
      if (!key.data?.vapid_public_key) throw new Error("Push not configured on server");
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key.data.vapid_public_key),
      });
      const j = sub.toJSON();
      await api.post("/push/subscribe", {
        endpoint: j.endpoint,
        keys: { p256dh: j.keys.p256dh, auth: j.keys.auth },
        user_agent: navigator.userAgent.slice(0, 200),
      });
      localStorage.setItem(REGISTRATION_KEY, j.endpoint);
      setPushOn(true);
      toast.success("Push notifications enabled");
    } catch (e) {
      toast.error(e.message || "Could not enable push");
    } finally {
      setPushBusy(false);
    }
  };

  const disablePush = async () => {
    setPushBusy(true);
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        const j = sub.toJSON();
        await api.post("/push/unsubscribe", {
          endpoint: j.endpoint,
          keys: { p256dh: j.keys?.p256dh || "", auth: j.keys?.auth || "" },
        });
        await sub.unsubscribe();
      }
      localStorage.removeItem(REGISTRATION_KEY);
      setPushOn(false);
      toast.success("Push notifications turned off");
    } catch (e) {
      toast.error("Could not turn off — try again");
    } finally {
      setPushBusy(false);
    }
  };

  const testPush = async () => {
    try {
      await api.post("/push/test", { title: "SaloneHCM", body: "This is a test notification", url: "/m" });
      toast.success("Test notification sent");
    } catch { toast.error("Test failed"); }
  };

  const enrolBiometric = async () => {
    setBioBusy(true);
    try {
      if (!("credentials" in navigator) || !("create" in navigator.credentials))
        throw new Error("Biometric not supported on this browser");
      const opts = await api.post("/auth/webauthn/register/begin", {});
      const publicKey = opts.data;
      // Convert base64url to ArrayBuffer where required
      publicKey.challenge = b64uDec(publicKey.challenge);
      publicKey.user.id = b64uDec(publicKey.user.id);
      (publicKey.excludeCredentials || []).forEach((c) => { c.id = b64uDec(c.id); });
      const cred = await navigator.credentials.create({ publicKey });
      const attestation = {
        id: cred.id,
        rawId: b64uEnc(cred.rawId),
        type: cred.type,
        response: {
          clientDataJSON: b64uEnc(cred.response.clientDataJSON),
          attestationObject: b64uEnc(cred.response.attestationObject),
        },
        clientExtensionResults: cred.getClientExtensionResults(),
      };
      await api.post("/auth/webauthn/register/finish", {
        credential: attestation,
        device_label: navigator.userAgent.slice(0, 60),
      });
      toast.success("Biometric enrolled ✓");
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message || "Enrol failed");
    } finally {
      setBioBusy(false);
    }
  };

  const revokeCred = async (cid) => {
    try {
      await api.delete(`/auth/webauthn/credentials/${cid}`);
      toast.success("Device revoked");
      refresh();
    } catch { toast.error("Could not revoke"); }
  };

  return (
    <div className="p-4 space-y-4" data-testid="mobile-profile">
      <div>
        <h1 className="text-lg font-bold text-[#0A4A1E]">Profile</h1>
        <p className="text-[11px] text-[#525860] mt-1">{user?.name}</p>
        <p className="text-[11px] text-[#525860]">{user?.email}</p>
        <span className="inline-block mt-1 text-[10px] uppercase tracking-widest bg-[#E4F7E7] text-[#0A4A1E] px-2 py-1 rounded-full">
          {user?.role}
        </span>
      </div>

      {/* Push notifications */}
      <section className="bg-white border border-[#E2DFD6] rounded-xl p-4 space-y-3" data-testid="mobile-profile-push">
        <div className="flex items-center gap-2">
          {pushOn ? <Bell className="w-5 h-5 text-[#0A4A1E]" /> : <BellOff className="w-5 h-5 text-[#525860]" />}
          <div className="flex-1">
            <div className="text-sm font-semibold">Push notifications</div>
            <div className="text-[11px] text-[#525860]">Voucher due · payslip ready · leave decided</div>
          </div>
        </div>
        <div className="flex gap-2">
          {pushOn ? (
            <>
              <button onClick={testPush} className="flex-1 text-xs border border-[#E2DFD6] py-2 rounded-lg"
                      data-testid="mobile-profile-push-test">Send test</button>
              <button onClick={disablePush} disabled={pushBusy}
                      className="flex-1 text-xs border border-[#B03A2E] text-[#B03A2E] py-2 rounded-lg disabled:opacity-50"
                      data-testid="mobile-profile-push-disable">
                {pushBusy ? "…" : "Turn off"}
              </button>
            </>
          ) : (
            <button onClick={enablePush} disabled={pushBusy}
                    className="flex-1 bg-[#0A4A1E] text-white text-xs py-2 rounded-lg disabled:opacity-50"
                    data-testid="mobile-profile-push-enable">
              {pushBusy ? "Enabling…" : "Enable notifications"}
            </button>
          )}
        </div>
      </section>

      {/* Biometric */}
      <section className="bg-white border border-[#E2DFD6] rounded-xl p-4 space-y-3" data-testid="mobile-profile-biometric">
        <div className="flex items-center gap-2">
          <Fingerprint className="w-5 h-5 text-[#0A4A1E]" />
          <div className="flex-1">
            <div className="text-sm font-semibold">Biometric sign-in</div>
            <div className="text-[11px] text-[#525860]">Use Face ID / Touch ID / fingerprint to sign in</div>
          </div>
        </div>
        {creds.length > 0 ? (
          <div className="space-y-2">
            {creds.map((c) => (
              <div key={c.id} className="flex items-center gap-2 bg-[#FAFAF7] rounded-lg p-2.5"
                   data-testid={`mobile-profile-cred-${c.id}`}>
                <Smartphone className="w-4 h-4 text-[#525860]" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium truncate">{c.device_label}</div>
                  <div className="text-[10px] text-[#A1A5AB]">
                    Added {new Date(c.created_at).toLocaleDateString()}
                    {c.last_used_at && ` · last used ${new Date(c.last_used_at).toLocaleDateString()}`}
                  </div>
                </div>
                <button onClick={() => revokeCred(c.id)} className="text-[#B03A2E] p-1.5 active:bg-[#FBE9E9] rounded"
                        aria-label="Revoke this device"
                        data-testid={`mobile-profile-cred-revoke-${c.id}`}>
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[11px] text-[#686D76]">No devices enrolled yet.</p>
        )}
        <button onClick={enrolBiometric} disabled={bioBusy}
                className="w-full text-xs border border-[#0A4A1E] text-[#0A4A1E] py-2 rounded-lg disabled:opacity-50 flex items-center justify-center gap-1"
                data-testid="mobile-profile-biometric-enrol">
          <Fingerprint className="w-4 h-4" /> {bioBusy ? "Enrolling…" : "Enrol this device"}
        </button>
      </section>

      {/* About */}
      <section className="bg-white border border-[#E2DFD6] rounded-xl p-4" data-testid="mobile-profile-about">
        <div className="flex items-center gap-2">
          <Info className="w-4 h-4 text-[#525860]" />
          <div className="text-[11px] text-[#525860]">
            SaloneHCM Mobile · PWA v1.0 · Same secure backend as the web platform
          </div>
        </div>
      </section>

      <button onClick={logout}
              className="w-full text-sm bg-white border border-[#B03A2E] text-[#B03A2E] py-3 rounded-xl active:bg-[#FBE9E9] flex items-center justify-center gap-2"
              data-testid="mobile-profile-signout">
        <LogOut className="w-4 h-4" /> Sign out
      </button>
    </div>
  );
}
