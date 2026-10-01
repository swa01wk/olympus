# Live project scaffold

When Phase 16 provides a live control-api, set:

```bash
NEXT_PUBLIC_OLYMPUS_DATA_MODE=live
OLYMPUS_API_URL=http://localhost:8000
```

Implement HTTP adapters in `lib/api/http-services.ts` against OpenAPI from the control plane. Do not import `lib/fixtures/**` from live adapter code paths.
