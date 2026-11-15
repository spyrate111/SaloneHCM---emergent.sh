import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ShieldOff, LayoutDashboard, ArrowLeft } from "lucide-react";

export const AccessDenied = () => {
  const { user } = useAuth();
  return (
    <div className="min-h-[70vh] grid place-items-center" data-testid="access-denied-page">
      <div className="text-center max-w-md px-6">
        <div className="mx-auto w-16 h-16 rounded-2xl bg-[#FBE9E9] grid place-items-center">
          <ShieldOff className="w-8 h-8 text-[#B03A2E]" strokeWidth={1.5} />
        </div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860] mt-6">403 · Restricted</div>
        <h1 className="font-heading text-3xl font-bold text-[#1A1C1E] mt-2">
          You don&rsquo;t have permission to view this page
        </h1>
        <p className="text-sm text-[#686D76] mt-3">
          Your <span className="font-semibold capitalize">{user?.role || "current"}</span> role
          doesn&rsquo;t include access to this area. If you think you should have access,
          ask your administrator to update your role.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3 flex-wrap">
          <Link to="/dashboard"
            className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm font-medium px-5 py-2.5 rounded-lg"
            data-testid="access-denied-home-btn">
            <LayoutDashboard className="w-4 h-4" /> Go to my dashboard
          </Link>
          <button onClick={() => window.history.back()}
            className="inline-flex items-center gap-2 bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] text-sm font-medium px-5 py-2.5 rounded-lg"
            data-testid="access-denied-back-btn">
            <ArrowLeft className="w-4 h-4" /> Go back
          </button>
        </div>
      </div>
    </div>
  );
};

export default AccessDenied;
