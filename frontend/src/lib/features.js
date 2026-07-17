/** Feature-flag helpers driven by the user's company tier. */
import { useAuth } from "../context/AuthContext";

export const TIER_COLORS = {
  lite: "bg-[#EBE8E0] text-[#525860]",
  professional: "bg-[#E5EEF6] text-[#26547C]",
  enterprise: "bg-[#FBE9DF] text-[#B84F2F]",
  gov: "bg-[#E4F7E7] text-[#17A035]",
};

export const TIER_DESCRIPTIONS = {
  lite: "Core payroll & compliance for small teams.",
  professional: "+ benefits, talent, AI assistant, analytics, documents.",
  enterprise: "+ What-if simulator, scenarios, decision-brief PDF, AI Action Mode.",
  gov: "Gov-tier reports, ministry payrolls, bulk SMS payslips.",
};

export function useFeatures() {
  const { user } = useAuth();
  const features = user?.company?.features || [];
  const has = (f) => features.includes(f);
  const role = user?.role;
  return {
    features,
    has,
    company: user?.company,
    tier: user?.company?.tier,
    role,
    isAdmin: role === "admin" || role === "superadmin",
    isSuperAdmin: role === "superadmin",
  };
}
