"""Company tiers + feature gating for multi-tenant SaloneHCM."""

# Tier hierarchy (low → high)
TIERS = ["lite", "professional", "enterprise", "gov"]

# Features available at each tier (inclusive of lower tiers)
TIER_FEATURES = {
    "lite": [
        "employees", "payroll", "compliance", "leave", "attendance", "self_service",
    ],
    "professional": [
        "employees", "payroll", "compliance", "leave", "attendance", "self_service",
        "benefits", "talent", "documents", "ai_assistant", "ai_context",
        "team_view", "audit_log", "analytics",
    ],
    "enterprise": [
        "employees", "payroll", "compliance", "leave", "attendance", "self_service",
        "benefits", "talent", "documents", "ai_assistant", "ai_context",
        "team_view", "audit_log", "analytics",
        "simulator", "scenarios", "scenario_compare", "decision_brief_pdf",
        "ai_action_mode",
    ],
    "gov": [
        "employees", "payroll", "compliance", "leave", "attendance", "self_service",
        "benefits", "talent", "documents", "ai_assistant", "ai_context",
        "team_view", "audit_log", "analytics",
        "simulator", "scenarios", "scenario_compare", "decision_brief_pdf",
        "ai_action_mode",
        "gov_payroll", "ministry_reports", "bulk_sms_payslips", "nra_export",
    ],
}

TIER_LABELS = {
    "lite": "Salone HCM Lite",
    "professional": "Salone HCM Professional",
    "enterprise": "Salone HCM Enterprise",
    "gov": "Salone HCM Gov",
}


def features_for(tier: str) -> list[str]:
    return TIER_FEATURES.get(tier, TIER_FEATURES["lite"])


def tier_label(tier: str) -> str:
    return TIER_LABELS.get(tier, "Salone HCM")


def tier_rank(tier: str) -> int:
    try:
        return TIERS.index(tier)
    except ValueError:
        return -1
