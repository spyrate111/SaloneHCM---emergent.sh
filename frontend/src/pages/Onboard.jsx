/**
 * `/onboard/:token` — public route the new-hire hits by scanning the QR
 * printed by the admin. Auto-consumes the one-time token, sets the session
 * cookies, then redirects to the mobile home. Also offers a "Save to home
 * screen" nudge so the phone becomes the primary interface.
 */
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { API, setToken } from "../lib/api";
import { CheckCircle2, ShieldAlert, Loader2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Onboard() {
  const { token } = useParams();
  const nav = useNavigate();
  const { applyAuth, refetch } = useAuth();
  const [status, setStatus] = useState("loading");
  const [msg, setMsg] = useState("");
  const [user, setUser] = useState(null);

  useEffect(() => {
    let cancelled = false;
    axios
      .post(`${API}/auth/onboarding-consume`, { token }, { withCredentials: true })
      .then(async (r) => {
        if (cancelled) return;
        const data = r.data || {};
        setToken(data.token);
        applyAuth({ ...data.user, token: data.token });
        // Sync full profile from /me so features/roles are hydrated
        try { await refetch(); } catch { /* noop */ }
        setUser(data.user);
        setStatus("ok");
        setTimeout(() => { if (!cancelled) nav(data.landing || "/m", { replace: true }); }, 1500);
      })
      .catch((e) => {
        if (cancelled) return;
        setStatus("err");
        setMsg(e?.response?.data?.detail || "This onboarding link is invalid or expired.");
      });
    return () => { cancelled = true; };
  }, [token, nav, applyAuth, refetch]);

  return (
    <div className="min-h-screen bg-[#F7F6F2] flex items-center justify-center px-6" data-testid="onboard-page">
      <div className="bg-white rounded-2xl shadow-sm border border-[#E2DFD6] p-6 max-w-sm w-full text-center">
        <div className="w-14 h-14 mx-auto rounded-full bg-[#E4F7E7] flex items-center justify-center">
          {status === "loading" && <Loader2 className="w-6 h-6 text-[#0A4A1E] animate-spin" />}
          {status === "ok" && <CheckCircle2 className="w-6 h-6 text-[#0A4A1E]" />}
          {status === "err" && <ShieldAlert className="w-6 h-6 text-[#B03A2E]" />}
        </div>
        <h1 className="text-lg font-bold mt-3">
          {status === "loading" && "Signing you in…"}
          {status === "ok" && `Welcome, ${user?.name?.split(" ")[0] || "there"}!`}
          {status === "err" && "Onboarding link problem"}
        </h1>
        <p className="text-xs text-[#525860] mt-2">
          {status === "loading" && "One moment while we verify your onboarding code."}
          {status === "ok" && "You are now signed in on SaloneHCM. Taking you to the mobile app…"}
          {status === "err" && msg}
        </p>
        {status === "ok" && (
          <p className="text-[10px] text-[#A1A5AB] mt-4">
            Tip: tap your browser's <b>Share → Add to Home Screen</b> to keep SaloneHCM one tap away.
          </p>
        )}
      </div>
    </div>
  );
}
