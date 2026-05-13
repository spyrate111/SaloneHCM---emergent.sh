import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Lock, Mail, ArrowRight, ShieldCheck, UserCheck, AlertCircle } from "lucide-react";
import api from "../lib/api";

const BG = "https://images.unsplash.com/photo-1676029461383-215556e79bc8?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDJ8MHwxfHNlYXJjaHwyfHxzaWVycmElMjBsZW9uZSUyMGxhbmRzY2FwZSUyMHN1bnNldHxlbnwwfHx8fDE3Nzg0MjIzODZ8MA&ixlib=rb-4.1.0&q=85";

export default function Login() {
  const [params] = useSearchParams();
  const inviteToken = params.get("invite");
  const [mode, setMode] = useState(inviteToken ? "accept" : "login");
  const [email, setEmail] = useState("admin@salonehcm.sl");
  const [password, setPassword] = useState("Admin@2026");
  const [totpCode, setTotpCode] = useState("");
  const [needsTotp, setNeedsTotp] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [invite, setInvite] = useState(null);
  const [inviteErr, setInviteErr] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const { login, applyAuth } = useAuth();
  const nav = useNavigate();

  // Look up invite metadata on mount when ?invite=<token>
  useEffect(() => {
    if (!inviteToken) return;
    setMode("accept");
    api.get(`/auth/invite/${inviteToken}`)
      .then((r) => { setInvite(r.data); setEmail(r.data.email); })
      .catch((e) => {
        const d = e?.response?.data?.detail;
        setInviteErr((d && typeof d === "object") ? d.message : "Invitation invalid or expired");
      });
  }, [inviteToken]);

  const acceptInvite = async (e) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
      const r = await api.post("/auth/accept-invite", { token: inviteToken, password: newPassword });
      applyAuth(r.data);
      nav("/dashboard");
    } catch (er) {
      const d = er?.response?.data?.detail;
      setErr((d && typeof d === "object") ? d.message : (typeof d === "string" ? d : "Could not accept invitation"));
    } finally { setLoading(false); }
  };

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
      await login(email, password, needsTotp ? totpCode : undefined);
      nav("/dashboard");
    } catch (err) {
      const d = err?.response?.data?.detail;
      if (d && typeof d === "object" && d.code === "totp_required") {
        setNeedsTotp(true);
        setErr("");
      } else if (d && typeof d === "object" && d.code === "totp_invalid") {
        setErr("Invalid 2FA code — please try again");
      } else {
        setErr(typeof d === "string" ? d : "Sign-in failed");
        setNeedsTotp(false);
      }
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#F7F6F2]">
      {/* Left - visual */}
      <div className="relative hidden lg:block">
        <img src={BG} alt="Sierra Leone" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-br from-[#0a1f17]/85 via-[#133326]/70 to-[#0a1f17]/90" />
        <div className="relative z-10 h-full flex flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-md bg-[#D1603D] grid place-items-center font-heading font-bold">S</div>
            <div>
              <div className="font-heading font-bold text-lg leading-none">SaloneHCM</div>
              <div className="text-[10px] tracking-[0.18em] uppercase text-white/60 mt-1">Sierra Leone</div>
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-white/60 mb-4">Built for Salone businesses</div>
            <h1 className="font-heading text-4xl xl:text-5xl font-bold leading-tight max-w-md">
              Payroll, HR & compliance — <span className="text-[#D1603D]">localized</span> for Sierra Leone.
            </h1>
            <p className="mt-5 text-white/70 max-w-md text-[15px] leading-relaxed">
              NRA PAYE bands, NASSIT contributions, Employment Act 2023 — calculated automatically.
              From Bo to Freetown, run payroll in minutes.
            </p>
          </div>
          <div className="flex items-center gap-6 text-[11px] uppercase tracking-[0.18em] text-white/50">
            <span>NRA Compliant</span>
            <span className="w-1 h-1 rounded-full bg-white/40" />
            <span>NASSIT Ready</span>
            <span className="w-1 h-1 rounded-full bg-white/40" />
            <span>SLE Currency</span>
          </div>
        </div>
      </div>

      {/* Right - form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8 flex items-center gap-3">
            <div className="w-10 h-10 rounded-md bg-[#133326] grid place-items-center font-heading font-bold text-white">S</div>
            <div className="font-heading font-bold text-lg">SaloneHCM</div>
          </div>
          <div className="text-[11px] uppercase tracking-[0.22em] text-[#525860] mb-3">
            {mode === "accept" ? "You've been invited" : "Welcome back"}
          </div>
          <h2 className="font-heading text-3xl sm:text-4xl font-bold text-[#1A1C1E] mb-2">
            {mode === "accept" ? (invite ? `Join ${invite.company?.name || "your team"}` : "Accept your invitation") : "Sign in to your workspace"}
          </h2>
          <p className="text-[#525860] text-sm mb-8">
            {mode === "accept"
              ? "Set a password to activate your SaloneHCM account."
              : "Manage payroll, employees, and compliance for your Sierra Leonean business."}
          </p>

          {mode === "accept" ? (
            <>
              {inviteErr ? (
                <div className="bg-[#FBEAEA] border border-[#F2D0D0] text-[#B83A3A] text-sm rounded-md p-4 flex gap-2" data-testid="invite-error">
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="font-medium">{inviteErr}</div>
                    <button onClick={() => { setMode("login"); setInviteErr(""); }} className="underline text-xs mt-1">Sign in with existing credentials instead →</button>
                  </div>
                </div>
              ) : invite ? (
                <form onSubmit={acceptInvite} className="space-y-5" data-testid="accept-invite-form">
                  <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-4 text-sm flex items-start gap-3">
                    <UserCheck className="w-5 h-5 text-[#26547C] mt-0.5" strokeWidth={1.5} />
                    <div>
                      <div className="font-medium">{invite.name || invite.email}</div>
                      <div className="text-xs text-[#525860] font-data">{invite.email} · {invite.role}</div>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Choose a password</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A5AB]" strokeWidth={1.5} />
                      <input
                        data-testid="accept-password-input"
                        type="password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        required
                        minLength={8}
                        placeholder="At least 8 characters"
                        autoFocus
                        className="w-full bg-white border border-[#E2DFD6] rounded-md pl-10 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#26547C]"
                      />
                    </div>
                  </div>
                  {err && <div data-testid="login-error" className="text-sm text-[#B83A3A] bg-[#FBEAEA] border border-[#F2D0D0] rounded-md px-3 py-2">{err}</div>}
                  <button
                    data-testid="accept-submit-button"
                    type="submit"
                    disabled={loading}
                    className="w-full inline-flex items-center justify-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white rounded-md py-2.5 px-4 font-medium transition disabled:opacity-60"
                  >
                    {loading ? "Activating…" : "Accept invitation"}
                    <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
                  </button>
                </form>
              ) : (
                <div className="text-sm text-[#686D76]">Loading invitation details…</div>
              )}
            </>
          ) : (
          <form onSubmit={submit} className="space-y-5" data-testid="login-form">
            <div>
              <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A5AB]" strokeWidth={1.5} />
                <input
                  data-testid="login-email-input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full bg-white border border-[#E2DFD6] rounded-md pl-10 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#26547C]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A5AB]" strokeWidth={1.5} />
                <input
                  data-testid="login-password-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full bg-white border border-[#E2DFD6] rounded-md pl-10 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#26547C]"
                />
              </div>
            </div>

            {needsTotp && (
              <div data-testid="login-totp-block">
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">2FA code</label>
                <div className="relative">
                  <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A5AB]" strokeWidth={1.5} />
                  <input
                    data-testid="login-totp-input"
                    type="text"
                    inputMode="numeric"
                    pattern="\d{6}"
                    maxLength={6}
                    autoFocus
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    required
                    placeholder="123 456"
                    className="w-full bg-white border border-[#E2DFD6] rounded-md pl-10 pr-3 py-2.5 text-sm font-data tracking-widest focus:outline-none focus:ring-2 focus:ring-[#26547C]"
                  />
                </div>
                <p className="text-[11px] text-[#686D76] mt-1">Open your authenticator app and enter the 6-digit code.</p>
              </div>
            )}

            {err && <div data-testid="login-error" className="text-sm text-[#B83A3A] bg-[#FBEAEA] border border-[#F2D0D0] rounded-md px-3 py-2">{err}</div>}

            <button
              data-testid="login-submit-button"
              type="submit"
              disabled={loading}
              className="w-full inline-flex items-center justify-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white rounded-md py-2.5 px-4 font-medium transition disabled:opacity-60"
            >
              {loading ? "Signing in…" : "Sign In"}
              <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </form>
          )}

          <div className="mt-8 text-xs text-[#525860] bg-white border border-[#E2DFD6] rounded-md p-4">
            <div className="font-semibold uppercase tracking-wider text-[10px] text-[#1A1C1E] mb-2">Demo accounts</div>
            <div className="font-data">Admin · admin@salonehcm.sl · Admin@2026</div>
            <div className="font-data text-[#686D76]">Employee · aminata.kamara@salonehcm.sl · Employee@2026</div>
          </div>
        </div>
      </div>
    </div>
  );
}
