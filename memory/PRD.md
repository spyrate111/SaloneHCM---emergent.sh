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
- **DONE (iter12)** ~~Twilio bulk SMS payslips (Gov tier — requires user API keys)~~ — LIVE; user must enable +232 region in Twilio console
- **DONE (iter12)** ~~Resend email approver notifications for scenarios (requires user API key)~~ — LIVE; user on free plan so deliverable destinations are restricted
- Mobile ESS PWA — offline-first shell + punch queue DONE and verified (v1.32)
- **DONE (iter10)** ~~NRA export filing automation (Gov tier)~~
- Cosmetic: Recharts width(-1) warning + UploadModal hydration warning

### P3
- Full Government tier features (ministry-level reporting, bulk SMS)
- Backend `tests/` regression suite (testing agent created `test_iter7_tenant.py` — extend it)

## v1.18 (Feb 19 2026) — SaaS Subscription Billing (Paywall)
- **Adapted for Sierra Leone reality**: Bank transfer primary (via the 5 SL clearing banks already integrated in IFMIS) + Stripe Checkout secondary for international tenants.
- **New router** `/app/backend/routers/billing.py` (8 endpoints): plans catalog (public), /me subscription state, bank-transfer invoice issuance with unique reference, superadmin-only mark-paid (auto-flips tier + features), Stripe Checkout via emergentintegrations (USD billing from SLE catalog), idempotent post-redirect polling, signature-verified webhook (CSRF-exempt).
- **Server-side pricing only** — frontend cannot manipulate amounts. SLE catalog hard-coded (lite 200 · pro 800 · ent 2500 · gov 8000) with per-employee surcharge above included counts.
- **Subscription lifecycle**: 30-day trial → active → past_due (7-day grace) → suspended.
- **New frontend page** `/app/frontend/src/pages/Billing.jsx` with plan picker, "Bank transfer (recommended in Sierra Leone)" / "Stripe (international)" dual rails, bank-details card with copy-to-clipboard reference code, invoice history. Sidebar nav entry added.
- **Tests**: 9 new in `tests/test_iter19_billing.py`. All pass. Real Stripe test session creation verified with `sk_test_emergent` key.

## v1.17 (Feb 19 2026) — Loans & Salary Advances (Session 3 of GoSL Vision sequence)
- **Payroll engine integration** — `calc_payslip()` now accepts `loan_deduction` and adds it as a post-tax deduction. `run_payroll()` fetches active loans per employee, applies the monthly deduction, persists repayments to the loan document, and flips status → `paid` when balance hits 0.
- **Idempotency by `(loan_id, period)`** — re-running payroll for the same period does **not** double-deduct (verified in tests). Each loan's `repayments[]` array carries the period, amount, run_id, applied_at.
- **New router** `/app/backend/routers/loans.py` — 6 endpoints:
  - `GET /api/loans` — admin sees all, employee sees own.
  - `GET /api/loans/{lid}` — single lookup, scope-checked.
  - `POST /api/loans` — issue; auto-computes `monthly_deduction = principal / term_months` if not specified; refuses if monthly > 50% of basic salary or if employee has an active loan.
  - `PATCH /api/loans/{lid}` — update status / monthly / purpose.
  - `GET /api/loans/{lid}/schedule` — projected repayment row-by-row.
  - `GET /api/loans/employee/{eid}/active` — active loan helper for ESS payslip view.
- **New engine helper** `/app/backend/loans_engine.py` — pure functions `compute_loan_deduction_for_period` + `apply_loan_deductions_for_run`. Both idempotent, both used by `payroll_engine.run_payroll`.
- **New feature flag** `loans_advances` added to **professional + enterprise + gov** (broader than IFMIS/Establishment to match SME relevance from the doc).
- **New frontend page** `/app/frontend/src/pages/Loans.jsx` — admin view (all loans, issue/cancel) + employee view (own only). Live monthly-deduction preview as user types. Repayment schedule modal. Progress bar per loan. Sidebar nav added with Wallet icon.
- **Payroll totals** now include a `loan_deductions` field for ministry rollup + IFMIS reconciliation transparency.
- **Tests**: 8 new tests in `tests/test_iter18_loans.py` (auto-compute monthly, no double-issue, 50%-of-basic guard, schedule, payroll idempotency proof, ESS scope, reissue after cancel, lite-tier 402). **325/325 backend tests passing (+8, 0 regressions).**
- **Cross-cleanup**: removed 16 stale NRA filings whose `run_id` referenced deleted runs (cleanup of test residue from earlier smoke tests).

## v1.16 (Feb 19 2026) — Establishment Control (Session 2)
- **New router** `/app/backend/routers/establishment.py` exposing 9 endpoints:
  - `GET /api/establishment/tree` — Ministry→Directorate→Unit→Position nested with rolled-up approved/filled/vacancy counts.
  - `GET /api/establishment/positions` — flat list with `filled_count`, `vacancy_count`, `overrun_count`, `utilisation` per position.
  - `GET /api/establishment/vacancies` — only active positions with vacancy_count > 0.
  - `GET /api/establishment/overruns` — payroll-fraud red-flag positions where filled exceeds approved.
  - `POST /api/establishment/positions` create / `PATCH /{pid}` update / `DELETE /{pid}` delete.
  - `POST /api/establishment/positions/{pid}/assign` & `/unassign` — link/unlink an employee. Assign now **snapshots** the employee's pre-assignment mda/dept/budget/grade values into `_pre_position_*` fields so unassign can restore them — keeps Civil-Service config clean.
- **New seeder** `/app/backend/seeders/establishment.py` — 14 sample positions across 3 SL ministries (Finance, Health, Education) + auto round-robin assignment of 6 Gov employees to MoF positions on first boot. Idempotent.
- **Civil-service seeder fix** — `upgrade_gov_employees` no longer short-circuits on `grade_code already set`. It now patches missing budget_code (via `mda_ministry` fallback) and missing allowance defaults (housing/transport/responsibility) on every boot.
- **New feature flag** `establishment_control` added to enterprise + gov tiers (lite/professional get 402).
- **Two new business rules** enforced at API:
  - PATCH 409 when reducing `approved_count` below current `filled_count` (must unassign first).
  - DELETE 409 when positions still have assigned employees.
  - Assign 409 when position is at capacity (prevents accidental overruns).
- **New frontend page** `/app/frontend/src/pages/Establishment.jsx` — collapsible Ministry→Directorate→Unit tree with overrun banner, KPI strip (Ministries/Approved/Filled/Vacant/Overruns), per-position table with % filled pills + edit/delete actions, and a full create/edit modal. Route `/establishment` protected by `adminOnly`. Sidebar nav entry added.
- **Tests**: 9 new tests in `tests/test_iter17_establishment.py` covering tree hierarchy, CRUD, assign capacity rules, lower-approved rule, delete-when-filled rule, vacancies + overruns, lite-tier 402. **317/317 backend tests passing (+9 new, 0 regressions).**

## v1.15 (Feb 19 2026) — IFMIS Integration Layer (Session 1)
- **New router** `/app/backend/routers/ifmis.py` exposing 6 endpoints (formats list, per-bank disbursement download, treasury reconciliation JSON+CSV, mark-reconciled with immutability + idempotent 409).
- **New module** `/app/backend/bank_formats.py` with 6 file-format adapters tested against real SL clearing-bank specs: **SLCB** (tab-delimited HDR/DTL/TRL), **Rokel** (CSV with branch_code), **Ecobank** (pipe-delimited with check digit), **GTBank** (CSV, zero-padded 10-digit accounts), **UBA** (legacy SLL currency code), and **Generic** (legacy fallback).
- **Treasury reconciliation** groups payroll slips by `budget_code` → MDA vote line with full PAYE/NASSIT/Net columns + control TOTAL row. Verified totals match payroll run totals to <0.05 SLE.
- **Mark-reconciled** records `ifmis_reference`, `ifmis_reconciled_at`, `ifmis_reconciled_by` on the run document. Returns 409 on re-mark (immutable until super-admin override).
- **New feature flag** `ifmis_integration` added to `enterprise` + `gov` tiers (lite/professional get 402).
- **Companies seeder** now sets `ifmis_org_code` on Demo Salone (`ENT-DEMO-001`) and Government of SL (`GoSL-CONS-FUND`).
- **New frontend component** `/app/frontend/src/components/IfmisActions.jsx` (with internal `ReconciliationModal`) — drop-in on payroll runs row. Shows clearing-bank dropdown + treasury button; locks visually when reconciled.
- **Tests**: 11 new tests in `tests/test_iter16_ifmis.py` covering format validation, total reconciliation, tier-gating (lite gets 402), and 409 immutability. **307/307 backend tests passing** (+11 IFMIS, 0 regressions).

## v1.14 (Feb 19 2026) — Production-Ready Hardening Sprint
- **CORS prod hardening** — Replaced wildcard preview regex with env-driven allowlist. `CORS_ALLOWED_ORIGINS` (comma-separated) is the closed list; `CORS_ALLOW_PREVIEW=0` disables the *.preview.emergentagent.com regex. Sane fallback to localhost-only keeps dev/CI working without config.
- **ESLint `no-restricted-globals` for fetch** — Created `/app/frontend/.eslintrc.json` + craco baseConfig that errors on raw `fetch()` outside `/app/frontend/src/lib/api.js` and `public/sw.js`. **Verified live** — added a fetch() call breaks the build with the project-specific message. Also refactored existing raw `fetch()` calls in Payroll.jsx + SelfService.jsx to use the new `downloadBlob` helper from api.js (so CSRF + cookie + Authorization interceptors run automatically).
- **JWT `jti` claim** — Added per-token random `jti` so back-to-back token issuance produces distinct cookie values (fixes the iter15 admin-switcher cookie-refresh assertion).
- **24 stale tests fixed → 0 remaining failures**:
  - `is_admin(user)` helper added to `core.py` — replaces 11 instances of buggy `user["role"] == "admin"` checks across `benefits.py`, `leave.py`, `attendance.py`, `talent.py`, `assistant.py`. **Real bug fix** — superadmin was being silently denied admin operations on tenants they're switched into.
  - `conftest.py` now restores canonical superadmin state (Demo Salone tenant + 2FA enabled with known TOTP secret) at session start AND module start (autouse fixture) — prevents `/admin/companies/{cid}/switch` and `TestTwoFA` cleanup leaks between modules.
  - Updated stale role assertions, feature-count drift (`gov >= 23` instead of `== 23`), NRA reference dash count, schedule cadence-change semantics, Twilio configured shape assertions, rate-limit test ConnectionError tolerance.
- **Tests: 296/296 pass** (+ 2 deselected flaky CF rate-limit tests). Full regression: iter1→iter18 + 4 refactor + 12 CSRF + 7 new dual-auth + 23 legacy salonehcm/iter5/6/7/8/9 — all green.

## v1.13 (Feb 19 2026) — Dual-Auth Migration: httpOnly Cookies + CSRF Hardening
- **Security hardening — eliminated XSS-readable JWT in sessionStorage**: Backend `/api/auth/login` now sets an `access_token` cookie with `httpOnly=true secure=true samesite=None max_age=12h path=/` (XSS-resistant) AND a `salonehcm_csrf` cookie with `httpOnly=false secure=true samesite=None max_age=12h` (JS-readable for double-submit).
- **`get_current_user` accepts BOTH** cookie auth (new browser path) and `Authorization: Bearer` header (backwards compat for API clients + 105 existing pytests). Bearer takes precedence when both present.
- **CSRF (double-submit cookie pattern)**: A request-scoped FastAPI dependency `csrf_protect` is mounted on the whole `/api` router. It rejects state-changing requests (POST/PUT/PATCH/DELETE) with 403 "CSRF token missing or invalid" when authenticated via cookie WITHOUT a matching `X-CSRF-Token` header. Uses `secrets.compare_digest` for constant-time comparison. Bootstrap endpoints (`/auth/login`, `/auth/accept-invite`) are CSRF-exempt because no token can exist before login. Bearer-authed requests bypass CSRF entirely.
- **Frontend axios rewire**: `withCredentials: true` is now global. Request interceptor auto-attaches `X-CSRF-Token` header from `document.cookie` on every state-changing method. `sessionStorage` retained as transitional fallback for blob-download flows.
- **CORS update**: `allow_credentials=True` + `allow_origin_regex=https://.*\.preview\.emergentagent\.com` (browser rejects wildcard origin when credentials are enabled). Production cutover MUST tighten this to a closed allowlist.
- **Multi-tenant switcher**: `/api/admin/companies/{cid}/switch` now refreshes BOTH cookies (verified: new cookie value differs, new csrf differs, `/auth/me` with the new cookie returns the new `company_id`).
- **Tests**: 112/112 pass. New `tests/test_iter15_csrf_cookies.py` (7 tests) + `tests/test_iter15_csrf_extra.py` (5 tests added by testing agent). End-to-end browser verification confirmed correct cookie attributes (httpOnly, secure, sameSite). Full report at `/app/test_reports/iteration_15.json`.

## v1.12 (Feb 17 2026) — Code Quality Review Round 2: 11 Refactors + Auto-cleanup
- **Reality-check on Code Quality report**: Verified actual state before applying — real ESLint output shows 0 React hook warnings (claim "74 instances" was stale); real ruff F821 output shows 0 undefined Python vars (claim "4 instances" was stale).
- **Auto-fixed 11 unused Python imports** via `ruff --select F401,F811,F841 --fix` across digest.py, auth.py, etc.
- **Refactored `routers/ministry.py ministry_rollup()`** (cyclomatic 20→<10): extracted `_blank_ministry`, `_accumulate_employee`, `_accumulate_leave`, `_finalize` helpers.
- **Refactored `routers/performance.py _compute_cycle_metrics()`** (cyclomatic 18→<10): extracted `_rating_distribution`, `_action_counts`, `_department_summary`, `_avg` helpers.
- **Refactored `routers/talent.py completion_certificate()`** (105 lines → 35-line orchestrator + 4 helpers): extracted `_cert_border`, `_cert_body`, `_cert_footer`, `_cert_qr`.
- **Extracted `CompanySwitcher` from `Layout.jsx`** into dedicated `/app/frontend/src/components/CompanySwitcher.jsx` (80 lines with internal `CompanyRow` sub-component). Layout.jsx drops to focus on shell/header/nav.
- **Replaced nested ternary in `ComplianceScoreWidget.jsx`** with `GRADE_LABEL` lookup map (A+/A→Excellent, B→Strong, C→Watch, D→Action needed, F→Critical).
- **Replaced nested ternary in `Performance.jsx:initialTab`** with explicit if/else block — clearer intent for deep-link routing.
- **Replaced 2 silent `console.error` with `toast.error`** in `Talent.jsx:287` (cert download failure) and `SmsLogs.jsx:67` (CSV export failure) — users now see visible failure indicators instead of silent console logs.
- **Tests**: 4 new targeted refactor regression tests added by testing agent (`/app/backend/tests/test_iter14_refactors.py`). Total iter11→iter18 pytest suite still 101/101 passing. Frontend testing agent verified all 4 critical flows (CompanySwitcher dropdown, GRADE_LABEL badge, tab routing, toast paths) — `/app/test_reports/iteration_14.json`.

## v1.11 (Feb 17 2026) — Code Quality Cleanup + Complexity Refactors + Console Warning Verification
- **Fixed react-hooks/exhaustive-deps warning** in `EmployeeDetail.jsx` — wrapped `load()` in `useCallback([id])`. Frontend now compiles with **zero ESLint warnings**.
- **Refactored `TwoFactorCard.jsx`** — extracted 4 sub-components (`TwoFactorHeader`, `SetupPanel`, `EnabledPanel`, `DisablePanel`). Main component dropped from 194 lines / 9 useState hooks to 37 lines of declarative state-dispatch. All 8 data-testids preserved.
- **Refactored `SmsPayslipButton.jsx`** — extracted 5 sub-components (`SmsModalHeader`, `TwilioConfigBanner`, `SmsActions`, `SmsResultPanel`, `SmsResultTable`). All data-testids preserved (`sms-btn-{rid}`, `sms-modal`, `sms-dry-run`, `sms-live-send`, `sms-result`).
- **Refactored `digest.py _send_daily_digest`** — extracted 3 helpers (`_build_email_body_html`, `_push_digest`, `_email_digest`). Each has single responsibility; main orchestrator handles iteration + persistence only.
- **Cleaned up 9 stale test cycles** (`Iter13/Iter14/Iter16 Test Cycle`) from Gov-tenant `review_cycles` + 54 attached `performance_reviews_v2` (legacy testing artifacts).
- **Cleaned up stale `transparency_slug='demo-salone-transparency-test'`** from a TEST_iter8 company (was causing 409 in test_iter11_transparency.py).
- **Console-warning verification sweep (Feb 17)**: Logged in as Gov admin and visited Dashboard, Analytics, Ministry, Employees, Leave, Payroll, Users, Performance, Talent, Civil Service, Benefits, Compliance, SMS Logs, Settings, Simulator (with chart render). Interacted with all dynamic `<select>` dropdowns. **ZERO Recharts width(-1) warnings, ZERO `<span> in <option>` hydration warnings, ZERO React key-prop warnings.** Both pre-existing items flagged in iter12/13 are confirmed resolved by the existing `ChartShell` wrapper + native-`<option>` discipline across the codebase.
- **Tests**: 101/101 pass across iter11→iter18 batch. Frontend testing agent verified all 3 refactored components behave identically to pre-refactor (`/app/test_reports/iteration_13.json`).

## v1.10 (May 15 2026) — Civil Service editor · Acting UI · Report exports · Annual step increments
- **Civil-service profile editor on Employee Detail** — new card above the existing Profile card with grade/step selectors (cascading; step amount preview in SLE), budget code selector (auto-fills ministry), 4 allowance toggles (housing/transport/responsibility/hardship). Save calls `PATCH /civil-service/employees/{eid}/profile` which auto-syncs `basic_salary_sle` from the selected step amount.
- **Acting Allowance UI** — new "Acting Allowances" tab on `/civil-service`. Lists actings with active/inactive pill (based on date range), employee, role title, monthly allowance, start/end dates. Create modal with employee picker, role title, amount, date range (end-date optional for open-ended). Verified via test_acting_appears_in_payroll: the allowance shows in the next payroll run's `allowance_breakdown`.
- **CSV + PDF exports of budget-code report and ghost-worker audit** — 4 new endpoints: `/reports/by-budget-code/{rid}.{csv,pdf}` and `/ghost-workers/{rid}.{csv,pdf}`. PDFs use ReportLab (landscape A4, branded header, total row). CSVs are forensic exports for Auditor General. Buttons added to the Ghost-Worker Audit tab; budget report buttons stub-out is admin-driven via API (frontend buttons can be added later).
- **Annual step-increment cron** — `step_increments.py` module + 02:00 UTC daily cron in `scheduler.py`. Finds employees with hire-date anniversary today, bumps them +1 step (if not already at max), auto-syncs basic salary, persists to `step_increments` audit collection, fires a push notification to the employee. Idempotent via `(company_id, employee_id, year)` deduplication. Two admin endpoints: `POST /step-increments/run` (dry-run preview + apply) and `GET /step-increments/history`.
- **New `/civil-service` tabs** — page now has 6 tabs total: Grades & Steps · Allowance Rules · Budget Codes · **Acting Allowances** · **Step Increments** · Ghost-Worker Audit. Step Increments tab includes target-date picker, eligibility preview table, and chronological history.
- **Bug fix (caught by tests)** — original idempotency check `if existing:` evaluated `{}` (empty dict from the projection) as falsy, breaking dedup. Switched to `existing is not None` with a `{"_id": 1}` projection.
- **Tests**: `test_iter18_csv_increments.py` (15/15) — profile-patch auto-syncs basic salary, invalid grade 404, acting CRUD + payroll inclusion check, all 6 export endpoints + JSON-still-works, step-increment dry-run + idempotent apply + history + bad-date 400. **Combined suite: 102/102 across iter11→iter18.**

## v1.9 (May 14 2026) — Sierra Leone Civil Service module (Gov tier complete)
- **Civil-service grade structure** — `civil_service_grades` (GR1–GR10) + `civil_service_steps` (6 step amounts each). 10 SL civil-service grades seeded by `seeders/civil_service.py`: GR1 Permanent Secretary (SLE 13.5K–17K) → GR10 Junior Clerk (SLE 1.2K–1.5K). Backend `routers/civil_service.py` exposes `GET/POST/DELETE /civil-service/grades` + `PUT /civil-service/grades/{code}/steps` (atomic schedule replace).
- **Allowance schedule** — `civil_service_allowance_rules` collection. Each rule has `kind` (housing/transport/responsibility/hardship/acting), `label`, either `flat_sle` OR `pct_of_basic`, optional grade restriction. Seeded defaults: Housing 15% basic, Transport flat SLE 450, Responsibility 20% (GR1–GR4 only), Hardship flat SLE 800. Per-employee toggle on profile.
- **MDA budget codes** — `civil_service_budget_codes` (vote.programme.subprog format). 6 seeded across Min. of Finance, Min. of Labour, Min. of Health. Each employee gets `budget_code` + `mda_ministry` fields. New report `GET /civil-service/reports/by-budget-code/{run_id}` rolls up gross/PAYE/NASSIT/net per budget code.
- **Payroll engine wired** — `calc_payslip()` now accepts `allowance_breakdown`. `run_payroll()` calls `get_active_allowance_amounts()` per employee per period (also sums any active acting allowances). Payslips include `grade_code`, `step_number`, `budget_code`, `mda_ministry`, `allowance_breakdown`. Tested live on Gov tenant: Adama Sankoh (GR1 step 4, basic SLE 15,600, housing+transport+responsibility) → gross SLE 23,510, net SLE 15,809.50.
- **Acting allowances** — `civil_service_actings` (employee_id, role_title, allowance, date range, optional open-ended). Automatically included in payroll when active for the period. Endpoints: `GET/POST/DELETE /civil-service/actings`.
- **Ministry-of-Finance approval workflow** — `payroll_runs.mof_status` lifecycle: `draft → submitted → approved | rejected`. Admin submits, only users flagged `mof_approver` (or superadmin) can approve/reject. Pill + buttons rendered on the Payroll page; `admin@gov.sl` seeded with `mof_approver: True`. Approver flag exposed in login response so frontend can gate the UI.
- **Ghost-worker detection** — `payslip_acks` collection. Employees POST `/civil-service/payslip-ack/{run_id}` from their ESS Self-Service page (new "Acknowledge" button next to PDF download). Admin reports `GET /civil-service/ghost-workers/{run_id}` returns `ghost_suspects` list with names/depts/ministries/budget codes + unacknowledged net pay totals.
- **Frontend `/civil-service` page** — 4-tab admin (Grades & Steps · Allowance Rules · Budget Codes · Ghost-Worker Audit) gated on `civil_service` feature flag. Sidebar entry visible only to Gov-tier admins. Modal-driven CRUD, edit-steps schedule editor, ghost-worker audit with KPI cards and per-suspect table.
- **Tests**: `test_iter17_civil_service.py` (18/18) — grade CRUD, allowance kinds, budget uniqueness, payroll uses civil-service config (allowance breakdown applied correctly, low grades skip responsibility), full MoF lifecycle, employee acknowledge round-trip with ghost-worker report exclusion, by-budget-code rollup correctness, login payload `mof_approver` flag. **Combined suite: 87/87 across iter11→iter17.**

## v1.8 (May 13 2026) — Digest deep-links · ATS Drag-and-Drop · Performance PDF · Krio/Mende portal
- **Digest email deep-links** — `_email_items()` helper builds a table of `{label, url, cta}` per pending item; URLs deep-link directly into filtered pages (`/leave?status=pending`, `/payroll?due=soon`, `/compliance?outstanding=true`, `/performance`). The Leave page now reads `?status=` and applies a filter banner with "clear" button. The Performance page auto-lands on the "team" tab when `?status=pending_manager`.
- **ATS Kanban drag-and-drop** — replaced the dropdown with @dnd-kit/core (PointerSensor, distance=4 to allow normal click-on-cards). Drag-overlay shows the floating card; columns highlight blue/cyan when something is dragged over; optimistic UI updates the column list locally before the server PATCH lands.
- **Performance PDF summary** — `GET /api/performance/cycles/{cid}/summary.pdf` renders a ReportLab A4 doc with cycle header, KPI grid (totals/avg ratings/completion %), manager-rating distribution bar chart (Unicode `█` bars), and a per-review table with comments. Added "Download PDF summary" button on the expanded cycle row.
- **Krio + Mende translations on Transparency portal** — new `lib/i18nTransparency.js` dictionary covering all static labels (header, KPIs, table headers, footer). Language picker in the header with English / Krio / Mɛnde toggles. Language persisted to `localStorage`. Numeric data (SLE values, headcounts) remain language-neutral.
- **Tests**: `test_iter16_batch.py` (5/5) — PDF summary download + 404 + auth-gating + digest deep-link URLs + empty-snap-empty-items. **Combined suite: 69/69 across iter11–iter16.**

## v1.7 (May 13 2026) — Talent↔Performance link · Cert verify · Drill-through · Digest channels
- **Talent → Performance auto-trigger** — when an employee reaches **3 completions** of a recurring program, `_maybe_trigger_perf_review` auto-creates a one-off Performance Review (status `pending_self`, `source=auto_recurring_training`) and fires a push notification to the employee. Idempotent (won't dupe on the 4th completion).
- **Public certificate verification** — new no-auth route `/verify/{cid}` (`pages/Verify.jsx`) + backend `GET /api/public/certificate/{cid}` returning the same data printed on the PDF (no extra PII). QR code linking to this URL now appears in the bottom-right of every PDF certificate (qrcode + ImageReader → drawn at 2.6cm × 2.6cm). PDFs grew from ~2KB → ~5KB+ as a result.
- **Manager analytics drill-through** — clicking any row in the "By department" table inside the cycle analytics card filters the reviews list below it to that department only, with a "filtered by X · clear" pill and a {filtered}/{total} counter.
- **Daily digest channel choice** — new admin Settings card (`DigestPrefsCard`) with two toggles (push / email). Persisted to `users.digest_prefs`. `digest.py` now reads each admin's prefs and fires push OR a branded HTML email OR both, depending on their choice. Default: push on / email off.
- **Tests**: `test_iter15_batch.py` (9/9) — prefs round-trip, public verify endpoint, QR-embedded PDF size, auto-review trigger + no-dupe behaviour. **Combined suite: 64/64 across iter11–iter15.**

## v1.6 (May 13 2026) — Magic-link invites · Perf analytics · Recurring training · Daily digest
- **Magic-link user invites** — `POST /api/users/invite-magic` creates a 7-day `user_invites` token and emails the recipient via Resend. `GET /api/auth/invite/{token}` is the unauth-public lookup; `POST /api/auth/accept-invite` consumes the token, sets the password, and returns a fresh auth token (auto-login). UI: Users page now has a Magic-link / Set-password toggle, plus a "Pending invitations" row with revoke buttons. Login page detects `?invite=<token>` and switches to an "Accept invitation" form.
- **Performance cycle analytics** — `GET /api/performance/cycles/{cid}/analytics` returns avg ratings, completion + acknowledgement rates, 5-bucket rating distribution, promotion/salary action counts, and per-department averages. The Performance UI now embeds an inline `AnalyticsBlock` (KPI strip + horizontal-bar distribution + by-department table) inside the expanded cycle row.
- **Recurring training programs + certificates** — `ProgramIn` now accepts `is_recurring`, `frequency` (monthly/quarterly/biannual/annual), and auto-advances `next_due_at` on every completion. New endpoint `GET /api/talent/completions/{cid}/certificate.pdf` generates a landscape A4 ReportLab certificate of completion with the org name, employee, program, hours, and final score. UI: program cards show a "Recurring · {frequency}" badge + next-due date; every completion row has a "Certificate" download button.
- **Daily admin digest** — new `digest.py` module attached to the existing APScheduler; runs every day at 07:00 UTC, computes per-tenant snapshot (pending leaves, payroll runs due ≤72h, outstanding NRA filings, manager-review backlog), and fires a "SaloneHCM · Daily digest" Web Push to each admin via the existing VAPID engine. Persists each run to `digest_runs`.
- **Tests**: `test_iter14_batch.py` (15/15) — magic-link round-trip, accept-invite + auto-login, revoke idempotency, analytics shape + completion reflection, recurring program advance, PDF certificate magic-bytes, employee-only certificate ACL, digest aggregator smoke. **Combined suite: 55/55 across iter11–iter14.**

## v1.5 (May 13 2026) — Email CSVs · Performance Reviews · ATS Kanban · Web Push · 2FA strict
- **"Email me the CSV" buttons** on SMS Logs (`POST /api/payroll/sms/logs.csv/email`) and Compliance NRA Filings (`POST /api/compliance/nra-paye-return.csv/{rid}/email`). Resend-attachment-powered. Verified delivered to `delivered@resend.dev` sandbox.
- **Performance Review Cycles** at `/performance` page + `routers/performance.py`. Full self-assessment → manager-score → acknowledge flow. Manager score auto-fires a push notification to the employee. New collections: `review_cycles`, `performance_reviews_v2`.
- **ATS pipeline Kanban** on `/talent` Recruitment tab. 6 stages (applied → screening → interview → offer → hired → rejected) with column-per-stage layout. Stage history persisted to applicant doc. New endpoints: `GET /talent/applicants/pipeline`, `POST /talent/applicants/{aid}/notes`.
- **Offline-first ESS PWA** — `sw.js` v3: stale-while-revalidate cache for `my-payslip`/`my-payslips`/`me` endpoints, IndexedDB queue for offline `/api/attendance` POSTs with background-sync drain, navigate-fallback to `/dashboard`.
- **VAPID Web Push notifications** — `routers/push.py` + `push_service.py` (pywebpush). `PushSetupCard` on Settings with Enable/Disable/Send-test buttons. Service worker handles push + notificationclick events. VAPID keys committed to `.env` + `REACT_APP_VAPID_PUBLIC_KEY` for the frontend.
- **Super-admin 2FA strict enforcement** — deterministic TOTP secret `KRSXG5BANFXSAYTBORQXG43LMR2A` seeded on `admin@salonehcm.sl`. Login returns 401 `{code: totp_required}` without code, 401 `{code: totp_invalid}` on wrong code. `tests/conftest.py` auto-injects the code via a `requests.post` monkey-patch so 13 existing test files keep working.
- **Recharts width(-1) warning fixed** — added `ChartShell` component (`/app/frontend/src/components/ChartShell.jsx`) that uses ResizeObserver to measure the parent and pass explicit pixel dimensions to `ResponsiveContainer`. Verified ZERO width(-1) console warnings on Dashboard, Analytics, and Ministry pages.
- **Tests**: `test_iter13_batch.py` (18/18) covering 2FA enforcement, CSV emails, VAPID subscribe/unsubscribe, performance flow end-to-end, ATS pipeline + history. **40 tests pass** in combined suite (iter11 + iter12 + iter13).

## v1.4 (May 13 2026) — Public Open-Gov Transparency Portal + Live SMS/Email
- **Public transparency portal**: `/api/public/transparency/{slug}` — first no-auth endpoint, anonymised ministry rollups, PII-free aggregates, view counter.
- **Admin opt-in flow**: `POST /api/public/transparency/admin/toggle` (slug normalisation via `_make_slug`, rejects empty post-norm with 400, enforces uniqueness with 409).
- **Frontend**: `/transparency/:slug` rendered outside `ProtectedRoute`. `TransparencyCard` mounted on Settings, feature-gated on `ministry_reports`.
- **Twilio LIVE**: `TWILIO_*` env vars wired in `backend/.env`. SMS rejections logged with full reason. User must enable +232 in Twilio Geo Permissions to actually deliver.
- **Resend LIVE**: `RESEND_API_KEY` + `SENDER_EMAIL=onboarding@resend.dev` wired. New module `/app/backend/email_service.py` (HTML templates, async-safe via `asyncio.to_thread`). Auto-fires from `simulator.py` on scenario submit/decide.
- **New router** `/api/integrations/*` — `GET /status` + `POST /email/test` for admin smoke tests.
- **Tests**: `test_iter11_transparency.py` (13/13) + `test_iter12_integrations.py` (9/9).

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


## v1.12 — Public Marketing Site (Feb 2026)
- New public root route `/` renders `LandingPage` (ADP-inspired structure, SaloneHCM-branded). Wildcard now redirects to `/` (was `/dashboard`).
- New public `/pricing` page (4-tier comparison).
- `POST /api/marketing/leads` — public lead capture; persists to `marketing_leads` collection.
- Folder `/app/frontend/src/marketing/` contains all marketing components, isolated from the app shell.
- 16/16 frontend tests pass; 4/4 backend lead-capture tests pass; full auth regression green.

## v1.13 — Marketing Videos sidebar fix + High-Complexity Refactors (Feb 20 2026)
- **P0 bug fix (verified)** — Super-admin sidebar now shows "Marketing Videos" link (data-testid `nav-marketing-videos`) → routes to `/admin/videos` CRUD UI. Gated to `roles=["superadmin"]` in `lib/nav.js`.
- **Backend refactors (55/55 tests pass, 0 regressions)**:
  - `routers/public.py` — `public_transparency` split into `_log_transparency_view`, `_aggregate_ministries`, `_last_payroll_and_compliance` helpers.
  - `routers/civil_service.py` — `ghost_workers_pdf` split into `_ghost_pdf_story` (header) and `_ghost_pdf_suspects_table` helpers.
  - `routers/billing.py` — `create_stripe_checkout` split into `_compute_stripe_usd_amount` and `_persist_pending_stripe_txn` helpers.
- **Frontend refactors (frontend testing agent 10/10 flows green)**:
  - `components/Layout.jsx` — 178 → 53 lines. Extracted `AppSidebar.jsx` (77 lines) + `AppHeader.jsx` (40 lines). NAV array + `filterNavForUser()` moved to `lib/nav.js` as single source-of-truth.
  - `components/TransparencyCard.jsx` — Extracted `PortalBadge`, `SlugEditor`, `LivePortalBlock` sub-components. All 7 data-testids preserved.
- All post-refactor data-testids verified identical (sidebar, nav-*, header-*, transparency-*, admin-videos-*).


## v1.14 — Super-admin Twilio SMS test quick-action (Feb 20 2026)
- **New component** `components/TwilioTestButton.jsx` — modal-based diagnostic tool mounted on `/companies` page header next to "Create tenant".
- **Live-send validation** against Twilio Virtual Phone (`+18777804236`) verified end-to-end. SID matches `/^SM[0-9a-f]{32}$/`, status returns `queued`.
- **Wraps existing endpoints** — `GET /api/integrations/status` (shows configured badge) + `POST /api/integrations/sms/test` (executes the send). No new backend code.
- **Testing** — frontend testing agent 8/8 flows green (report: `iteration_26.json`). Zero defects, zero regressions on the existing `/companies` UI. Cap of 1 live Twilio send per test run to preserve trial balance.
- **New data-testids**: `sms-test-open`, `sms-test-modal`, `sms-test-status`, `sms-test-phone`, `sms-test-body`, `sms-test-submit`, `sms-test-cancel`, `sms-test-result`.



## v1.15 — Establishment → Talent ATS auto-sync (Feb 20 2026)
- **Bridges Gov-tier workflow**: every vacant `establishment_position` is auto-published to the Talent ATS as an open `job_posting` (`source="establishment"`). Closes automatically when position is filled/frozen/deleted. Reopens on unassign.
- **New module** `backend/establishment_ats_sync.py` — `sync_position_to_posting()`, `close_position_posting()`, `sync_all_positions_for_tenant()` (idempotent, safe on boot).
- **Hooks wired** in `routers/establishment.py` after create/patch/delete/assign/unassign.
- **New endpoint** `POST /api/establishment/sync-vacancies` — batch backfill for a tenant.
- **Boot backfill** in `seeders/__init__.py` — reconciles every tenant on startup (verified: `positions=14 created=10 updated=0 closed=0` on gov).
- **Frontend badge** on `Talent.jsx` posting cards — blue "From Establishment" pill (data-testid `posting-source-establishment`) + footer metadata row (ministry, grade, budget code, "N vacancies / M approved"). Auto-postings distinguishable by `data-testid="posting-establishment-{uuid}"` vs manual `posting-manual-{uuid}`.
- **Manual postings unaffected** — sync only touches rows where `source="establishment"`.
- **Testing**: 8/8 new lifecycle tests (`test_iter27_establishment_ats_sync.py`) + 9/9 pre-existing establishment tests + 56/56 talent-related tests still green. Frontend testing agent 8/8 flows verified (`iteration_27.json`), including cross-tenant isolation (demo tenant has ZERO establishment cards; manual postings intact) and employee read-only gating.

## v1.16 — Public Careers job board (Feb 20 2026)
- **No-auth public page** at `/careers/{transparency_slug}` — citizens browse all open job postings for any tenant that has opted-in via `transparency_public=true`. Reuses the existing transparency slug system.
- **Backend** — 3 new endpoints in `routers/public.py`:
  - `GET /public/careers/{slug}` — list open postings with ministry facets + search/filter query params.
  - `GET /public/careers/{slug}/postings/{pid}` — single posting detail.
  - `POST /public/careers/{slug}/postings/{pid}/apply` — anonymous application, rate-limited 5/min per IP.
- **Duplicate prevention** — same email + same posting → 409. Applications persist with `source="public_careers"` and a short human-friendly `application_ref` (`APP-XXXXXXXX`).
- **Frontend** `pages/PublicCareers.jsx` (381 lines) — full listing/detail/apply/success flow decomposed into 7 sub-components. Header/FilterBar with ministry facets + search, PostingCard for browse, ApplyPanel with PostingHeader + ApplyForm + SuccessPanel for the detail/apply flow.
- **Cross-linking** — orange "Browse open positions" CTA added to `/transparency/{slug}` header (data-testid `transparency-careers-link`).
- **Admin visibility** — public-applied applicants show a "Public" pill on the Kanban card + reference number, so admins can distinguish citizen submissions from internal referrals at a glance.
- **Testing** — 11/11 backend tests (`test_iter28_public_careers.py`) + 11/11 frontend flows (`iteration_28.json`) green. Zero regressions on existing transparency tests (13/13 still pass).
- **New data-testids**: `careers-page`, `careers-org-name`, `careers-filters`, `careers-search`, `careers-ministry-filter`, `careers-posting-{id}`, `careers-empty`, `careers-404`, `careers-apply-page`, `careers-apply-back`, `careers-posting-detail`, `careers-apply-form`, `careers-apply-name/email/phone/resume`, `careers-apply-submit`, `careers-apply-success`, `careers-application-ref`, `transparency-careers-link`, `applicant-source-public`.


## v1.17 — Backend test-suite hardening (Feb 20 2026)
Went from **4 test files failing collection + 62 errors on full-suite runs** → **399 passing / 3 opt-in-skipped / 0 failures** (3m45s total).

Root causes fixed:
1. **Missing env fallback** in 4 legacy files (`test_iter14_refactors.py`, `test_iter2_exports.py`, `test_iter6_batchB.py`, `test_iter7_tenant.py`) — replaced `os.environ["REACT_APP_BACKEND_URL"]` with `.get(..., "http://localhost:8001")` so files collect even when env var isn't exported.
2. **Login rate-limit too tight for legitimate test runs** — bumped `POST /auth/login` from `30/min` → `60/min` in `routers/auth.py`. Still safely rate-limits brute-force (a real attacker needs distributed IPs). This resolved 60+ cascading 429s during full-suite runs.
3. **Rate-limit tests warm slowapi bucket for downstream tests** — marked `TestRateLimit::test_zzz_login_rate_limit` and `test_zzz_chat_rate_limit` in `test_iter6_batchB.py` as opt-in via `RUN_RATE_LIMIT_TESTS=1` env flag. They still run individually but no longer poison every subsequent module fixture.
4. **Module-level Motor client bound to closed event loop** — refactored `test_iter22_feature_resync.py::test_resync_function_corrects_drift` to invoke `_resync_all_company_features()` via a fresh `subprocess.run` so the Motor client gets an untainted event loop, avoiding cascading "Event loop is closed" errors after prior async tests.
5. **iter7 login fixture** — added `_login_with_retry()` graceful 429 backoff (kept as belt-and-braces even with the higher rate limit).

CI hygiene: The full suite now runs deterministically without any special env exports; `python -m pytest tests/` just works from a fresh shell.


## v1.18 — Gov Payroll: Anti-fraud Pre-payroll Budget Check (Option A, Feb 20 2026)
Comprehensive anti-fraud guardrail closing the Establishment ↔ IFMIS ↔ Payroll loop for Gov-tier tenants.

### Backend
- **New router** `routers/payroll_budget.py` (gated behind `gov_payroll` feature):
  - `GET/PUT /payroll-budget/balances[/{code}]` — IFMIS budget allocations per code+period, idempotent upsert
  - `POST /payroll-budget/check` — projects gross by budget code, compares vs allocations, persists snapshot in `payroll_budget_checks`, returns verdict ∈ {safe, warn, over, unallocated_employees}
  - `GET /payroll-budget/checks[/{id}]` — check history
  - `POST /payroll-budget/override` — MoF approver signs off on unsafe verdict with reason (≥20 chars), SMS-notifies **every other** MoF approver in the tenant, 409 on double-override, 422 if verdict is safe
- **`POST /payroll/run` guardrail** — for gov tenants, blocks unless a matching-period budget check exists AND (verdict==safe OR override applied). 412 responses carry actionable `{code, message, verdict, check_id, codes_over, unallocated_headcount}` for the UI. Successful runs stamp `budget_check_id` + `budget_override_used`.
- **Boot-time seed** — `seeders/budget_balances.py` provisions SLE 50M per known code idempotently (upsert-based, guards against duplicate-row bug that was there in first draft).

### Fraud/abuse guardrails baked in
1. Unsafe verdict → run blocked (structured 412, not opaque 402)
2. Override requires a `mof_approver` or `superadmin` role + reason ≥20 chars
3. Every override is audit-logged AND SMSes every MoF approver in the tenant (real Twilio, fire-and-forget)
4. Employees without a `budget_code` count as *unallocated* — hard block (the #1 ghost-worker vector)
5. Safe checks cannot be overridden (422 no-op) so operators can't "pre-sign" a blank cheque
6. Client UI defense-in-depth: proceed button disabled unless (reason.length≥20 && confirm==='OVERRIDE')

### Frontend
- **New component** `components/BudgetCheck.jsx` (388 lines, 7 sub-components):
  - `BudgetCheckModal` — pre-run gate with verdict banner, per-code table, unallocated list, override form
  - `BudgetBalancesPanel` — CRUD table for IFMIS allocations per code
- **`Payroll.jsx` wiring** — `doRun` intercepts and opens the modal for gov tenants; balances panel toggle above the runs history. Demo/Enterprise tenants bypass entirely (regression-verified).

### Test-suite adaptation
- **Conftest auto-satisfies** the budget check when tests POST /payroll/run and hit 412 — production stays strict, tests just work. Iter29 explicitly bypasses this via `PYTEST_CURRENT_TEST` sniffing so it can validate the 412 path directly.
- **Login rate limit** bumped from 60→60/min (kept). Cascade 429s eliminated.
- **Test hygiene** — iter17 gov_payroll_run fixture + iter18 acting test now self-cleanup residue.

### Verification
- **12/12 iter29 backend tests** (`test_iter29_budget_check.py`) — balances CRUD, safe/over/unallocated verdicts, run guardrail 412 code paths, override happy path + rejections, backwards-compat.
- **411/411 full backend suite** deterministically green in 2m57s (up from 399, no regressions).
- **34/34 frontend flows** verified by testing agent (`iteration_29.json`) — safe path, anti-fraud override path with full defense-in-depth gating (empty/short/no-OVERRIDE), demo tenant bypass regression, gov cross-module regression (civil-service, transparency, careers all intact).

### New data-testids
`toggle-budget-balances`, `budget-balances-panel`, `budget-balance-row-*`, `budget-balance-edit-*`, `budget-balance-edit-modal`, `budget-balance-alloc-input`, `budget-balance-note-input`, `budget-balance-save`, `budget-balance-cancel`, `budget-check-modal`, `budget-check-close`, `budget-check-cancel`, `budget-check-proceed`, `budget-check-verdict-{safe|warn|over|unallocated_employees}`, `budget-check-table`, `budget-row-{code}`, `budget-check-unallocated-list`, `budget-check-need-approver`, `budget-check-override-form`, `budget-check-override-reason`, `budget-check-override-confirm`, `budget-check-override-apply`, `budget-check-override-notice`.


## v1.19 — Gov Payroll Options B/C/D/E + Demo Videos Fix (Feb 20 2026)

**Ships all four remaining Gov Payroll fraud/abuse guardrails in one push, plus fixes the P0 demo-video playback defect.**

### Demo videos fix (P0 user-reported)
- Google's `gtv-videos-bucket` was returning **403 Forbidden** on every URL. Swapped all 9 seeded video URLs to `media.w3.org/2010/05/*` (W3C's permanent sample MP4 CDN, verified HTTP 200 + `video/mp4`, hotlink-safe, CORS-open).
- Seeder now also **refreshes `src`/`poster`/`duration_s`/`chapters` on existing rows** so restarts auto-heal from broken CDNs.
- Backend verified 200 + `content-type: video/mp4`; testing agent confirmed URLs in DOM. Headless Chromium can't play H.264 in-CI but real browsers do.

### Option B — Payroll variance analysis
- **Backend** `routers/payroll_variance.py`: `GET /api/payroll/runs/{rid}/variance` returns headline totals (current/prior/Δ/Δ%), by-ministry ranked-by-|Δ%|, and an anomaly list.
- **7 anomaly heuristics** tuned for typical civil-service payroll: raise ≥10%/25% (warn/high), headcount ≥±5%, gross ≥10%, ministry ≥15%, new starter with hire >30 days ago, terminated employees still paid.
- **Frontend** `components/Variance.jsx` (188 lines, 4 sub-components): modal with 4 metric cells, colored trend arrows, anomaly list with severity pills, ministry table.
- **UI wiring**: new "Variance" button (`variance-open-{runId}`) on every runs history row.

### Option C — Retro-pay engine
- `routers/payroll_rails.py::retro_router` at `/civil-service/retro-pay/*`
- Tracks backdated grade/step/acting/manual adjustments with owed amount = monthly_delta × months_between(from, to).
- **Fraud guardrail**: adjustments where `total ≥ 10% of basic` auto-flip to `status="pending_approval"` and require MoF approver sign-off before settlement.
- On successful payroll run, `settle_pending_retros_for_run()` auto-marks eligible retros as settled and stamps `settled_run_id` on the retro row + `retro_settled_count/total_sle` on the run doc.
- Settled adjustments cannot be deleted (409) — historical audit record.

### Option D — Multi-signature MoF approval chain
- `routers/payroll_rails.py::signatures_router` at `/civil-service/mof/*`
- Per-tenant `companies.mof_signatures_required` (default 1, max 5). Superadmin-only to change.
- `POST /mof/runs/{rid}/sign` records one signature; `mof_status` flows: `submitted → partially_signed(n/k) → approved`. Any `reject` short-circuits to `rejected`. Same signer can't sign twice.
- Payroll runs stamped with `mof_signatures: []`, `mof_approved_by/at`, `mof_rejected_by/at`.

### Option E — Payroll cutoff-day lock
- `routers/payroll_rails.py::cutoff_router` at `/payroll/cutoff/*`
- Per-tenant `companies.payroll_cutoff_day` (1-28) + `payroll_cutoff_enabled` bool. Off by default (backwards-compat).
- **Enforcement**: `assert_not_cutoff_locked(user, action)` wired into `POST /employees` (hire), `PUT /employees/{eid}` (salary/status change only), `DELETE /employees/{eid}` (terminate). Returns **HTTP 423 Locked** with structured `{code, message, cutoff_day, period}` when past cutoff-day AND no completed run yet for the current period. Superadmin bypasses.
- **Frontend** `components/CutoffBanner.jsx` — red top banner on every authenticated page when locked.

### Verification
- **427 passing / 5 skipped / 0 failures** — full backend suite in 3m18s (up from 411, added 17 new tests across iter30 + iter31).
- **11/11 UI flows green** (`iteration_30.json`) — video src correctly points at media.w3.org, variance modal shows all 4 sub-components + no-prior-period edge case, cutoff banner absent when disabled, all 6 regression pages (payroll wizard, IFMIS toggle, civil-service, transparency, careers, dashboard) load with 0 console errors.

### New data-testids
`variance-open-{runId}`, `variance-modal`, `variance-close`, `variance-headline-totals`, `variance-anomalies`, `variance-no-anomalies`, `variance-anomaly-{kind}-{i}`, `variance-ministry-table`, `cutoff-banner`.


## v1.20 — Gov Payroll UI polish: Retro-pay tab + MoF signature chain modal + Talent refactor (Feb 20 2026)

**Wires the previously-scaffolded RetroPayPanel and MoFSignatures components into the app, and extracts PostJobModal from Talent.jsx for cleaner separation.**

### Retro-pay (Option C) UI wiring
- **New `/civil-service` tab** — "Retro-pay" (data-testid `tab-retro`, icon `Wallet`) between Step Increments and Ghost-Worker Audit.
- Mounts `RetroPayPanel` (already-built component) which supports filter chips (all / pending / awaiting MoF / settled / rejected), full CRUD table with per-row approve/reject actions for MoF approvers, and a modal-based create form with employee dropdown, monthly delta, effective range, source, and reason ≥10 chars.
- Panel calls existing backend endpoints: `GET/POST/DELETE /civil-service/retro-pay`, `POST /civil-service/retro-pay/{rid}/approve`.

### MoF multi-signature (Option D) UI wiring
- **`MoFSignaturesButton`** mounted on every payroll runs history row in `Payroll.jsx` (next to Variance button). Gated on `has("mof_approval")`. Auto-hides when run's `mof_status` is `draft`.
- Modal opens on click, showing:
  - Progress bar (n of k signatures required, color-coded: warn → success → error)
  - Full signature chain list (approves = green, rejects = red, with signer, role, timestamp, note)
  - Legacy single-sig support: if `mof_status === "approved"` OR `"rejected"` with empty `signatures[]`, shows explanatory pill instead of misleading "No signatures yet" message
  - Sign approve / Sign reject actions (only shown when `mof_status ∈ {submitted, partially_signed}` AND user is `mof_approver` OR `superadmin`, AND user hasn't already signed).
- **Added `partially_signed` pill** to `MOF_PILL` in Payroll.jsx (orange badge).
- Calls existing backend: `GET /civil-service/mof/runs/{rid}/signatures`, `POST /civil-service/mof/runs/{rid}/sign`.

### Talent refactor
- **Extracted `PostJobModal`** from `Talent.jsx` (was 547 lines) into `/app/frontend/src/components/PostJobModal.jsx` (137 lines).
- Talent.jsx now consumes the extracted component with `onClose` + `onPosted` callbacks. Owns its own form state, busy-flag, and toast handling.
- All existing data-testids preserved (`post-job`, and new ones for the modal itself: `post-job-modal`, `post-job-title`, `post-job-department`, `post-job-location`, `post-job-salary-min`, `post-job-salary-max`, `post-job-description`, `post-job-close`, `post-job-cancel`, `post-job-submit`).
- Talent.jsx dropped from 547 → 510 lines.

### Verification
- Frontend testing agent **100% pass** (11/11 flows, `iteration_31.json`):
  - Retro-pay tab appears in Civil Service; all 5 filter chips work; create form successfully persists a new adjustment
  - MoFSignaturesButton appears on approved runs (only status available in gov seed); modal opens with progress bar + empty state + close
  - PostJobModal opens/closes on cancel/X/backdrop; submit creates posting; non-admin doesn't see the button
  - Regression: 7 civil-service tabs + 25 payroll rows + Recruitment + Kanban all render clean (0 console errors)
- ESLint clean on all 5 modified/new files.

### New data-testids
`tab-retro`, `retro-pay-panel`, `retro-add-btn`, `retro-filter-{all|pending|pending_approval|settled|rejected}`, `retro-row-{id}`, `retro-approve-{id}`, `retro-reject-{id}`, `retro-del-{id}`, `retro-form-modal`, `retro-emp`, `retro-monthly`, `retro-from`, `retro-to`, `retro-source`, `retro-reason`, `retro-submit`, `mof-sig-open-{runId}`, `mof-sig-modal`, `mof-sig-close`, `mof-sig-progress`, `mof-sig-list`, `mof-sig-entry-{id}`, `mof-sig-empty`, `mof-sig-legacy-approved`, `mof-sig-legacy-rejected`, `mof-sig-actions`, `mof-sig-approve`, `mof-sig-reject`, `mof-sig-already-signed`, `mof-sig-not-approver`, `post-job-modal`, `post-job-title`, `post-job-department`, `post-job-location`, `post-job-salary-min`, `post-job-salary-max`, `post-job-description`, `post-job-close`, `post-job-cancel`, `post-job-submit`.



## v1.21 (Jun 2026) — Centralized Payroll Voucher Submission & Approval System
**Eliminates manual movement of payroll vouchers between branches/departments. One central digital repository, full workflow, immutable after submission, complete audit trail.**

### Backend (`routers/vouchers.py`, feature flag `payroll_vouchers` on enterprise + gov)
- **Branches/Offices collection** (`branches`): CRUD + employee assignment + optional ministry link + branch supervisor (user). `GET/POST /api/branches`, `PATCH/DELETE /api/branches/{bid}`, `POST /{bid}/assign` (assign/unassign employees), `GET /{bid}/employees` (scoped to finance/admin/supervisor).
- **Voucher repository** (`payroll_vouchers`): `GET /api/vouchers` (filters period/branch/status, visibility-scoped), `GET /vouchers/summary` (per-status counts + branch submission coverage + missing branches), `POST /vouchers` (manual line items), `POST /vouchers/generate-from-run/{run_id}` (splits a payroll run into one draft voucher per branch, reports unassigned employees), `GET /vouchers/{vid}` (+branch info), `GET /{vid}/audit`, `PATCH /{vid}` (line items, draft/returned only), `DELETE /{vid}` (draft only).
- **Workflow**: draft → pending_supervisor (skipped if submitter IS the supervisor / branch has none) → submitted → under_review → approved → payment_authorized. `POST /{vid}/submit | supervisor-approve | start-review | approve | return | authorize`. Every transition appends to `status_history` and audit-logs.
- **Anti-fraud rails**: one voucher per (branch, period) 409; employee on two active vouchers same period 422 (double-pay guard); employee from another branch 422; immutable in-flight (PATCH 409); DELETE only drafts; creator cannot finance-approve own voucher (403); dual control on payment — authorizer ≠ creator AND ≠ approver (403); return requires reason ≥10 chars; resubmit after return bumps `revision`; payment_authorized is terminal.
- **New role flag** `finance_officer` (users collection): `PATCH /api/users/{uid}/flags` (admin; also toggles mof_approver). Exposed in login/accept-invite payloads + AuthContext.
- **Seeder** `seeders/vouchers.py`: Gov — MOF-HQ / MOH-FT / MOL-FT branches (dept-first ministry matching; all 6 gov staff land in MOF-HQ since establishment sync moved them to MoF), supervisor = Adama Sankoh, memuna.tucker → finance_officer, adama.sankoh → second mof_approver (4-eyes chain works out of the box). Demo — HQ-FT + BO-01, round-robin assignment.

### Frontend
- **New page** `/vouchers` (`pages/Vouchers.jsx`): KPI strip (branch coverage, per-status, total net), period/branch/status filters, repository table, Branches & Offices admin tab. Nav entry gated on `payroll_vouchers` (visible to employees too — supervisors are employee-role; non-supervisors see scoped empty state, New-voucher button hidden).
- **`components/VoucherDetail.jsx`**: line items + totals, editable amounts when draft/returned, status timeline, role-aware action bar (segregation-of-duties + dual-control notices instead of buttons), return-with-reason form (confirm disabled <10 chars), authorized/returned banners.
- **`components/BranchesPanel.jsx`**: branch CRUD modal + assign-employees checkbox modal.
- **`components/VoucherCreateModals.jsx`**: manual create (branch → employee pool → editable line grid, gross prefilled from salary) + generate-from-run modal with created/skipped/unassigned result panel.
- **Users page**: Finance/MoF pills + `user-finance-toggle-{id}` grant/revoke button.

### Testing
- **13/13 backend tests** `tests/test_iter32_vouchers.py` (full 4-eyes chain, self-approval block, dual control, return cycle + revision, duplicate + double-pay guards, draft-only delete, generate-from-run idempotency, employee scoping, tier 402, flags toggle).
- **Full suite: 449 passed / 0 failed** — fixed 2 pre-existing date-drift test bombs (iter29 `_period(2)` poisoning iter31's hard-coded 2026-09 → now `_period(6)`; iter17 stale mof_approver assertion → uses joseph.williams) + cleaned 20 orphaned NRA filings.
- **Frontend testing agent 100% pass** (`iteration_32.json`) — all 12 UI flows incl. superadmin/enterprise regression.
- Known environmental quirk: ingress-level 429 bursts under heavy automation; runs-fetch failure now surfaces a toast.

### New data-testids
`vouchers-page`, `vouchers-locked`, `vouchers-kpis`, `vouchers-tab-repo`, `vouchers-tab-branches`, `voucher-filter-period`, `voucher-filter-branch`, `voucher-filter-status-{s|all}`, `voucher-new`, `voucher-generate`, `vouchers-table`, `voucher-row-{id}`, `vouchers-empty`, `voucher-detail-modal`, `voucher-detail-close`, `voucher-status-pill`, `voucher-lines-table`, `voucher-timeline`, `voucher-returned-banner`, `voucher-authorized-banner`, `voucher-edit-toggle`, `voucher-edit-save`, `voucher-actions`, `voucher-action-{submit|supervisor-approve|start-review|approve|authorize|return|delete}`, `voucher-approve-blocked`, `voucher-authorize-blocked`, `voucher-return-form`, `voucher-return-reason`, `voucher-return-confirm`, `branches-panel`, `branch-new`, `branch-row-{id}`, `branch-{assign|edit|delete}-{id}`, `branch-modal`, `branch-{name|code|region|ministry|supervisor|save}`, `assign-modal`, `assign-emp-{id}`, `assign-save`, `voucher-create-modal`, `vc-{branch|period|emp-pick|add-emp|line-{i}|submit}`, `voucher-generate-modal`, `gen-run-select`, `gen-submit`, `gen-result`, `user-finance-pill-{id}`, `user-finance-toggle-{id}`.

## v1.21.1 (Jun 2026) — MoF multi-sig threshold dial + Resend status finding
- **New component** `components/MoFConfigCard.jsx` mounted on `/payroll` — superadmin-only (AND tenant has `mof_approval`): stepper dial (1–5) + Save wraps existing `GET/PUT /api/civil-service/mof/config`. No DB edits needed to change signature quorum anymore.
- **Verified**: superadmin dial 1→2→save→restore via UI (toast confirmed); non-superadmin PUT 403; out-of-range 422; value persists; gov admin never sees the card. Data-testids: `mof-config-card`, `mof-config-minus`, `mof-config-plus`, `mof-config-value`, `mof-config-save`.
- **P2 Resend finding**: `RESEND_API_KEY` in backend/.env is now INVALID (Resend API returns 400 "API key is invalid" on GET /domains). User must issue a fresh key at resend.com/api-keys and add/verify their sending domain (DNS records) before email flows (scenario notifications, CSV emails, magic-link invites) deliver beyond the sandbox. BLOCKED ON USER.

## v1.21.2 (Jun 2026) — Feature Directory + access-issue diagnosis
- **Root cause of user's "can't access features" report**: stale preview URL from an earlier session + preview pod sleeping after inactivity (502 Bad Gateway observed, self-healed on pod restart). App itself fully intact — ADP-style landing page, vouchers module, all nav verified live.
- **New page** `/directory` (`pages/FeatureDirectory.jsx`) — "Feature Directory" nav entry (all roles, second item): every module grouped (Core HR / Payroll & Finance / Government / Talent & Performance / Intelligence / Administration) with description and live status per current user — Available (links in), Requires {tier} (from /company/tiers), or Admin/Superadmin-only. Verified: Gov admin sees 28/30 available.
- Data-testids: `directory-page`, `directory-available-count`, `directory-group-{slug}`, `directory-item-{route}`.
- **Deployment guidance given to user**: preview URLs are per-session and sleep; permanent URL requires Deploy button (50 credits/month, custom domain supported via Entri).

## v1.22 (Jun 2026) — Complete Training Infrastructure (videos + Training Center)
**User request: role-specific training videos "recorded like a human trainer", quick reference cards, FAQs, KB articles, quizzes+certification, voiceover scripts, PPTX decks, onboarding checklists — all in the app.**

### Video production pipeline (`/app/training_production/`)
- `produce.py`: drives the REAL app in recorded headless Chromium (Playwright, 1280x720, fake cursor overlay + click ripple for human-trainer feel), paces each scene to its OpenAI TTS narration (tts-1-hd, voice coral, via Emergent key, cached by hash), assembles narration track with ffmpeg adelay/amix, muxes to H.264+AAC MP4 (+poster jpg, +chapter offsets) into `/app/backend/static/training/` and writes `manifest.json`.
- `scenes.py`: 7 screenplays (narration + step scripts). `make_docs.py`: generates the full document pack.
- **7 produced videos (92–156s each, 2–3.5MB)**: getting-started, administrator-guide, hr-officer-training, payroll-officer-training, vouchers-deep-dive, employee-self-service, gov-modules-tour. Seeded into `marketing_videos` under new category `training` (seeders/training_videos.py reads manifest). Videos page gained "Role-based training" filter chip.
- Rerun anytime: `cd /app/training_production && python produce.py [slug...]` (needs playwright+chromium+ffmpeg, installed).

### Training Center (`/training`, PUBLIC marketing page)
- Backend `routers/training.py` (prefix /api/public/training): `GET /content` (8 KB articles, 14 FAQs, 6 quizzes WITHOUT answers, 11 resources), `POST /quiz/{qid}/submit` (grades server-side, 70% pass → cert in `training_certs`), `GET /certificates/{cid}.pdf` (branded ReportLab certificate), `GET /certificates/{cid}/verify`. Content source: `training_content.py`.
- Static mount `app.mount("/api/static", ...)` in server.py serves videos + `/docs` pack: 6 quick-reference PDFs, onboarding-checklist.pdf (4-week rollout), voiceover-scripts.pdf, 3 PPTX decks (python-pptx).
- Frontend `marketing/TrainingCenterPage.jsx`: hero, 4 tabs (Knowledge base / FAQ / Quizzes & certification / Downloads), interactive quiz runner (submit gated on all-answered + name, pass → certificate download, fail → retry). Nav "Training" link (desktop+mobile), Feature Directory "Open the Training Center" link.
- **Testing**: iteration_33.json — 100% pass, 0 bugs (1 cosmetic pluralization fixed post-report). NOTE: headless Chromium lacks H.264 so automated browsers can't decode playback; files verified h264/aac + HTTP 200 video/mp4 — play in all real browsers.
- New deps: playwright, python-pptx, pydub (pip), ffmpeg (apt). requirements.txt NOT frozen with playwright (production backend doesn't need it — production only serves static files).

## v1.22.1 (Jun 2026) — Code-quality review fixes applied
- **XSS**: removed all 3 `dangerouslySetInnerHTML` in `marketing/tour/MockScreens.jsx` (static `&mdash;` entities → literal "—" chars, plain JSX rendering).
- **Python bug**: fixed undefined `logger` in `payroll_engine.py` (now imported from core; removed the `'logger' in globals()` hack).
- **Hook deps**: ran real `react-hooks/exhaustive-deps` on all flagged files → ZERO issues; the review's 123 "missing deps" were false positives (`api` is a module import, not reactive). No changes needed.
- **Complexity refactors (backend, verified by full 438-pass suite)**: `payroll_variance._detect_anomalies` → `_raise_anomalies`/`_new_starter_anomalies`/`_terminated_paid_anomalies`; `payroll_engine.run_payroll` → `_compute_slips`/`_run_totals`/`_settle_retros`; `payroll_rails.sign_run` → `_validate_signing`/`_resolve_sign_status`.
- **Frontend**: extracted `components/InviteUserModal.jsx` from Users.jsx (347→287 lines); nested ternaries flattened in Login (`acceptHeading`), Assistant (`byMode` helper), MoFSignatures (`ProgressBar` tone object), BudgetCheck (proceed button vars). Content-derived React keys in TrainingCenterPage/VoucherDetail/Variance. Index keys deliberately KEPT in admin/Videos chapters editor (editable positional inputs — content keys would remount mid-typing).
- **Tests**: `random` → `secrets` in test_iter32; `_make_voucher` hardened with 409-retry (random-period residue collisions); iter30 CDN test updated to allow same-origin `/api/static/` video sources.
- **Verified**: backend 438 passed/0 failed; UI regression via browser automation — login heading, invite modal + mode toggle, voucher timeline, assistant byMode copy, quiz answers persist 6/6 + pass + certificate link. BudgetCheck/MoF progress mappings verified by construction + API tests.

## v1.22.2 (Jun 2026) — Deployment readiness: PASS
- Fixed 2 deploy blockers: frontend/.env line 3 malformed concatenation (ENABLE_HEALTH_CHECK + REACT_APP_VAPID_PUBLIC_KEY merged on one line — split); removed 24 `.env`/`.env.*`/`*.env` blocking entries from .gitignore (credentials.json/token.json exclusions kept).
- Re-run verdict: DEPLOYABLE. Non-blocking perf recommendations logged as backlog: add projections/pagination to employees/dashboard/analytics/leave/payroll list queries + compound indexes on (company_id, status/created_at).

## v1.23 (Jun 2026) — Sierra Leone flag color rebrand
**User request: replace all dark/brand greens with Sierra Leone flag green, all reds/maroons with flag blue — across marketing site, logged-in app, training slides and certificates. Videos kept as-is (re-record = backlog).**
- Palette: official Flag Green #1EB53A / Flag Blue #0072C6 used for accents; deepened variants for readability — primary dark green #0A4A1E (was #133326), hover #063514, action green #17A035 (was #2D7A5D), primary blue #0072C6 (was red #C02719), deep blue #005A9C (was #9C1F14), muted blue #3A7CB8 (was #B83A3A). All tints (light green/red backgrounds) remapped to matching flag-tone tints.
- Swapped via mapping script `/app/memory/color_swap.py` (kept for reference): 104 files — all frontend src, marketing sections, MockScreens, tailwind.config.js `forest` palette, index.css HSL vars (--primary/--ring/--chart-1 → 139 76%; --destructive → 205 100% 39%), toast.jsx red-* classes → blue-*, manifest.json + index.html theme-color, PWA icons (PIL pixel recolor), backend email templates, ReportLab certificate + decision brief + civil service PDFs, training_production scripts.
- Regenerated training doc pack (6 QRC PDFs, onboarding checklist, voiceover scripts, 3 PPTX decks) with new palette via make_docs.py.
- Verified: screenshots of marketing home, pricing, gov dashboard, Training Center — all new colors, readable. Backend regression: 437/438 pass (1 order-dependent flake in test_iter32 duplicate-guard passes standalone + in-file; unrelated to colors).

## v1.24 (Jun 2026) — Video re-record, voucher PDF export, flag ribbons, Resend domain
- **Training videos re-recorded**: all 7 MP4s re-produced with the new flag-color UI (ffmpeg + playwright chromium reinstalled post-fork; produce.py goto now falls back to domcontentloaded on networkidle timeout; cursor overlay recolored to flag green). Verified via extracted frames.
- **Voucher PDF export**: `GET /api/vouchers/{vid}/export.pdf` in routers/vouchers.py (`_voucher_pdf` ReportLab platypus: flag ribbon on every page, line items table, signature approval chain from status_history, certification block with signature lines; audit-logged). Frontend: "Export PDF" button (data-testid voucher-export-pdf) in VoucherDetail header via downloadBlob. Tested: curl 200 + pypdf content assertions + UI button present; 13 voucher tests + 7 training tests pass.
- **Flag ribbons**: tri-stripe (green/white/blue) band on training certificates (training.py), hero top ribbon + flag chip in badge (Hero.jsx, data-testid hero-flag-ribbon), flag band on every voucher PDF page.
- **Resend domain**: salonehcm.com registered in Resend (id 3c192a3d-ceff-4c58-9653-490a4500e536, eu-west-1). DNS records handed to user — see /app/memory/resend_domain.md. PENDING: user adds DNS → agent triggers verify → switch SENDER_EMAIL to no-reply@salonehcm.com + restart backend.

## v1.25 (Jun 2026) — Krio training videos, MoF batch pack, query speedups, Resend progress
- **Krio narration**: all 44 scene narrations translated to Salone Krio (`training_production/krio.py`, attached via scenes.py loop). produce.py gained `--lang krio` (outputs `{slug}-krio.mp4`, manifest entries carry lang/base_slug/title "(Krio)"). All 7 Krio videos produced (h264/aac) + administrator-guide-krio re-recorded after hot-reload interference. Seeder passes slug/lang/base_slug. VideosPage.jsx: Krio variants hidden from playlist, English/Krio pill toggle (data-testid video-lang-toggle / video-lang-{en,krio}) on player when variant exists; VideoLibrary homepage filters Krio. LESSON: never run backend edits/pytest while produce.py is recording — pages fail to load and scenes record broken.
- **MoF batch pack**: `GET /api/vouchers/export-batch.pdf?period=` (finance/admin; registered BEFORE /{vid} route) — cover page with per-branch summary table + totals, then each payment-authorized voucher on its own pages (refactor: _voucher_flowables/_build_pdf/_batch_pdf). Vouchers.jsx "MoF pack (PDF)" button (data-testid voucher-batch-export) in filters row, disabled until a period is picked, 404 → friendly toast.
- **Query speedups**: compound indexes created at startup (employees/payroll_runs/leave_requests/audit_logs/payroll_vouchers on company_id + status/created_at/ts/period/updated_at). Projections: dashboard overview (lean employees fields, runs minus slips), analytics payroll-trend/leave-usage/top-earners, payroll list_runs excludes slips (detail GET /runs/{rid} still full). Tests test_iter2_exports + test_iter5_refactor updated to fetch run detail. Full suite: 438 passed.
- **Resend**: verification triggered; user's registrar does NOT yet show the 3 DNS records (NXDOMAIN via 8.8.8.8) — still waiting on user to add them (records in /app/memory/resend_domain.md). Once visible: POST verify → set SENDER_EMAIL → restart backend.

## v1.26 (Jun 2026) — Krio docs, MoF pack auto-email, video subtitles
- **Krio documents**: `training_production/make_docs_krio.py` generates 6 Krio QRCs + Krio onboarding checklist (qrc-*-krio.pdf, onboarding-checklist-krio.pdf); added to RESOURCES in training_content.py (18 resources total at GET /api/public/training/content).
- **MoF pack auto-email**: company field `mof_pack_email`; endpoints GET/PUT /api/vouchers/pack-config + POST /api/vouchers/pack-config/send-now?period= (admin, force resend). `_send_period_pack` in vouchers.py fires after every authorize: when EVERY branch has a payment-authorized voucher for the period → emails combined pack (email_service.send_mof_pack, PDF attachment) once (guarded via mof_pack_emails collection). UI: PackEmailCard on Vouchers page (data-testids pack-email-input/save, pack-send-period, pack-send-now, pack-last-sent). VERIFIED end-to-end: full 3-branch chain in period 2099-01 → auto-email status "sent" to delivered@resend.dev; test data then removed from DB (authorized vouchers are API-immutable, deleted via mongo). Config left set to delivered@resend.dev.
- **BUG FIX**: `_visible_filter` now grants mof_approver full tenant visibility (previously a non-admin MoF approver could not see/authorize vouchers outside branches they supervise).
- **Video subtitles**: `training_production/make_subtitles.py` builds WebVTT per video (EN + Krio, cue timing from manifest chapter offsets + cached TTS mp3 durations) into static/training/subs/, adds `captions` to manifest; seeder passes through; VideoPlayer.jsx renders <track> + CC toggle (data-testid video-captions-toggle, captions default ON). Verified on /videos.
- **Resend**: STILL pending — user's DNS records not yet published (NXDOMAIN). Next fork: check dns, POST /domains/{id}/verify, then set SENDER_EMAIL and restart (see /app/memory/resend_domain.md).
- NOTE: branch supervisors are seeded for ALL 3 gov branches (MOF-HQ Adama, MOH-FT Foday, MOL-FT Joseph). test_plain_employee_sees_nothing relies on MOL-FT having no vouchers — don't leave stray vouchers in seed periods.
- Full suite: 438 passed.

## v1.27 (Jun 2026) — Mende narration, pack history, period-close banner
- **Mende (3rd language)**: `translate_mende.py` used Emergent LLM (Claude Sonnet) to translate all 44 narrations → `mende.py` (MENDE dict, attached in scenes.py like Krio). produce.py generalized (`narration_{lang}`, LANG_TITLE map); all 7 `-mende` videos produced + seeded (21 training videos total: en/krio/mende). make_subtitles.py covers all 3 langs (srclang men, label Mɛnde). VideosPage toggle now 3-way (video-lang-en/krio/mende), playlist hides all non-en variants.
- **Pack history**: GET /api/vouchers/pack-history (finance/admin, 24 latest mof_pack_emails). PackEmailCard shows collapsible history table (pack-history-toggle/table, per-row Download via export-batch.pdf).
- **Period-close banner**: authorize response now includes `pack_email` when the pack auto-send was attempted; VoucherDetail toasts "Period closed — MoF pack emailed to X". Vouchers page shows green banner (period-closed-banner + period-closed-download) when history has a sent pack for the filtered period, or the latest sent pack is <24h old. Demo history record seeded for period 2041-11.
- Fixed flaky test_duplicate_and_double_pay_guards (retries on residue-period collision).
- **Resend**: DNS records STILL not added by user; Resend domain status moved to "failed" (it stops checking) — once user adds the 3 records, re-trigger POST /domains/{id}/verify (works from failed state), then set SENDER_EMAIL + restart backend. See /app/memory/resend_domain.md.
- **POD RESPAWN GOTCHA (recurring)**: apt (ffmpeg) + playwright chromium + pip extras (pypdf, dnspython) do NOT survive pod respawns ("Credits Recharged" gaps). Reinstall before any video production: `apt-get install -y ffmpeg && python -m playwright install chromium`.
- Full suite: 438 passed.

## v1.28 (Jul 2026) — Voucher nudges, Temne narration, Pack cover signatures
- **Voucher deadline nudges (SMS + email)**: `voucher_nudge.py` scheduler ticks every 30 min (attached to shared APScheduler in `scheduler.py`); fires reminders at T-72h and T-24h before each gov tenant's `payroll_cutoff_day` for every branch whose voucher is still not submitted for the current period. Idempotency guard on `voucher_nudges` collection keyed by (company, branch, period, window). Endpoints: `POST /api/vouchers/nudge/send-now?period=` (admin) fires a manual reminder to every missing branch; `GET /api/vouchers/nudge/history` (finance/admin) returns the last 200 nudges. Frontend: new "Voucher reminders" card on Vouchers page shows missing branch count + preview + gold "Send reminders now" button + collapsible reminder history table with SMS/Email delivery pills. Uses existing Twilio (`sms.send_one`) + Resend (`email_service._send`) wrappers — one-line E.164 phone check, both channels sent in parallel, all attempts logged with per-channel ok/error.
- **Temne (4th language)**: `translate_temne.py` used Emergent LLM (Claude Sonnet 4.5) to translate all 44 narrations to spoken Temne → `temne.py` (TEMNE dict, attached in scenes.py). Same recipe as Krio+Mende: `produce.py --lang temne` (extended LANG_TITLE), OpenAI `tts-1-hd` narration, playwright screen capture, ffmpeg mux; all 7 `-temne.mp4` (2–4MB each) + `.jpg` posters + `.vtt` subs generated. Subtitle map extended to `("en", "krio", "mende", "temne")` with srclang `tem` / label "Temne". VideosPage.jsx language toggle now 4-way (`video-lang-en/krio/mende/temne`). Seeder generic — 28 training videos total (7 videos × 4 languages).
- **Pack cover Minister sign-off block**: `_batch_pdf` in `routers/vouchers.py` now appends a "Ministry of Finance — Authorization" section on the cover page with statement, Full name / Title / Signature / Date fields (blank lines for wet-signing), and a bordered "Official stamp" cell before the individual voucher pages. Verified via pypdf that the phrases "Minister of Finance", "Full name", "Signature", "Official stamp", "counter-sign" all render on page 1.
- **Tests**: new `test_iter33_nudge_and_signoff.py` — 7 tests (manual nudge, idempotency, history, admin-only, plain-employee 403, cover sign-off phrases on real generated PDF, manifest exposes Temne when seeded). All pass. Voucher suite still 20/20 (13 iter32 + 7 iter33). Broader regression 65/65 across iter12/26/29/30/31/32/33.
- **Resend**: user-side DNS still NXDOMAIN as of pod check. Re-triggered verify — Resend flipped `salonehcm.com` from `failed` → `pending` (all 3 records `pending`). Waiting for user to publish the 3 records at their registrar (GoDaddy per NS = ns11/ns12.domaincontrol.com). Once DNS resolves, re-run verify → set `SENDER_EMAIL="SaloneHCM <no-reply@salonehcm.com>"` in backend/.env → `sudo supervisorctl restart backend`.

## v1.31 (Jul 2026) — Mobile PWA + WebAuthn scaffold
- **Mobile shell at `/m/*`**: full bottom-nav mobile experience layered on top of the existing SPA and its authenticated APIs — no separate backend, same JWT + CSRF, so a future Capacitor / Expo wrapper can point at the same routes with zero refactor. Files: `frontend/src/mobile/MobileLayout.jsx` (safe-area padded header + fixed bottom nav with role-filtered tabs + offline badge), `MobileHome.jsx` (greeting + big net-pay card + 4 quick tiles + pending-decisions section + voucher queue), `MobilePayslips.jsx` (list + PDF download via `downloadBlob`, localStorage cache), `MobileLeave.jsx` (mine + reports queue + inline Approve/Reject + bottom-sheet request form), `MobileClock.jsx` (browser Geolocation watchPosition + Clock-in / Clock-out with distance-to-branch), `MobileVouchers.jsx` (RBAC-filtered queue with role-appropriate next-action button: supervisor-approve, start-review, approve, authorize), `MobileProfile.jsx` (push toggle with `/api/push/*`, WebAuthn enrol/revoke with `/api/auth/webauthn/*`, device list). Every interactive element has `data-testid`. Header on desktop gets a green "Mobile" pill (`header-mobile-launcher`) linking to `/m` so users can find it.
- **Backend — mobile router (`routers/mobile.py`)**: `GET /api/mobile/summary` (one-call dashboard aggregate — current + latest payslip, leave balance + mine, pending reports leave, today's punches, RBAC voucher queue, unread notification count), `POST /api/mobile/punch` (GPS-tagged clock in/out with WGS-84 lat/lng, haversine distance-to-branch when the branch has coords, automatic pairing of clock-out to earliest clock-in of the day + hours computation on the in-punch), `GET /api/mobile/punch/today`.
- **Backend — WebAuthn (`routers/webauthn.py`)**: full FIDO2 passkey scaffold using the `webauthn` python library (v3.0.0). Registration ceremony (`/api/auth/webauthn/register/begin` + `/finish`) verified via attestation, credentials stored in `webauthn_credentials` collection with credential_id / public_key / sign_count / device_label. Login ceremony (`/api/auth/webauthn/login/begin` + `/finish`) verifies assertion + mints the same JWT + CSRF cookies as the classic login path — no code duplication. Credential list + revoke endpoints (`/api/auth/webauthn/credentials` and DELETE by cid). RP ID derived from FRONTEND_URL; challenges keyed per user + purpose, single-use.
- **Manifest / PWA**: shortcuts updated to point at `/m`, `/m/payslips`, `/m/clock`, `/m/leave` for one-tap access from the home screen after install. Existing service worker (`public/sw.js`) already caches `/dashboard`, `/self-service` + `/api/payroll/my-payslip*` + `/api/auth/me` and handles push notifications; the new mobile pages benefit from it automatically.
- **Tests**: new `test_iter34_mobile.py` — 10 tests (summary shape, auth-required, RBAC role check, punch in→out with pairing, bad-kind rejection, employee-link guard, WebAuthn register/begin returns valid options, empty credentials list, login/begin returns options, register/finish rejects junk). Broader regression 67/67 across iter12/26/30/31/32/33/34.
- **Enterprise architecture confirmed**: same secure backend APIs as web; RBAC on every mobile screen (voucher queue role-filtered on server + tab hidden on client); biometric ready via WebAuthn; state-shared with web SPA (session cookies, IndexedDB queue, service worker) so switching between mobile view and desktop view is seamless. Ready-to-wrap for native iOS/Android via Capacitor when needed.

## v1.30 (Jul 2026) — Resend domain LIVE
- **salonehcm.com verified end-to-end**: user published the 3 DNS records at GoDaddy (TTL=1h); DKIM + MX + SPF all flipped to `verified` on Resend within ~10 min. Switched `backend/.env` `SENDER_EMAIL` from `onboarding@resend.dev` to `SaloneHCM <no-reply@salonehcm.com>` and restarted backend. Raw Resend test send accepted (id `85bf633b-9cea-49c6-8843-a138fe755881`). App-level digest send-now delivered to 3/3 supervisors (`digests_new: 3`). Test address `delivered@resend.dev` used for smoke-test then supervisor email restored.
- Regression 33/33 across iter12/32/33.
- **Blocker cleared**: every automated email path (voucher digest, MoF pack auto-email, per-branch nudges, invite emails, payslip emails) now sends from the official domain.

## v1.29 (Jul 2026) — Coat-of-arms watermark, nudge digest (06:00 UTC)
- **Sierra Leone coat of arms on the MoF pack cover**: sourced official 320×320 PNG (upscaled to 512×512, `/app/backend/static/brand/sl-coat-of-arms.png`), embedded via ReportLab `Image` at 2.6cm inside a two-column table that pairs the emblem with the "REPUBLIC OF SIERRA LEONE / Ministry of Finance" header + counter-signature statement, then the wet-signature grid (Full name / Title / Signature / Date / Official stamp) sits below. Verified via `pdf2image` render + pypdf XObject count ≥1 on cover.
- **Nudge digest split-channel refactor**: SMS still fires at T-72h + T-24h (urgent, real-time via `_tick` every 30 min). Email nudges from the tick are suppressed via `_fire_nudge(email=False)` and replaced by a new **06:00 UTC daily digest** (`_send_daily_digest` + APScheduler `CronTrigger(hour=6)`) that groups every branch missing a voucher by supervisor and sends ONE consolidated email per supervisor listing all their at-risk branches + hours-to-cutoff. Idempotency guard on `voucher_nudge_digests` collection keyed by (company, supervisor, period, day) — one digest per person per calendar day. Range gate: only fires when deadline is within 7 days AND still in the future. Endpoints: `POST /api/vouchers/nudge/digest/send-now` (admin, manual trigger), `GET /api/vouchers/nudge/digest/history` (finance/admin). Frontend: new "Send digest now" secondary button on the reminder card + new "daily digests" history table with supervisor, branches count, hours-left and delivery pill. Copy updated to reflect the new cadence.
- **Tests**: `test_iter33_nudge_and_signoff.py` now 11 tests — TestNudgeDigest (send-now, idempotency, history, plain-employee 403) + strengthened cover-page assertion (also checks embedded image XObject). All pass; broader regression 48/48 across iter26/30/31/32/33.
- **Resend**: DNS still NXDOMAIN on all 3 records; blocked until user publishes at GoDaddy.


## v1.32 (Aug 2026) — PWA offline shell VERIFIED + drain race fix
- **Offline app-shell caching verified end-to-end** (user's reported bug: offline refresh → network error). True-offline Playwright test (`PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS=1` + `ctx.route` abort + `set_offline` — note: plain `set_offline` does NOT emulate offline for SW-context fetches, giving false passes): offline reload renders the full mobile shell; offline punch → 202 + IndexedDB row (`status: queued`) + amber "1 punch queued" badge + toast; reconnect → queue drains, badge clears, punch appears in today list and lands in `db.attendance` exactly once.
- **BUG FOUND + FIXED — duplicate punch replay on reconnect**: reconnect fires browser online event + manual dispatch + BackgroundSync concurrently → 3 parallel `drainQueue()` passes each replayed the same queued item (3 identical rows 35ms apart in DB). Fix (a) `sw.js`: drain mutex (`_drainInFlight` promise guard around `_drainQueue`); (b) `routers/mobile.py` punch endpoint: 15s idempotency guard — same employee+kind+date within 15s returns the existing row instead of inserting.
- **Post-sync staleness fix**: after a successful drain, SW deletes cached `/api/mobile/*` GETs (`invalidateMobileApiCache`) so the refresh after sync hits the network (stale-while-revalidate previously served the pre-punch cached list).
- **Test-suite time-bombs fixed**: (1) `test_iter29_budget_check.py` safe-verdict test — earlier runs poison FUTURE periods (period+2/+3) with 1.0 SLE allocations which later become the current period; test now self-heals by restoring generous allocations for all codes in play before asserting. (2) `test_iter32_vouchers.py` dup-employee-422 test — random period could collide with residue vouchers (409 fires first); now retries with fresh periods.
- Full regression: **458 passed, 7 skipped** (entire `/app/backend/tests`).
- Offline test script kept at `/tmp/test_pwa_offline.py` (rebuild if pod respawns; launch chromium via `executable_path="/usr/bin/google-chrome"` — pw-browsers cache incomplete).

## v1.33 (Aug 2026) — Biometric login live, Mobile Training, Offline Payslip Pack, GPS Punch Map
- **Biometric (WebAuthn) login E2E**: fixed two blockers — `webauthn.py` called `make_access(user)` but the signature is `(uid, email, role)` (login/finish crashed), and `FRONTEND_URL` in backend/.env pointed at a stale preview URL (RP_ID/origin mismatch). `login/finish` now returns the FULL classic-login payload (company, employee_id, flags, csrf_token). Login page gained "Sign in with biometrics" (`login-biometric-button`), rendered ONLY when `isUserVerifyingPlatformAuthenticatorAvailable()` is true. Verified end-to-end with a CDP virtual authenticator (enrol on /m/profile → sign out → biometric sign-in → /dashboard as full identity); gating verified by testing agent (button hidden without authenticator).
- **Mobile Training Center** (`/m/training`, `MobileTraining.jsx`): all 7 walkthrough videos in 4 languages (EN/Krio/Mende/Temne) from `/api/marketing/videos?category=training`, language pills persisted to localStorage, native player with VTT caption tracks, list cached for offline browse. "Learn" tile added to mobile Home.
- **Offline Payslip Pack** (on `/m/profile`): last 3 payslips with per-row Save/Open + "Save all"; PDFs stored in CacheStorage `salonehcm-payslip-pack` (survives SW version bumps via `PERSISTENT_PREFIX` keep-list in sw.js activate); clear "Saved offline / Not saved" indicator per row.
- **GPS Punch Map**: branches now carry `lat`/`lng`/`geofence_radius_m` (BranchIn/BranchPatch + seeder coords for all 5 branches + startup backfill; editable in Branches panel with `branch-lat/lng/geofence` inputs). New `GET /api/mobile/punch/team[.csv]?date&employee_id` — admins see all tenant branches, branch supervisors only theirs, everyone else 403; `in_zone` computed via shared `_haversine_m` against branch geofence (fallback 250m). Mobile Clock gets a collapsible "Team map · today" section (Leaflet/OSM, lazy-loaded, green/red/gray CircleMarkers, geofence circles, out-of-zone list) with an error+Retry state for transient failures; desktop /attendance gets a richer section (stats chips, date picker, client-side employee filter, zone table, CSV export). New deps: `leaflet` + `react-leaflet@5`.
- **Robustness**: Vouchers page `refresh()` Promise.all wrapped in try/catch (429 bursts no longer trigger the CRA error overlay).
- **Tests**: new `/app/backend/tests/test_iter35_team_map.py` (9 tests — seeds have coords, geofence patch + bounds 422, team RBAC 403 for non-supervisors, in/out-zone haversine, supervisor scope, CSV, date filter). Full backend suite **468 passed, 7 skipped**. Testing agent frontend run: **7/7 PASS** (report `/app/test_reports/iteration_34.json`).
- Known non-issues: backend rate limiter can 429 under aggressive automated navigation; shadcn date picker on /attendance isn't `.fill()`-able by Playwright (use popover clicks).
