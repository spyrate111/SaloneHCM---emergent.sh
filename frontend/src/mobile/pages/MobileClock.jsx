/**
 * Mobile clock in/out — grabs geolocation via the browser API and posts to
 * /api/mobile/punch. Punches are stored server-side with the GPS pin; when
 * offline the request is intercepted by the service worker and queued in
 * IndexedDB for later sync.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "../../lib/api";
import { Timer, MapPin, LogIn, LogOut, AlertTriangle } from "lucide-react";

export default function MobileClock() {
  const [today, setToday] = useState([]);
  const [loc, setLoc] = useState(null);
  const [locErr, setLocErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = () =>
    api.get("/mobile/punch/today").then((r) => setToday(r.data || [])).catch(() => {});

  useEffect(() => { refresh(); }, []);

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
      toast.success(kind === "in" ? "Clocked in ✓" : "Clocked out ✓");
      setToday((prev) => [...prev, r.data].sort((a, b) => a.clocked_at.localeCompare(b.clocked_at)));
    } catch (e) {
      if (!navigator.onLine) toast("You are offline — punch queued and will sync when online");
      else toast.error("Could not clock — try again");
    } finally {
      setBusy(false);
    }
  };

  const last = today[today.length - 1];
  const isOut = !last || last.kind === "out";
  const nextAction = isOut ? "in" : "out";

  return (
    <div className="p-4 space-y-4" data-testid="mobile-clock">
      <div>
        <h1 className="text-lg font-bold text-[#0A4A1E]">Time & attendance</h1>
        <p className="text-[11px] text-[#525860]">Punch with a GPS pin — anti-buddy-punching.</p>
      </div>

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
