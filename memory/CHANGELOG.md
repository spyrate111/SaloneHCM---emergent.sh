## CHANGELOG

### v1.5 (May 2026) — Compliance, Automation, Mobile, Security

**Compliance Score**
- New `compliance_score.py` engine weighting 4 dimensions: NRA filing timeliness (25%), NASSIT contribution accuracy (30%), SMS delivery success in last 30d (20%), audit-log coverage (25%)
- `GET /api/dashboard/compliance-score` returns `{score, grade, breakdown, weights}` — drops non-applicable dimensions cleanly so non-Gov tenants aren't penalised for missing SMS
- Animated SVG-arc `ComplianceScoreWidget` on Dashboard with letter grade + expandable per-dimension breakdown

**Recurring Payroll Schedules**
- New `payroll_schedules` collection + `routers/schedules.py` (CRUD + manual run-now)
- `scheduler.py` boots an in-process APScheduler (5-min tick) that fires due schedules with `_evaluate_due()`; updates `last_run_*` + recomputes `next_run_at` on each fire
- Cadences: `monthly` (with `day_of_month` clamped to month length), `biweekly`, `weekly`
- Frontend `/schedules` page (admin-only) with create/pause/run-now/delete

**Ministry Rollup (Gov tier exclusive)**
- New `routers/ministry.py` — `GET /api/ministry/rollup` gated on `require_feature("ministry_reports")` (Gov tier only)
- Aggregates by department (= ministry): headcount active/total, manager count, monthly gross/net/PAYE/NASSIT, average basic, leave pending, leave-days approved in last 30d
- Frontend `/ministry` page: KPI strip · grouped bar chart (Gross/PAYE/NASSIT per ministry) · per-ministry breakdown table

**2FA for super-admin (TOTP)**
- `twofa.py` — pyotp + qrcode; data-URL QR for the setup screen
- New endpoints `POST /api/auth/2fa/setup|enable|disable` + `GET /api/auth/2fa/policy`
- Login flow: `LoginIn.totp_code` optional; if `twofa_enabled`, returns structured 401 `{detail: {code: "totp_required"}}` so frontend can prompt; subsequent submit with valid code completes login
- Enforced on `superadmin` role (`TWOFA_REQUIRED_ROLES`); super-admin cannot disable
- Frontend: TOTP input on Login (auto-prompted on `totp_required`), `TwoFactorCard` on Settings with QR + 6-digit verify + disable flow

**Mobile ESS PWA**
- `public/manifest.json` (theme `#133326`, standalone display, shortcuts to /self-service /leave /documents)
- `public/sw.js` — network-first for navigation, cache-first for static assets, API calls never cached
- `index.html` — manifest link, theme-color meta, apple-mobile-web-app-* metas, proper viewport-fit
- `Layout.jsx` — responsive sidebar (slide-in drawer on `<lg`, hamburger button in header, backdrop tap-to-close, auto-close on route change)
- Service worker registers via `useEffect` on App mount

**Bug fixes & nits this iter**
- Removed unused vars in `tests/test_iter8_phase_abc.py`
- Stale carry-over from iter8 audit (documents.py role check) verified clean — no remaining `role != "admin"` literals across routers

**Architectural invariants preserved**
- Every Mongo query uses `tenant_filter(user)`; every insert wrapped in `with_tenant()`
- Tier-gated endpoints return **402** with upgrade prompt
- All third-party integrations route through `integration_playbook_expert_v2`
- Token in `sessionStorage` (key `salonehcm_token`); httpOnly cookie also set on login
- APScheduler lifecycle managed by FastAPI lifespan (start on startup, stop on shutdown)

---

### v1.4 — Multi-tenant SaaS + Bulk SMS (May 2026)

**Phase a — Super-admin + user invitations**
- `superadmin` role with router-level `Depends(require_superadmin)` for `/api/admin/*`
- Seed admin (`admin@salonehcm.sl`) auto-upgraded to `superadmin` on every boot (idempotent)
- `POST /api/admin/companies` — provision new tenant + initial admin user atomically
- `PATCH /api/admin/companies/{id}/tier` — change tier, refreshes feature list
- `POST /api/admin/companies/{id}/switch` — moves super-admin's `company_id` and issues fresh JWT
- `routers/users.py` — `/api/users` CRUD + invite + reset-password + unlinked-employees
- Frontend: `Users` page (admin) + `Companies` page (super-admin) + `CompanySwitcher` dropdown

**Phase b — Twilio bulk SMS payslips**
- `sms.py` — `send_payslip_batch()` with `asyncio.Semaphore(8)` bounded concurrency
- E.164 phone normalization
- Auto dry-run when `TWILIO_*` unset (graceful fallback)
- `POST /api/payroll/runs/{rid}/send-sms` gated by `require_feature("bulk_sms_payslips")` (Gov tier)
- Per-recipient `sms_logs` collection (tenant-scoped)
- Gov tenant seeded with 6 ministerial employees + admin `admin@gov.sl / GovAdmin@2026`
- Frontend: `SmsPayslipButton` modal

**Phase b' — SMS Audit page**
- `GET /api/payroll/sms/summary`, `/sms/batches`, `/sms/logs.csv` (all tenant-scoped, admin-only)
- `GET /api/payroll/sms/logs` accepts `period`, `status`, `batch_id` query filters
- Frontend `/sms-logs` page with batches/recipients drill-down + CSV export

**Phase c — Simulator refactor**
- `pages/Simulator.jsx`: 558 → **96 lines** orchestrator
- `hooks/useSimulator.js` (state + API actions)
- `components/simulator/`: ApprovalBanner, RulesEditor, SimulationResults, SavedScenariosTable, ComparisonPanel, SaveScenarioModal, ShareLinkModal

**Cross-cutting bug fix**
- 6 places (documents, payroll, assistant, benefits, leave) where `role != 'admin'` literal locked superadmins out — all now use `role not in ("admin","superadmin")`
