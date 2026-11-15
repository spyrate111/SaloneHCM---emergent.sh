# Resend Email Domain Setup — salonehcm.com

- Resend domain id: `3c192a3d-ceff-4c58-9653-490a4500e536` (region eu-west-1)
- Status: registered, awaiting user DNS records + verification
- Verify: `curl -X POST https://api.resend.com/domains/3c192a3d-ceff-4c58-9653-490a4500e536/verify -H "Authorization: Bearer $RESEND_API_KEY"`
- Check: `curl https://api.resend.com/domains/3c192a3d-ceff-4c58-9653-490a4500e536 -H ...` → status should become `verified`
- After verified: set SENDER_EMAIL="SaloneHCM <no-reply@salonehcm.com>" in /app/backend/.env + restart backend

## DNS records the user must add at their registrar
| Type | Host/Name | Value | Priority |
|------|-----------|-------|----------|
| TXT | resend._domainkey | p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDKE9qCTN+uKk3559ozoNUfkL6j5cXr0+OdPhN2DLVFwVmXY2v/aQSDtC9WMYR7j+uRkBugiTaN4vHi3JxDCIshVo2KU6sOezUaCl5PkC9D9vIUcBQ/OIHF9WXT6UHbdXKDeEHXF0d8yxMMR98LkLncAJGzVJaL+IbNFJkCZvm28QIDAQAB | — |
| MX | send | feedback-smtp.eu-west-1.amazonses.com | 10 |
| TXT | send | v=spf1 include:amazonses.com ~all | — |
