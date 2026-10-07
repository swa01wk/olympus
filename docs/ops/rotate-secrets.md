# Rotate secrets

## API tokens

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"actor_id":"<uuid>","scopes":["read","operate","approve","admin"]}' \
  http://localhost:8000/auth/tokens
```

Rotate: `POST /auth/tokens/{id}/rotate` (admin). Revoke: `POST /auth/tokens/{id}/revoke`.

## Inbound webhook secrets

`POST /integrations/sources/{id}/rotate-secret` with `new_secret_ref` and optional `grace_hours`.
During grace, HMAC verification accepts the previous secret via `secondary_secret_ref`.
