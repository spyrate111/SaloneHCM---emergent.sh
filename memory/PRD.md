# SaloneHCM — Product Requirements

## Original Problem Statement
SaloneHCM — Sierra Leone Human Capital Management & Payroll System. Cloud-based enterprise-grade HCM and payroll platform tailored to Sierra Leone's labor laws, tax framework (NRA PAYE, NASSIT), and financial regulations. Feature parity with ADP Workforce Now, Gusto, Paychex Flex, Rippling — localized for Sierra Leonean businesses. Currency: Sierra Leonean Leone (SLE). Multi-tenant with Lite/Professional/Enterprise/Gov tiers.

## Mission (displayed on Settings page)
Build a cloud-based, enterprise-grade Human Capital Management (HCM) and payroll platform tailored specifically to Sierra Leone's labor laws, tax framework, and financial regulations — offering the same depth and feature parity as ADP Workforce Now, Gusto, Sure Payroll, Paychex Flex, and Rippling — but localized for Sierra Leonean businesses of all sizes, from SMEs to large enterprises all around the country and the Government of Sierra Leone.

## Architecture (v1.3 — Multi-tenant)
- React 19 + Tailwind + shadcn/ui frontend, JWT in `sessionStorage`
- FastAPI backend modularised under `/app/backend/routers/*` (all routes under `/api`)
- MongoDB (Motor). **All data collections scoped by `company_id`** via `core.tenant_filter()` / `core.with_tenant()`.
- Collections: companies, users, employees, payroll_runs, leave_requests, attendance, benefit_plans, benefit_enrollments, job_postings, applicants, training_programs, training_completions, performance_reviews, documents, payroll_scenarios, audit_logs, assistant_messages
- Emergent Object Storage for uploads — path `salonehcm/{company_id}/uploads/{employee_id}/{uuid}.{ext}`
- Anthropic Claude Sonnet 4.5 via Emergent Universal LLM key for AI Assistant
- ReportLab for PDF (payslip + Decision Brief)
- slowapi rate-limiting with X-Forwarded-For aware `_client_ip`

## Tier ladder (`/app/backend/tiers.py`)
| Tier | Features |
|------|----------|
| **lite** | Core: employees, payroll, compliance, leave, attendance, self_service |
| **professional** | Lite + benefits, talent, documents, ai_assistant, analytics, team_view, audit_log |
| **enterprise** | Professional + simulator, scenarios, scenario_compare, decision_brief_pdf, ai_action_mode |
| **gov** | Enterprise + gov_payroll, ministry_reports, bulk_sms_payslips, nra_export |

Feature gating dependency: `require_feature("simulator")` → returns 402 if user's company tier lacks it.

## Implemented
### v1.0 — Core MVP
Auth, Dashboard, Employees CRUD, Payroll Engine (PAYE + NASSIT), Compliance, Leave, Attendance, AI Assistant.

### v1.1 — Advanced features
Benefits, Talent, Analytics, AI Action Mode, What-if Payroll Simulator, Scenario Save/Approve/Compare, slowapi rate-limiting, modular routers.

### v1.2 (May 2026) — MSS + Vault
Manager Self-Service (`/team`), Manager Leave Approval, Decision Brief PDF, Document Vault (Emergent Object Storage), Mission card on Settings.

### v1.3 (May 2026) — Multi-tenant + GovTier
- **Companies collection** with 2 seeds: Demo Salone Ltd. (enterprise), Government of Sierra Leone (gov)
- **`company_id` stamped on every collection** via `seeders/migrate.backfill_company_id()` at startup
- **Tier-gated features** with `require_feature(...)` dep returning 402 with upgrade prompt
- **NEW endpoints**: `GET /api/company`, `GET /api/company/tiers`
- **Login response** now includes `{company_id, company: {id, name, tier, label, features}}`
- **Frontend**: `useFeatures()` hook drives sidebar filtering + Settings tier showcase, header shows company name + tier badge
- **Settings page**: Mission + Current Plan card + Tier Ladder + Company info
- **Code review refactor**: Extracted `PlanCard` from Assistant.jsx, split Documents.jsx into `useDocuments` hook + `UploadModal` + `DocumentsTable`, split `seed.py` into `seeders/` package (companies, users, employees, benefits, talent, migrate), extracted `_decision_brief.py` + `_ai_context.py` + `_ai_executor.py` from monolithic simulator/assistant routers.

## Sierra Leone Payroll Rules
- NASSIT: 5% employee + 10% employer of basic
- PAYE bands (monthly SLE): 0–800 (0%), 800–2,200 (15%), 2,200–3,600 (20%), 3,600–5,000 (25%), 5,000–7,500 (30%), >7,500 (35%)

## Key API Endpoints
- `POST /api/auth/login` → `{token, company_id, company: {id,name,tier,label,features}, ...}`
- `GET /api/company`, `GET /api/company/tiers`
- `GET /api/employees`, `GET /api/team/me`, `GET /api/team/managers`, `GET /api/team/:eid`
- `POST /api/payroll/run`, `GET /api/payroll/runs`, `/runs/{id}/payslip/{eid}.pdf`, `/runs/{id}/bank-file`
- `POST /api/payroll/simulate`, `POST /api/payroll/scenarios`, `/scenarios/compare`, `/scenarios/compare/pdf`, `/scenarios/{id}/apply`
- `PUT /api/leave/{lid}/decision` — admin OR direct manager
- `POST /api/documents/upload` (multipart), `GET /api/documents`, `/documents/{id}/download`, `DELETE /api/documents/{id}`
- `POST /api/assistant/chat`, `POST /api/assistant/action/execute`

## Backlog (P1 → P3)
### P1
- Cross-tenant user provisioning: admin can invite users to their company; super-admin can switch companies
- Seed manager hierarchy with explicit direct reports (Aminata Kamara → her HR staff) for regression test data
- Performance reviews UI + recruitment ATS expansions

### P2
- Twilio bulk SMS payslips (Gov tier — requires user API keys)
- Resend email approver notifications for scenarios (requires user API key)
- Mobile ESS PWA
- NRA export filing automation (Gov tier)
- Cosmetic: Recharts width(-1) warning + UploadModal hydration warning

### P3
- Full Government tier features (ministry-level reporting, bulk SMS)
- Backend `tests/` regression suite (testing agent created `test_iter7_tenant.py` — extend it)

## Test Credentials
See `/app/memory/test_credentials.md`.

## Architecture Notes for Future Agents
- **Multi-tenant invariant**: every Mongo query MUST include `**tenant_filter(user)`, every insert MUST be wrapped with `with_tenant(doc, user)`.
- Tier gating: gate routers with `Depends(require_feature("feature_name"))` from `core.py`.
- Tier-locked endpoints return **402 Payment Required** (not 403) with an upgrade-prompt body.
- All third-party integrations route through `integration_playbook_expert_v2`.
- Emergent LLM key powers both AI Assistant and Object Storage.
- Token is in `sessionStorage` (key `salonehcm_token`); axios interceptor adds Bearer header.
- Documents soft-delete only (`is_deleted=true`).
- Storage paths are tenant-scoped: `salonehcm/{company_id}/uploads/...`
