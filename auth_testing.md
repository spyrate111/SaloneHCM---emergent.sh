# SaloneHCM Auth Testing Notes

Auth uses JWT (HS256, 12h) returned in JSON body and stored client-side as `salonehcm_token`. Client adds `Authorization: Bearer <token>` to requests.

## Test
```
curl -X POST $REACT_APP_BACKEND_URL/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@salonehcm.sl","password":"Admin@2026"}'
```
Response includes `token`. Then:
```
curl -H "Authorization: Bearer <token>" $REACT_APP_BACKEND_URL/api/auth/me
```

## Seeded MongoDB
- users: 1 admin + 10 employee accounts
- employees: 10 seeded
- bcrypt hash starts with `$2b$`
