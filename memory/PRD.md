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
- Mobile ESS PWA — ICONS + manifest shipped iter9; offline-first still pending
- **DONE (iter10)** ~~NRA export filing automation (Gov tier)~~
- Cosmetic: Recharts width(-1) warning + UploadModal hydration warning

### P3
- Full Government tier features (ministry-level reporting, bulk SMS)
- Backend `tests/` regression suite (testing agent created `test_iter7_tenant.py` — extend it)

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
