/* Helpers for VAPID web-push subscribe / unsubscribe + server registration. */
import api from "./api";

const VAPID_PUBLIC_KEY = process.env.REACT_APP_VAPID_PUBLIC_KEY || "";

function urlB64ToUint8Array(b64) {
  const padding = "=".repeat((4 - (b64.length % 4)) % 4);
  const base64 = (b64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export function isPushSupported() {
  return (
    typeof window !== "undefined"
    && "serviceWorker" in navigator
    && "PushManager" in window
    && "Notification" in window
    && !!VAPID_PUBLIC_KEY
  );
}

export async function currentSubscription() {
  if (!isPushSupported()) return null;
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
}

export async function subscribePush() {
  if (!isPushSupported()) throw new Error("Push notifications not supported in this browser");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("Notification permission denied");
  const reg = await navigator.serviceWorker.ready;
  const existing = await reg.pushManager.getSubscription();
  if (existing) await existing.unsubscribe();
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlB64ToUint8Array(VAPID_PUBLIC_KEY),
  });
  const json = sub.toJSON();
  await api.post("/push/subscribe", {
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    user_agent: navigator.userAgent.slice(0, 200),
  });
  return sub;
}

export async function unsubscribePush() {
  const sub = await currentSubscription();
  if (!sub) return false;
  const json = sub.toJSON();
  try {
    await api.post("/push/unsubscribe", {
      endpoint: json.endpoint,
      keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    });
  } catch (e) { /* ignore */ }
  return sub.unsubscribe();
}

export async function sendTestPush(message = "This is a test from SaloneHCM") {
  return api.post("/push/test", { title: "SaloneHCM test", body: message, url: "/dashboard" });
}
