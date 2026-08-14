/**
 * Mobile clock in/out — grabs geolocation via the browser API and posts to
 * /api/mobile/punch. Punches are stored server-side with the GPS pin; when
 * offline the request is intercepted by the service worker and queued in
 * IndexedDB for later sync.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "../../lib/api";
import { Timer, MapPin, LogIn, LogOut, AlertTriangle, WifiOff, RefreshCw, CheckCircle2, XCircle, RotateCw, Trash2 } from "lucide-react";

const EMPTY_SUMMARY = { queued: 0, syncing: 0, failed: 0, total: 0 };

export default function MobileClock() {
  const [today, setToday] = useState([]);
  const [loc, setLoc] = useState(null);
  const [locErr, setLocErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [queue, setQueue] = useState([]); // detailed rows for the drawer
  const [online, setOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);
  const [showQueue, setShowQueue] = useState(false);

  const refresh = () =>
    api.get("/mobile/punch/today").then((r) => setToday(r.data || [])).catch(() => {});

  useEffect(() => { refresh(); }, []);

  // Ask the service worker for its current queue snapshot on mount
  useEffect(() => {
    if ("serviceWorker" in navigator && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({ kind: "queue-status" });
    }
  }, []);

  // Track online/offline transitions and drain when back online
  useEffect(() => {
    const on = () => {
      setOnline(true);
      if (navigator.serviceWorker?.controller) {
        navigator.serviceWorker.controller.postMessage({ kind: "drain-queue" });
      }
    };
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  // Listen for SW queue-status broadcasts (new v5 protocol)
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const handler = (event) => {
      const d = event.data || {};
      if (d.kind === "queue-status") {
        setSummary(d.summary || EMPTY_SUMMARY);
        setQueue(d.items || []);
      } else if (d.kind === "queue-drained") {
        if (d.count > 0) toast.success(`Synced ${d.count} queued punch${d.count === 1 ? "" : "es"}`);
        if (d.failed > 0) toast.error(`${d.failed} punch${d.failed === 1 ? "" : "es"} failed — tap to retry`);
        refresh();
      } else if (d.kind === "queue-added") {
        toast(`Punch queued — will sync when you're back online`);
      }
    };
    navigator.serviceWorker.addEventListener("message", handler);
    return () => navigator.serviceWorker.removeEventListener("message", handler);
  }, []);

  useEffect(() => {
    if (!navigator.geolocation) {
      setLocErr("Location not available on this device");
      return;
    }
    const watch = navigator.geolocation.watchPosition(
      (pos) => {
        setLoc({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        });
        setLocErr(null);
      },
      (err) => setLocErr(err.message || "Location permission denied"),
      { enableHighAccuracy: true, maximumAge: 10_000, timeout: 15_000 },
    );
    return () => navigator.geolocation.clearWatch(watch);
  }, []);

  const punch = async (kind) => {
    setBusy(true);
    try {
      const payload = {
        kind,
        lat: loc?.lat, lng: loc?.lng, accuracy_m: loc?.accuracy,
        device_id: (navigator.userAgent || "").slice(0, 60),
      };
      const r = await api.post("/mobile/punch", payload);
      if (r.status === 202 || r.data?.queued) {
        // Handled by the queue-added toast above
      } else {
        toast.success(kind === "in" ? "Clocked in ✓" : "Clocked out ✓");
        setToday((prev) => [...prev, r.data].sort((a, b) => a.clocked_at.localeCompare(b.clocked_at)));
      }
    } catch (e) {
      toast.error("Could not clock — try again");
    } finally {
      setBusy(false);
    }
  };

  const last = today[today.length - 1];
  const isOut = !last || last.kind === "out";
  const nextAction = isOut ? "in" : "out";

  const drainNow = () => {
    if (navigator.serviceWorker?.controller) {
      navigator.serviceWorker.controller.postMessage({ kind: "drain-queue" });
      toast("Syncing queued punches…");
    }
  };
  const retry = (id) => navigator.serviceWorker?.controller?.postMessage({ kind: "retry-failed", id });
  const purge = () => {
    if (window.confirm("Delete all failed punches? This cannot be undone.")) {
      navigator.serviceWorker?.controller?.postMessage({ kind: "purge-failed" });
      toast("Failed punches deleted");
    }
  };

  const hasQueueActivity = summary.total > 0 || !online;

  return (
    <div className="p-4 space-y-4" data-testid="mobile-clock">
      <div>
        <h1 className="text-lg font-bold text-[#0A4A1E]">Time & attendance</h1>
        <p className="text-[11px] text-[#525860]">Punch with a GPS pin — anti-buddy-punching.</p>
      </div>

      {/* Sync status card — visible whenever there is queue activity or user is offline */}
      {hasQueueActivity && (
        <div className="rounded-xl border p-3 space-y-2"
             data-testid="mobile-clock-queue-badge"
             style={{
               background: summary.failed > 0 ? "#FBE9E9" : (!online ? "#F6EDD8" : "#E4F7E7"),
               borderColor: summary.failed > 0 ? "#F1BAB3" : (!online ? "#F0DEA9" : "#B7E6C0"),
               color: summary.failed > 0 ? "#B03A2E" : (!online ? "#8B6A14" : "#0A4A1E"),
             }}>
          <div className="flex items-center gap-2 text-xs">
            {summary.failed > 0 ? <XCircle className="w-4 h-4 flex-shrink-0" />
              : !online ? <WifiOff className="w-4 h-4 flex-shrink-0" />
              : <CheckCircle2 className="w-4 h-4 flex-shrink-0" />}
            <div className="flex-1">
              <div className="font-semibold">
                {summary.failed > 0
                  ? `${summary.failed} punch${summary.failed === 1 ? "" : "es"} failed to sync`
                  : summary.syncing > 0
                  ? `Syncing ${summary.syncing} punch${summary.syncing === 1 ? "" : "es"}…`
                  : summary.queued > 0
                  ? `${summary.queued} punch${summary.queued === 1 ? "" : "es"} queued`
                  : "You are offline"}
              </div>
              <div className="text-[10px] opacity-80">
                {summary.failed > 0
                  ? "Tap Retry below, or the queue will retry automatically on the next sync."
                  : !online && summary.total === 0
                  ? "Any punch you make now will be stored locally and sync when you're online."
                  : summary.syncing > 0
                  ? "One moment — uploading your queued punches now."
                  : online
                  ? "Waiting for the next drain to send these to the server."
                  : "Waiting for signal to sync automatically."}
              </div>
            </div>
            {summary.total > 0 && (
              <button
                onClick={() => setShowQueue(!showQueue)}
                className="text-[10px] font-medium underline"
                data-testid="mobile-clock-queue-toggle"
              >
                {showQueue ? "Hide" : "View"} ({summary.total})
              </button>
            )}
          </div>
          {summary.total > 0 && online && (
            <button
              onClick={drainNow}
              className="w-full flex items-center justify-center gap-1 bg-current text-white text-[11px] px-3 py-2 rounded-lg active:opacity-90"
              style={{ background: summary.failed > 0 ? "#B03A2E" : "#8B6A14", color: "white" }}
              data-testid="mobile-clock-queue-sync"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Sync now
            </button>
          )}
          {showQueue && summary.total > 0 && (
            <div className="mt-2 divide-y divide-black/10 bg-white/60 rounded-lg" data-testid="mobile-clock-queue-list">
              {queue.map((it) => {
                let body = {};
                try { body = JSON.parse(it.body || "{}"); } catch { /* noop */ }
                return (
                  <div key={it.id} className="flex items-center gap-2 p-2 text-[11px]" data-testid={`mobile-clock-queue-item-${it.id}`}>
                    <StatusDot status={it.status} />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium capitalize">{body.kind || "punch"} · {new Date(it.queued_at).toLocaleTimeString()}</div>
                      <div className="opacity-70 truncate">
                        {it.status === "failed" ? (it.last_error || "failed") : it.status}
                        {it.attempts ? ` · ${it.attempts} attempt${it.attempts === 1 ? "" : "s"}` : ""}
                      </div>
                    </div>
                    {it.status === "failed" && (
                      <button onClick={() => retry(it.id)} className="p-1.5 rounded active:bg-black/10"
                              data-testid={`mobile-clock-queue-retry-${it.id}`} aria-label="Retry">
                        <RotateCw className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                );
              })}
              {summary.failed > 0 && (
                <button onClick={purge} className="w-full flex items-center justify-center gap-1 p-2 text-[10px]"
                        data-testid="mobile-clock-queue-purge">
                  <Trash2 className="w-3 h-3" /> Discard all failed
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* geolocation status */}
      <div className={`rounded-xl p-3 flex items-center gap-2 text-xs ${loc ? "bg-[#E4F7E7] text-[#0A4A1E]" : "bg-[#FBE9E9] text-[#B03A2E]"}`}
           data-testid="mobile-clock-geo">
        {loc ? (
          <>
            <MapPin className="w-4 h-4" />
            <div className="flex-1">
              <div className="font-medium font-data">{loc.lat.toFixed(5)}, {loc.lng.toFixed(5)}</div>
              <div className="text-[10px] opacity-70">accuracy ±{Math.round(loc.accuracy)}m</div>
            </div>
          </>
        ) : (
          <>
            <AlertTriangle className="w-4 h-4" />
            <div>{locErr || "Waiting for GPS lock…"}</div>
          </>
        )}
      </div>

      {/* action buttons */}
      <div className="grid grid-cols-1 gap-3">
        <button
          onClick={() => punch(nextAction)}
          disabled={busy}
          className={`h-24 rounded-2xl text-white text-lg font-bold flex flex-col items-center justify-center gap-1 disabled:opacity-50 active:opacity-90 ${
            nextAction === "in" ? "bg-[#0A4A1E]" : "bg-[#8B6A14]"
          }`}
          data-testid={`mobile-clock-${nextAction}`}
        >
          {nextAction === "in" ? <LogIn className="w-6 h-6" /> : <LogOut className="w-6 h-6" />}
          {busy ? "Recording…" : nextAction === "in" ? "Clock in" : "Clock out"}
        </button>
      </div>

      {/* today's punches */}
      <section data-testid="mobile-clock-today-list">
        <div className="text-[10px] uppercase tracking-widest text-[#525860] mb-2">Today · {new Date().toLocaleDateString()}</div>
        {today.length === 0 ? (
          <div className="text-center py-6 text-[#525860]">
            <Timer className="w-9 h-9 mx-auto text-[#A1A5AB]" />
            <p className="mt-2 text-xs">No punches recorded yet today.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {today.map((p) => (
              <div key={p.id} className="bg-white border border-[#E2DFD6] rounded-xl p-3 flex items-center gap-3"
                   data-testid={`mobile-clock-punch-${p.id}`}>
                {p.kind === "in" ? <LogIn className="w-5 h-5 text-[#0A4A1E]" /> : <LogOut className="w-5 h-5 text-[#8B6A14]" />}
                <div className="flex-1">
                  <div className="text-sm font-semibold uppercase">{p.kind}</div>
                  <div className="text-[11px] text-[#525860]">
                    {new Date(p.clocked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    {p.distance_from_branch_m != null && ` · ${Math.round(p.distance_from_branch_m)}m from ${p.branch_name || "branch"}`}
                  </div>
                </div>
                {p.hours > 0 && (
                  <div className="text-right">
                    <div className="text-[13px] font-bold font-data">{p.hours.toFixed(1)}h</div>
                    <div className="text-[10px] text-[#525860]">worked</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function StatusDot({ status }) {
  const color = {
    queued: "#8B6A14",
    syncing: "#0072C6",
    failed: "#B03A2E",
    synced: "#0A4A1E",
  }[status] || "#525860";
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${status === "syncing" ? "animate-pulse" : ""}`}
      style={{ background: color }}
      title={status}
    />
  );
}
