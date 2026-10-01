# Phase 07 — Code Intelligence Index (Deterministic, Python-First)

## 1. Objective

Build the practical MVP Code Intelligence Index (ARCH §14.3, TECH §13): a deterministic, versioned, SHA-bound structural index of a Python/FastAPI repository. It covers:

- **entities:** repository, package, module, file, class, method, function, route, schema, ORM model, table and test;
- **relations:** contains, imports, calls, inherits, accesses, exposes, verified_by.

Lexical/symbol search and traversal APIs expose retrieval provenance. The index is the structural substrate for:
- canonical promotion and SpecCodeLinks (08);
- Brownfield discovery (11);
- impact analysis (13);
- bug code-path traversal (15).

This phase deliberately **does not** decide canonical status or link specs. It produces correct, reproducible indexes for any given `(repository, sha)`, reading Git objects from the Repository's canonical RepositoryWorkspace (resolved through Phase 01's `WorkspaceLocator`) at that exact SHA. It never reads a working tree, and it never indexes uncommitted changes. The candidate vs canonical index distinction is defined in README §5.9.6. Phase 07 builds only `CANDIDATE` versions itself. `CANONICAL` versions are created exclusively by Phase 08's `CanonicalIndexService`, and only at `Repository.canonical_commit`.

## 2. Architectural Context

- **Position:** Intelligence/Context plane → `core/intelligence/code_index`.
- **Upstream:** 01 (Repository + canonical RepositoryWorkspace metadata, `WorkspaceLocator`, `materialize_fixture_repository` test helper), 00 (DB).
- **Downstream:**
  - 08: candidate vs canonical index, `code_entity_changes`, SpecCodeLink.
  - 09: Sentinel uses test entities.
  - 11: Brownfield discovery and ObservedBehavior.
  - 13: incremental re-index, hybrid retrieval, embeddings.
  - 15: code-path traversal.
- **Invariants:**
  - 18–19 (groundwork): every index version is tied to an exact SHA and carries a `kind` so candidate and canonical are distinguishable.
  - Deterministic parsing first. Semantic retrieval never replaces structural relations.
  - Retrieval results expose structural/lexical/semantic origin and provenance (ARCH §22).

## 3. Current Repository Assessment

Inspection on 2026-10-01: no parser, index or retrieval code exists.

### Existing
- (after 01) `repositories` / `repository_workspaces` tables, `WorkspaceLocator` and the read-only GitInspector — **RETAIN/EXTEND** (`git ls-tree`, `git cat-file --batch` read access against the bare canonical workspace, without checkout).
- (after 01) the test helper `materialize_fixture_repository(fixture_dir) -> (repository, sha)` — **RETAIN**. Phase 07 tests use it instead of a private `make_git_repo`, so indexes are always built against a registered Repository's canonical workspace.

### Partial
- None.

### Missing
- All index code, tables, APIs and reference fixtures — **ADD**.

### Refactor / Migration Required
- None.

## 4. Scope

1. Tables: `code_index_versions`, `code_entities`, `code_relations`.
2. Source reading at an exact SHA, independent of any working copy: `git ls-tree -r <sha>` + `git cat-file --batch`, run against `WorkspaceLocator.resolve(repository.workspace.logical_location)`. The index is reproducible from `(repository, sha)` alone. A SHA that is not present in the canonical object store fails with `COMMIT_NOT_FOUND`. Candidate commits are readable because ExecutionWorkspaces share the canonical object store (README §5.9.2). Source bytes are read transiently for parsing. Only spans, hashes, names and structural metadata are persisted (README §5.9.1).
3. Parsers and extractors (Python `ast`, no execution of repository code):
   - `python_ast.py`: modules, classes, methods, functions, qualified names, line spans, decorators, docstrings (first line), signature text and content hash per entity.
   - `imports.py`: absolute and relative import resolution to local modules (`IMPORTS`). Unresolved external imports are recorded as `metadata.external_imports`, each classified deterministically as `STDLIB` (`sys.stdlib_module_names`), `DECLARED_DEPENDENCY` (top-level name matched to a distribution declared in the repository's statically parsed `pyproject.toml` / `requirements*.txt`, using `importlib.metadata.packages_distributions()` only as a name-mapping table from Olympus's own environment) or `UNDECLARED`. Repository code is never imported to do this.
   - `calls.py`: resolvable local call edges (`CALLS`) via name binding within the module, imported names, `self.method` within a class, and class instantiation. Unresolvable calls are dropped (they are listed in `metadata.unresolved_calls`). Confidence is 1.0 for direct binding and 0.8 for `self.` heuristics.
   - `inheritance.py`: `INHERITS` for locally resolvable bases.
   - `fastapi_routes.py`: `@app.get/post/...`, `@router.<method>` and `APIRouter(prefix=…)` plus `include_router` prefix composition. Produces a ROUTE entity `{method, path, handler}` with relations `EXPOSES` (route → handler) and `CALLS` from the handler.
   - `pydantic_schemas.py`: classes deriving from `BaseModel` (transitively, locally) produce SCHEMA entities (fields, types). Route `response_model` / parameter annotations produce `USES_SCHEMA`.
   - `sqlalchemy_models.py`: declarative models (`DeclarativeBase`/`declarative_base()` subclasses with `__tablename__`) produce ORM_MODEL entities (columns) plus TABLE entities, with `MAPS_TO` (model → table). `session.query(Model)`, `select(Model)`, `session.add(Model(...))` and `db.get(Model, …)` produce `ACCESSES` (function → model).
   - `pytest_tests.py`: `test_*` functions and `Test*` classes produce TEST entities. A test's imports and calls of local symbols produce `VERIFIED_BY` (symbol → test). FastAPI `TestClient` calls with a literal path (`client.post("/tickets")`) produce `VERIFIED_BY` (route → test) through route path matching.
   - `git_metadata.py`: per-file last-commit SHA, author date and commit count at the index SHA (stored in FILE metadata).
4. Stable entity identity: `stable_key = f"{type}:{file_path}:{qualified_name}"` (routes: `ROUTE:{METHOD} {path}`; tables: `TABLE:{name}`). This key is the cross-version identity used by 08 and 13.
5. `CodeIndexer.build(repository_id, sha, kind, scope_ref) → CodeIndexVersion`. It is idempotent: an existing READY version for `(repository, sha, kind, scope_ref)` is returned. `kind=CANONICAL` is accepted only from `CanonicalIndexService` (Phase 08; a module-private capability argument), and only when `sha == Repository.canonical_commit` or is the SHA being atomically promoted to it. Every other caller, including the REST rebuild API, may build only `CANDIDATE`.
6. Determinism: entities and relations are sorted and hashed, and `code_index_versions.content_hash` is a sha256 over the sorted `(stable_key, content_hash)` list plus sorted relations. Re-indexing the same SHA must produce the same hash.
7. Retrieval: `core/intelligence/code_index/retrieval/`:
   - `structural.py`: neighbors by relation/direction/depth; paths between entities.
   - `lexical.py`: symbol/route/file search using `pg_trgm` on `qualified_name`, `file_path` and route path.
   Every result carries `retrieval_source ∈ {STRUCTURAL, LEXICAL}` (SEMANTIC added in 13), the `index_version_id`, SHA and provenance.
8. APIs for rebuild, versions, entities, neighbors and search.
9. Reference fixtures: `tests/fixtures/repos/supportdesk_r1/`, a hand-written FastAPI + SQLAlchemy + Pydantic + pytest SupportDesk app with:
   - `app/main.py`, `app/api/tickets.py`, `app/services/ticket_service.py`, `app/repositories/ticket_repository.py`, `app/models/ticket.py`, `app/schemas/ticket.py`, `app/db.py`;
   - `tests/test_tickets_api.py`, `tests/test_ticket_service.py`.
   Plus a golden expected-index file `tests/fixtures/repos/supportdesk_r1.expected_index.json` (entity stable keys + relations).

## 5. Out of Scope

- Canonical vs candidate **promotion**, repository pointers and SpecCodeLinks (08).
- Incremental indexing (13), embeddings/semantic retrieval (13) and runtime probes (12).
- Languages other than Python and frameworks other than FastAPI/Pydantic/SQLAlchemy/pytest (TECH §2.1).
- LibCST (optional per TECH, not used).

### Do Not Change
- Never import or execute indexed repository code (security: repository content is untrusted).
- No graph database (TECH §2.1).

## 6. Domain / Data Model Changes

Migration `0016_p07_code_index.py` (TECH 008 partial):

```python
class IndexKind(StrEnum):
    CANDIDATE = "CANDIDATE"
    CANONICAL = "CANONICAL"


class IndexSource(StrEnum):
    REPOSITORY_SNAPSHOT = "REPOSITORY_SNAPSHOT"
    EXECUTION = "EXECUTION"
    INTEGRATION_CANDIDATE = "INTEGRATION_CANDIDATE"
    RELEASE = "RELEASE"
    EXTERNAL_PUSH = "EXTERNAL_PUSH"  # used by Phase 16 adoption (README §5.9.9); declared here so the enum is complete


class EntityType(StrEnum):
    REPOSITORY = "REPOSITORY"
    PACKAGE = "PACKAGE"
    MODULE = "MODULE"
    FILE = "FILE"
    CLASS = "CLASS"
    METHOD = "METHOD"
    FUNCTION = "FUNCTION"
    ROUTE = "ROUTE"
    SCHEMA = "SCHEMA"
    ORM_MODEL = "ORM_MODEL"
    TABLE = "TABLE"
    TEST = "TEST"


class RelationType(StrEnum):
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    ACCESSES = "ACCESSES"
    EXPOSES = "EXPOSES"
    USES_SCHEMA = "USES_SCHEMA"
    MAPS_TO = "MAPS_TO"
    VERIFIED_BY = "VERIFIED_BY"


class CodeIndexVersion(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "code_index_versions"
    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"))
    commit_sha: Mapped[str]
    kind: Mapped[IndexKind]
    source: Mapped[IndexSource]
    scope_ref: Mapped[str] = mapped_column(
        default=""
    )  # execution key / IC key / "" for repository snapshot
    status: Mapped[str]  # BUILDING | READY | FAILED | SUPERSEDED | DISCARDED
    parent_index_version_id: Mapped[uuid.UUID | None]  # incremental base (Phase 13)
    indexer_version: Mapped[str]
    content_hash: Mapped[str | None]
    stats: Mapped[dict] = mapped_column(JSONB)  # counts per type/relation, parse errors
    __table_args__ = (
        UniqueConstraint("repository_id", "commit_sha", "kind", "scope_ref", "indexer_version"),
    )


class CodeEntity(Base, UUIDPkMixin):
    __tablename__ = "code_entities"
    index_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_index_versions.id", ondelete="CASCADE"), index=True
    )
    stable_key: Mapped[str]
    type: Mapped[EntityType]
    language: Mapped[str] = mapped_column(default="python")
    file_path: Mapped[str | None]
    qualified_name: Mapped[str]
    start_line: Mapped[int | None]
    end_line: Mapped[int | None]
    content_hash: Mapped[str | None]
    is_public: Mapped[bool]
    metadata: Mapped[dict] = mapped_column("metadata", JSONB)
    __table_args__ = (
        UniqueConstraint("index_version_id", "stable_key"),
        Index(
            "ix_code_entities_qn_trgm",
            "qualified_name",
            postgresql_using="gin",
            postgresql_ops={"qualified_name": "gin_trgm_ops"},
        ),
    )


class CodeRelation(Base, UUIDPkMixin):
    __tablename__ = "code_relations"
    index_version_id: Mapped[uuid.UUID] = mapped_column(index=True)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_entities.id", ondelete="CASCADE")
    )
    relation: Mapped[RelationType]
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_entities.id", ondelete="CASCADE")
    )
    provenance: Mapped[
        str
    ]  # AST | FRAMEWORK:fastapi | FRAMEWORK:sqlalchemy | FRAMEWORK:pydantic | FRAMEWORK:pytest | HEURISTIC
    confidence: Mapped[float]
    __table_args__ = (
        UniqueConstraint("index_version_id", "source_entity_id", "relation", "target_entity_id"),
        Index("ix_rel_src", "source_entity_id", "relation"),
        Index("ix_rel_tgt", "target_entity_id", "relation"),
    )
```

Index versions with status READY are immutable (trigger), except for `status` → SUPERSEDED/DISCARDED.

Representative entity (ARCH §14.3):

```json
{"stable_key":"METHOD:app/services/ticket_service.py:TicketService.update_status","type":"METHOD",
 "qualified_name":"app.services.ticket_service.TicketService.update_status","start_line":41,"end_line":63,
 "metadata":{"decorators":[],"signature":"(self, ticket_id: int, status: TicketStatus) -> Ticket"}}
```

## 7. State / Lifecycle Changes

CodeIndexVersion: BUILDING → READY | FAILED. READY → SUPERSEDED (Phase 08/13 pointer moves) | DISCARDED (candidate cleanup, Phase 08). Owner: `CodeIndexer` (BUILDING/READY/FAILED) and `CanonicalIndexService` (Phase 08). No DeliveryCycle state changes.

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| POST | `/projects/{id}/code-index/rebuild` | `{repository_id, sha?, kind: CANDIDATE}` (`sha` defaults to `canonical_commit`); HUMAN/SYSTEM; `kind: CANONICAL` → 422 `CANONICAL_INDEX_RESERVED` (Phase 08 services only); 422 `REPOSITORY_NOT_READY` unless the Repository is READY |
| GET | `/repositories/{id}/code-index/versions` | |
| GET | `/code-index/versions/{id}` | stats, hash |
| GET | `/code/entities?index_version_id=&type=&file=&q=` | |
| GET | `/code/entities/{id}` | entity + direct relations (both directions) |
| GET | `/code/entities/{id}/neighbors?relation=&direction=in|out|both&depth=1..4` | structural traversal |
| GET | `/code/search?q=&mode=symbol|lexical|route&index_version_id=` | results include `retrieval_source`, `score`, `provenance` |
| GET | `/code/paths?from=&to=&relations=` | shortest structural path (BFS, bounded depth) |

```python
class CodeIndexer:
    async def build(self, repository_id: uuid.UUID, sha: str, kind: IndexKind, source: IndexSource, scope_ref: str = "") -> CodeIndexVersion
class StructuralRetrieval:
    async def neighbors(self, entity_id, relations: set[RelationType] | None, direction, depth) -> list[RetrievalHit]
    async def path(self, from_id, to_id, relations, max_depth=6) -> list[RetrievalHit] | None
class LexicalRetrieval:
    async def search(self, index_version_id, q: str, mode: str, limit=20) -> list[RetrievalHit]
class RetrievalHit(BaseModel):
    entity_id: uuid.UUID; stable_key: str; type: EntityType; retrieval_source: Literal["STRUCTURAL","LEXICAL","SEMANTIC"]
    score: float; path: list[str] = []; provenance: list[str]; index_version_id: uuid.UUID; commit_sha: str
```

Events: `code_index.build_started`, `code_index.ready` (TECH `code_index.updated` is emitted by Phase 08 for canonical updates), `code_index.failed`.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/intelligence/repository/git_source.py` | read tree/blobs at SHA from the locator-resolved canonical RepositoryWorkspace |
| `core/intelligence/code_index/parsers/python_ast.py`, `imports.py`, `calls.py`, `inheritance.py` | core extraction |
| `core/intelligence/code_index/parsers/frameworks/{fastapi_routes,pydantic_schemas,sqlalchemy_models,pytest_tests}.py` | framework extractors |
| `core/intelligence/code_index/parsers/git_metadata.py` | file history metadata |
| `core/intelligence/code_index/entities/`, `relations/` | models, repositories, stable keys |
| `core/intelligence/code_index/indexer.py` | orchestration, hashing, persistence (bulk insert via `COPY`/`executemany`) |
| `core/intelligence/code_index/retrieval/{structural,lexical,types}.py` | retrieval |
| `apps/control_api/routers/code_intelligence.py` | REST |
| `tests/fixtures/repos/supportdesk_r1/`, `supportdesk_r1.expected_index.json`, `tests/fixtures/repos/indexer_edge_cases/` | fixtures |

## 10. Development Tasks

- [ ] 07.1 Add migration `0016` and the models, including the immutability trigger for READY versions.
- [ ] 07.2 Implement the `git_source` blob/tree reader at an exact SHA.
- [ ] 07.3 Write the `supportdesk_r1` fixture repository. Tests materialize it with Phase 01's `materialize_fixture_repository(fixture_dir) -> (repository, sha)` (an EXTERNAL_CLONE of a temp `file://` origin), never by indexing a fixture directory directly.
- [ ] 07.4 Implement `python_ast` extraction (modules, classes, methods, functions, spans, public flag, content hash).
- [ ] 07.5 Implement import resolution and `IMPORTS`.
- [ ] 07.6 Implement call resolution and `CALLS` with confidence.
- [ ] 07.7 Implement `INHERITS`.
- [ ] 07.8 Implement the FastAPI routes extractor (router prefixes, `include_router`) and `EXPOSES`.
- [ ] 07.9 Implement the Pydantic schema extractor and `USES_SCHEMA`.
- [ ] 07.10 Implement the SQLAlchemy model/table extractor and `MAPS_TO`/`ACCESSES`.
- [ ] 07.11 Implement the pytest extractor and `VERIFIED_BY` (symbol and route path matching).
- [ ] 07.12 Implement Git metadata.
- [ ] 07.13 Implement the `CodeIndexer` orchestration with deterministic ordering and content hash. Parse errors are recorded per file and do not abort the build unless more than `policy.index.max_parse_error_ratio` of files fail.
- [ ] 07.14 Implement structural and lexical retrieval with `RetrievalHit` provenance.
- [ ] 07.15 Add the REST routes and events.
- [ ] 07.16 Write the golden-file and determinism tests.

## 11. LLM-Dependent Tasks

No LLM dependency in this phase. Indexing and retrieval are deterministic by design (ARCH §14.3; semantic retrieval is Phase 13).

## 12. Testing Strategy

### Unit Tests
- One test per extractor, using `tests/fixtures/repos/indexer_edge_cases/`: relative imports, aliased imports, nested classes, decorators, router prefixes, `include_router`, Pydantic inheritance, SQLAlchemy 2.0 `Mapped[...]` style, pytest classes and parametrize.
- Stable key formation.
- Retrieval ranking and provenance fields.

### Persistence Tests
- READY index immutability.
- Bulk insert of more than 5k entities completes within a time budget (performance smoke: under 10 s locally).

### Integration Tests
- Golden test: indexing `supportdesk_r1` at its SHA matches `expected_index.json` exactly (stable keys and relations).
- Determinism: indexing the same SHA twice (fresh DB rows) gives an identical `content_hash`.
- SHA binding: modify a file and commit, then index both SHAs. The versions differ, the old version is unchanged, and entity `content_hash` differs only for changed entities.
- Working-tree independence: create a temporary worktree from the canonical workspace and write an uncommitted change. Indexing the SHA ignores it, and the hash is unchanged.
- Canonical reservation: `POST /code-index/rebuild` with `kind: CANONICAL` → 422 `CANONICAL_INDEX_RESERVED`. A direct `CodeIndexer.build(kind=CANONICAL)` without the Phase 08 capability raises.
- No source bodies persisted: after indexing `supportdesk_r1`, no `code_entities`/`code_relations`/`code_index_versions` column contains a distinctive source line from the fixture (for example the body line of `TicketService.update_status`).
- Expected traversals on `supportdesk_r1` (from `route POST /tickets`):
  - `EXPOSES → create_ticket handler → CALLS → TicketService.create → CALLS → TicketRepository.add → ACCESSES → Ticket ORM_MODEL → MAPS_TO → tickets TABLE`;
  - `VERIFIED_BY → test_create_ticket`.
- Search: `q=update_status` returns the method with `retrieval_source=LEXICAL`.

### Security Tests
- The indexer never imports repository modules. A fixture module with a top-level `raise SystemExit` / file-write side effect is indexed without side effects.
- Path traversal in tree entries (`../`) is ignored.

### Commands
```
make check
uv run pytest tests/integration/code_index tests/unit/code_index
```

## 13. Milestone

Given any registered Python repository (materialized in its canonical RepositoryWorkspace) and an exact commit SHA, Olympus deterministically builds an immutable, SHA-bound Code Intelligence Index of packages, modules, files, classes, methods, functions, FastAPI routes, Pydantic schemas, SQLAlchemy models/tables and pytest tests. Their contains/imports/calls/inherits/accesses/exposes/verified_by relations match the golden SupportDesk fixture, and the index is queryable through structural and lexical retrieval APIs that report retrieval source and provenance.

## 14. Acceptance Criteria

- [ ] Index content is reproducible: the same `(repository, sha)` gives an identical `content_hash`.
- [ ] Every CodeIndexVersion records the exact `commit_sha`, `kind` and `source`. CANDIDATE and CANONICAL are distinguishable in schema and API.
- [ ] The golden `supportdesk_r1` index matches all expected entities and relations.
- [ ] The route → handler → service → repository → model → table chain is traversable for every SupportDesk route.
- [ ] Test entities are linked via `VERIFIED_BY` to the symbols and routes they exercise.
- [ ] Every retrieval result includes `retrieval_source`, `index_version_id`, `commit_sha` and provenance.
- [ ] Repository code is never executed or imported during indexing.
- [ ] READY index versions are immutable.
- [ ] Indexes are built from Git objects of the Repository's canonical RepositoryWorkspace at the exact SHA. Uncommitted working-tree content is never indexed, and no source-file bodies are persisted in index tables.
- [ ] Only CANDIDATE versions can be created outside Phase 08's `CanonicalIndexService`.

## 15. Exit Criteria

- §14 green.
- The `stable_key` format and `RetrievalHit` contract are frozen (08, 11, 13 and 15 depend on them).
- `STATUS.md` updated: Code Intelligence technical tracker items checked.

## 16. Dependencies

### Depends On
- 01: Repository + RepositoryWorkspace entities, `WorkspaceLocator`, fixture materialization helper. Real materialization (Phase 04) is **not** required: the helper produces an equivalent bare canonical workspace.

### Blocks
- 08 (and transitively 09+). Phase 11 also depends on it directly.

### Can Run In Parallel With
- 02, 03, 04, 05, 06. Its only dependency is Phase 01 and it shares no modules with them. Coordinate migration revision ordering at merge.

## 17. Risks / Implementation Notes

- **Static call resolution is incomplete.** This is accepted for the MVP (TECH §13.1: "not perfect whole-program static analysis"). Record unresolved calls in metadata so Phase 13 can fall back to lexical/semantic expansion.
- **Framework idioms** vary. Restrict guaranteed support to the patterns in the edge-case fixture, and document unsupported patterns in `core/intelligence/code_index/SUPPORTED_PATTERNS.md`.
- **Storage growth:** per-version full copies. Accept for the MVP, and Phase 08 discards candidate versions after integration.
- **Deferred:** incremental indexing and embeddings (13).

## 18. Deliverables

- Code: `core/intelligence/repository/git_source.py`, `core/intelligence/code_index/**`.
- Migration: `0016`.
- APIs/events: §8.
- Fixtures: `supportdesk_r1` repo + golden index, `indexer_edge_cases`.
- Docs: `SUPPORTED_PATTERNS.md`.
- Tests: §12 suites.
