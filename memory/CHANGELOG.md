## CHANGELOG

### v1.4 (May 2026) — Multi-tenant SaaS + Bulk SMS
**Phase a — Super-admin + user invitations**
- `superadmin` role with router-level `Depends(require_superadmin)` for `/api/admin/*`
- Seed admin (`admin@salonehcm.sl`) auto-upgraded to `superadmin` on every boot (idempotent)
- `POST /api/admin/companies` — provision new tenant + initial admin user atomically
- `PATCH /api/admin/companies/{id}/tier` — change tier, refreshes feature list
- `POST /api/admin/companies/{id}/switch` — moves super-admin's `company_id` and issues fresh JWT; subsequent `tenant_filter()` queries naturally hit the new tenant
- `routers/users.py` — `GET/POST /api/users`, `/invite`, `/{id}/reset-password`, `/{id}` DELETE, `/unlinked-employees` (all tenant-scoped); guards against self-delete + super-admin tampering
- Frontend: `Users` page (admin) + `Companies` page (super-admin) + `CompanySwitcher` dropdown in header (super-admin only)
- `useFeatures()` exposes `isAdmin`/`isSuperAdmin` flags
- `AuthContext` now exposes `refetch()` for post-switch user/company hydration

**Phase b — Twilio bulk SMS payslips**
- `sms.py` — `send_payslip_batch()` with `asyncio.Semaphore(8)` for bounded concurrency
- E.164 phone normalization (`+232 76 000 000` → `+23276000000`)
- Auto dry-run when `TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER` unset (graceful fallback)
- `POST /api/payroll/runs/{rid}/send-sms` gated by `require_feature("bulk_sms_payslips")` (Gov tier only) — returns `{batch_id, sent, would_send, failed, skipped, total, dry_run, twilio_configured, results}`
- Per-recipient `sms_logs` collection (tenant-scoped) for forensic auditability
- `GET /api/payroll/sms/status` reports whether Twilio is wired
- `GET /api/payroll/sms/logs` returns tenant's send history
- Gov tenant seeded with 6 ministerial employees (1 with empty phone to exercise skip path) + admin `admin@gov.sl / GovAdmin@2026`
- Frontend: `SmsPayslipButton` modal with dry-run/live toggle, Twilio-not-configured banner, per-recipient pill table

**Phase c — Simulator refactor**
- `pages/Simulator.jsx`: 558 → **96 lines** orchestrator
- New: `hooks/useSimulator.js` (state + API actions)
- New: `components/simulator/` — `ApprovalBanner.jsx`, `RulesEditor.jsx`, `SimulationResults.jsx`, `SavedScenariosTable.jsx`, `ComparisonPanel.jsx`, `SaveScenarioModal.jsx`, `ShareLinkModal.jsx`

**Bug fix this iter**
- Audit + fixed 6 places (`documents.py`, `payroll.py`, `assistant.py`, `benefits.py`, `leave.py`) where `role != 'admin'` literal blocked `superadmin` from acting in switched-in tenants. All such checks now use `role not in ("admin","superadmin")` to mirror `require_admin` semantics.

**Architectural invariants reinforced**
- Every Mongo query uses `**tenant_filter(user)`; every insert wrapped in `with_tenant()`
- Tier-gated endpoints return **402** with upgrade prompt + Settings deep-link
- All third-party integrations route through `integration_playbook_expert_v2`
