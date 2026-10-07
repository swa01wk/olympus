# Supported indexing patterns (Phase 07 MVP)

- Python 3.12 syntax via `ast` (no LibCST).
- FastAPI: `@app.<method>`, `@router.<method>`, `APIRouter(prefix=...)`, `include_router(..., prefix=...)`.
- Pydantic: classes with `BaseModel` bases; route `response_model=` keyword.
- SQLAlchemy declarative: `__tablename__`, `session.add(Model(...))`, `session.get(Model, ...)`, `select(Model)`.
- pytest: `test_*` functions, `Test*` classes, `TestClient` HTTP calls with literal paths.
- Imports: absolute/relative to local modules; external imports classified in file metadata.

Unsupported or best-effort: dynamic getattr, re-export aliases, star-import call targets, non-literal test client paths.
