# Phase 02 — ModelRouter, AgentRuntime and Live LLM Infrastructure

## 1. Objective

Introduce the provider-neutral model and runtime boundary from TECH §10:

- **ModelRouter**: alias-based model selection, provider adapters (Anthropic required, OpenAI optional), structured output validated against Pydantic schemas, retries with validation-error feedback, and token/latency/cost capture.
- The **AgentRuntime** protocol (`run`, `resume`, `cancel`, `stream`) and the initial **LangGraphRuntime** adapter.
- The **AgentProfile** registry and **prompt template versioning**.
- **Model-call audit records**.
- The **live-LLM test lane**, enforced by `--live-required`.

It exists so that every model-dependent capability in later phases (Kira, Atlas, Scout, Forge, Warden, Sentinel, Orchestrator) calls a real configured provider through one audited path. Runtime state stays explicitly non-authoritative.

## 2. Architectural Context

- **Position:** Execution plane, inside the runtime boundary (ARCH §3: EXECUTION WORKER → AGENT RUNTIME; TECH §3: AgentRuntime → ModelRouter → Live LLM provider APIs).
- **Upstream:** 00 (config, DB) and 01 (contract schema `TaskContractBody`, events, audit).
- **Downstream:** 03 (the worker invokes AgentRuntime), 04 (Forge tool loop), and 05, 06, 09, 11, 12, 13 (embedding), 14, 15 and 17 (agents).
- **Invariants:**
  - 1: LangGraph checkpoints are execution-local metadata, never canonical state.
  - 13: the agent does not decide authorization.
  - LLM Execution Policy: real provider for model-dependent behavior. Free-form prose may be stored as an artifact, but canonical entities come only from validated structured output.

## 3. Current Repository Assessment

Inspection on 2026-10-01: no runtime, provider, LangGraph or agent code exists.

### Existing
- (after 00/01) settings with model env vars, `canonical_json`, events and audit — **RETAIN/EXTEND**.

### Partial
- None.

### Missing
- ModelRouter, providers, structured output, AgentRuntime, LangGraphRuntime, profiles, prompts, model_calls and the live test lane — **ADD**.

### Refactor / Migration Required
- None.

| Component | Classification |
|---|---|
| `core/runtime/model_router.py`, `model_policy.py`, `structured_output.py`, `usage.py`, `budget.py` | ADD |
| `core/runtime/providers/{base,anthropic_provider,openai_provider,fake_provider}.py` | ADD |
| `core/runtime/agent_runtime.py`, `langgraph_runtime.py`, `agent_profiles.py`, `context.py`, `tool_client.py` (protocol only) | ADD |
| `core/runtime/prompts/registry.py` + `agents/*/prompts/` convention | ADD |
| `core/domain/model_calls/` + migration `0005` | ADD |
| `config/models.yaml`, `config/model_pricing.yaml` | ADD |
| `tests/plugins/live_guard.py`; CI `live` job | ADD / EXTEND |

## 4. Scope

1. `ModelRequest` / `ModelResult` contracts (TECH §10.3) plus `EmbeddingRequest` / `EmbeddingResult`.
2. `ModelPolicy`: resolves an alias to `(provider, model, max_output_tokens, temperature)` from `config/models.yaml` with env overrides (`MODEL_*`). Aliases (D-11): `product_decomposition`, `planning`, `architecture`, `repository_reasoning`, `implementation`, `review`, `verification_planning`, `orchestration`, `embedding`.
3. `AnthropicProvider`, which uses tool-use / JSON-schema structured output. `OpenAIProvider` (optional, but required for the `embedding` alias if Anthropic is the chat provider; see Q-04) uses `response_format=json_schema` and embeddings.
4. Structured-output loop: provider-native schema, then Pydantic validation, then on failure a retry with validation errors appended. The bound is `max_schema_retries` (default 2). Transport retries for 429/5xx/timeouts use exponential backoff and jitter (default 3), honoring `retry-after`.
5. Usage and cost: tokens, latency, `provider_request_id`, cost estimate from `config/model_pricing.yaml` and retry counts, persisted in `model_calls`.
6. Budget enforcement: per-execution `budgets` from TaskContract, plus a global `LLM_TEST_BUDGET_USD` for live tests. A call that would exceed the budget fails with `BudgetExceeded` before it is sent.
7. `AgentRuntime` protocol and data contracts (`AgentRunRequest`, `AgentResumeRequest`, `AgentRunResult`, `AgentEvent`).
8. `LangGraphRuntime`. It builds a graph from `AgentProfile.graph_factory`, uses a Postgres checkpointer in schema `langgraph_runtime` (non-authoritative), and supports streaming events, cooperative cancellation and resume from a **continuation package**. The LangGraph checkpoint is an optimization only.
9. `AgentProfile` registry: name, description, model alias, prompt template IDs, allowed tools, output schema, graph factory and max steps.
10. Prompt template registry: templates as Markdown files in `agents/<agent>/prompts/<name>.md` with front-matter `id`, `version`, and a computed sha256 hash recorded on each model call.
11. `ToolGatewayClient` **protocol only**, plus `DenyAllToolGateway` (real implementation in Phase 04).
12. `FakeProvider` for unit tests only, refused outside `OLYMPUS_ENV ∈ {local, test}`.
13. Diagnostic profile `diagnostic.structured_echo`: a minimal live structured-output agent used by Phase 02 and 03 platform tests. It summarizes supplied text into `DiagnosticSummary`.
14. Pytest plugin `live_guard` (`--live-required`), the CI `live` job (manual dispatch with secrets) and cost reporting at the end of the session.

## 5. Out of Scope

- Execution records, snapshot and lease (Phase 03). In this phase `model_calls.execution_id` is nullable, and an FK is added in Phase 03.
- The real ToolGateway (Phase 04) and all domain agents (later phases).
- Advanced routing or cost optimization (ARCH §25 non-goal).

### Do Not Change
- Do not hard-code a model name in domain or agent code (TECH Appendix A). Always resolve through an alias.
- Do not persist secrets or raw API keys in `model_calls`, artifacts or logs.

## 6. Domain / Data Model Changes

Migration `0005_p02_model_calls.py`:

```python
class ModelCall(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "model_calls"
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        index=True
    )  # FK added in 0006 (Phase 03)
    project_id: Mapped[uuid.UUID | None]
    delivery_cycle_id: Mapped[uuid.UUID | None]
    agent_profile: Mapped[str]
    purpose: Mapped[str]
    alias: Mapped[str]
    provider: Mapped[str]
    model: Mapped[str]
    prompt_template_id: Mapped[str | None]
    prompt_template_version: Mapped[str | None]
    prompt_hash: Mapped[str]
    output_schema: Mapped[str | None]
    output_schema_hash: Mapped[str | None]
    status: Mapped[str]  # SUCCEEDED | FAILED_SCHEMA | FAILED_PROVIDER | BUDGET_EXCEEDED | CANCELLED
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int] = mapped_column(default=0)
    cost_usd_estimate: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    transport_retries: Mapped[int] = mapped_column(default=0)
    schema_retries: Mapped[int] = mapped_column(default=0)
    validation_errors: Mapped[list | None] = mapped_column(JSONB)
    provider_request_id: Mapped[str | None]
    correlation_id: Mapped[str]
    response_artifact_ref: Mapped[str | None]  # content-addressed path, per retention policy
    __table_args__ = (Index("ix_model_calls_exec", "execution_id", "created_at"),)
```

Immutable after insert (trigger from Phase 01).

Retention policy: `config/models.yaml: retention: {store_prompts: hash_only|full, store_responses: structured_only|full}`. The default is `hash_only` / `structured_only` (TECH §24.3).

Contracts:

```python
class ContextItem(BaseModel):
    kind: Literal["TEXT", "CODE", "SPEC", "FACT", "ARTIFACT", "INSTRUCTION"]
    content: str
    source_ref: str | None = None
    provenance: Literal["DETERMINISTIC", "HUMAN", "AGENT", "SOURCE_DOCUMENT"] | None = None


class ModelRequest(BaseModel):
    purpose: str
    alias: str
    system_instructions: str
    context: list[ContextItem]
    output_schema: type[BaseModel] | None
    max_output_tokens: int | None = None
    temperature: float | None = None
    tools: list[ToolSpec] = []  # for tool-calling turns (Phase 04)
    metadata: dict[
        str, str
    ] = {}  # execution_id, project_id, prompt_template_id/version, correlation_id


class ModelResult(BaseModel):
    parsed_output: BaseModel | None
    raw_text: str | None
    tool_calls: list[ToolCall] = []
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    provider_request_id: str | None
    model_call_id: uuid.UUID
    cost_usd_estimate: Decimal


class AgentRunRequest(BaseModel):
    run_id: uuid.UUID  # == execution_id when invoked by worker
    agent_profile: str
    contract: TaskContractBody | None
    snapshot: dict | None  # ExecutionSnapshot content (Phase 03)
    context: list[ContextItem]
    workspace_path: str | None  # worktree (Phase 04); None for ANALYSIS w/o repo
    continuation: dict | None = None  # ContinuationPackage (Phase 03)


class AgentRunResult(BaseModel):
    run_id: uuid.UUID
    status: Literal["OUTPUT_PRODUCED", "CHECKPOINT_REQUESTED", "FAILED", "CANCELLED"]
    output: dict | None
    output_schema: str | None
    checkpoint_request: CheckpointRequest | None = None
    artifacts: list[ArtifactProposal] = []
    model_call_ids: list[uuid.UUID] = []
    runtime_metadata: dict = {}  # e.g. langgraph thread/checkpoint ids — NON-AUTHORITATIVE
    error: RuntimeErrorInfo | None = None


class AgentEvent(BaseModel):
    run_id: uuid.UUID
    seq: int
    type: Literal[
        "MODEL_CALL_STARTED",
        "MODEL_CALL_COMPLETED",
        "TOOL_REQUESTED",
        "TOOL_RESULT",
        "PROGRESS",
        "CHECKPOINT_REQUESTED",
        "OUTPUT_PROPOSED",
        "ERROR",
    ]
    payload: dict
    at: datetime
```

## 7. State / Lifecycle Changes

No canonical lifecycle changes. Runtime-local states (`RUNNING → OUTPUT_PRODUCED | CHECKPOINT_REQUESTED | FAILED | CANCELLED`) are returned to the caller. The authoritative Execution state machine (Phase 03) maps them. The runtime never writes Olympus state.

## 8. API / Contract Changes

```python
class ModelProvider(Protocol):
    name: str
    async def complete(self, req: ProviderRequest) -> ProviderResponse: ...
    async def embed(self, texts: list[str], model: str) -> list[list[float]]: ...

class ModelRouter:
    async def invoke(self, req: ModelRequest) -> ModelResult           # structured or tool-calling
    async def embed(self, alias: str, texts: list[str], metadata: dict) -> EmbeddingResult

class AgentRuntime(Protocol):
    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...
    async def resume(self, request: AgentResumeRequest) -> AgentRunResult: ...
    async def cancel(self, run_id: str) -> None: ...
    async def stream(self, run_id: str) -> AsyncIterator[AgentEvent]: ...

class ToolGatewayClient(Protocol):
    async def request(self, tool: str, params: dict) -> ToolResult: ...   # implemented in Phase 04

@dataclass(frozen=True)
class AgentProfile:
    name: str; model_alias: str; prompt_templates: tuple[str, ...]; output_schema: type[BaseModel] | None
    allowed_tools: tuple[str, ...]; graph_factory: Callable[[GraphDeps], CompiledGraph]; max_steps: int = 40
```

Errors are classified as `ProviderTransientError` (retry), `ProviderRateLimited` (retry with retry-after), `ProviderAuthError` (no retry), `SchemaValidationFailed` (schema retry, then fail), `BudgetExceeded` and `RuntimeCancelled`.

There are no REST endpoints in this phase. Read access to model calls (`GET /executions/{id}/model-calls`) arrives in Phase 03.

Events: `model_call.completed` and `model_call.failed` (domain events with project/cycle/execution correlation where present).

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/runtime/model_router.py` | invoke/embed; policy resolution; retries; budget; persistence of `model_calls`; emits events |
| `core/runtime/model_policy.py` | alias → provider/model; reads `config/models.yaml` + `MODEL_*` env |
| `core/runtime/structured_output.py` | schema → JSON schema; validation; error-feedback prompt construction |
| `core/runtime/usage.py` | token accounting; `config/model_pricing.yaml` cost estimate |
| `core/runtime/budget.py` | per-run and per-session budget ledger |
| `core/runtime/providers/anthropic_provider.py` | `anthropic` SDK async client via httpx; tool-use structured output |
| `core/runtime/providers/openai_provider.py` | `openai` SDK; `json_schema` response format; embeddings |
| `core/runtime/providers/fake_provider.py` | scripted responses for unit tests; constructor raises unless env allows |
| `core/runtime/agent_runtime.py` | protocol + contracts |
| `core/runtime/langgraph_runtime.py` | LangGraph adapter; checkpointer in `langgraph_runtime` schema; event stream; cancel |
| `core/runtime/agent_profiles.py` | registry + `register_profile()` |
| `core/runtime/prompts/registry.py` | load/hash templates; render with Jinja2 (`StrictUndefined`) |
| `core/runtime/tool_client.py` | `ToolGatewayClient` protocol + `DenyAllToolGateway` |
| `core/runtime/profiles/diagnostic.py`, `prompts/diagnostic_structured_echo.md` | diagnostic profile |
| `tests/plugins/live_guard.py` | `--live-required`; live budget report |

New dependencies: `anthropic`, `openai` (optional extra), `langgraph`, `langgraph-checkpoint-postgres`, `jinja2`, `tenacity` (or a hand-rolled retry).

## 10. Development Tasks

- [ ] 02.1 Add the `model_calls` model and migration `0005`, and attach the immutability trigger.
- [ ] 02.2 Write `config/models.yaml` (all aliases default to `${MODEL_DEFAULT}`) and `config/model_pricing.yaml`.
- [ ] 02.3 Implement `ModelPolicy` alias resolution. Unknown alias → `ConfigError`.
- [ ] 02.4 Implement the `ModelProvider` protocol and `AnthropicProvider` (structured output via a single forced tool whose input schema is the Pydantic JSON schema).
- [ ] 02.5 Implement `OpenAIProvider` (structured output plus embeddings). Enable it with the `MODEL_PROVIDER=openai` or `MODEL_EMBEDDING` alias.
- [ ] 02.6 Implement `structured_output.validate_or_feedback()` and the schema-retry loop.
- [ ] 02.7 Implement transport retry and error classification.
- [ ] 02.8 Implement usage and cost calculation and budget enforcement.
- [ ] 02.9 Implement `ModelRouter.invoke/embed`, persisting a `model_calls` row on success **and** failure, and emitting events.
- [ ] 02.10 Implement the prompt registry with front-matter version and hash.
- [ ] 02.11 Implement the `AgentRuntime` contracts and `AgentProfile` registry.
- [ ] 02.12 Implement `LangGraphRuntime.run/resume/cancel/stream` using `AsyncPostgresSaver` in schema `langgraph_runtime`. Resume must work with a continuation package **without** a LangGraph checkpoint: if the checkpoint is missing, rebuild from `continuation`.
- [ ] 02.13 Implement `ToolGatewayClient` protocol + `DenyAllToolGateway`.
- [ ] 02.14 Implement `FakeProvider` with an environment guard.
- [ ] 02.15 Implement the `diagnostic.structured_echo` profile and prompt.
- [ ] 02.16 Implement the `live_guard` pytest plugin and update the CI `live` job (secrets `ANTHROPIC_API_KEY`, optional `OPENAI_API_KEY`).
- [ ] 02.17 Write the tests in §12.

## 11. LLM-Dependent Tasks

| Item | Detail |
|---|---|
| Why model reasoning | This phase builds the model invocation path itself. The live test proves the real provider path works end to end. |
| Input context | `diagnostic.structured_echo`: a short fixture text (`tests/fixtures/diagnostic/paragraph.txt`). |
| Structured output | `DiagnosticSummary{title: str, bullet_points: list[str] (1..5), word_count_estimate: int}` |
| Runtime | `LangGraphRuntime` (one-node graph) plus a direct `ModelRouter.invoke` test |
| Model alias | `verification_planning` (any alias works; all point at `MODEL_DEFAULT`) |
| Path | `LangGraphRuntime → ModelRouter → AnthropicProvider → Anthropic API` |
| Validation | Pydantic plus a bullet count invariant |
| Retries | schema ≤ 2, transport ≤ 3 |
| Failure handling | `model_calls.status` set; `AgentRunResult.status=FAILED` with classified error |
| Cost/token logging | `model_calls` row; session cost summary printed by `live_guard` |
| Live acceptance test | `tests/integration/live_llm/test_model_router_live.py`, `test_langgraph_runtime_live.py` (`@pytest.mark.live_llm`) |

## 12. Testing Strategy

### Unit Tests (FakeProvider permitted)
- Invalid JSON, then corrected on retry 1. `schema_retries=1` is persisted.
- Malformed output persisting beyond the retry limit raises `SchemaValidationFailed`. `model_calls.status=FAILED_SCHEMA` with validation errors.
- 429 with retry-after is retried. 401 is not retried.
- Timeout is retried up to the limit, then `FAILED_PROVIDER`.
- Budget exceeded before the call raises `BudgetExceeded`, and no provider call is made.
- Alias resolution and env override.
- `FakeProvider` construction with `OLYMPUS_ENV=journey` raises.
- Prompt hash changes when the template changes. Rendering with a missing variable raises.

### Persistence Tests
- A `model_calls` row is immutable. Failure paths persist rows.

### Runtime / Live-LLM Tests (`live_llm`)
- A real `ModelRouter.invoke` returns a validated `DiagnosticSummary`, and `model_calls` has a non-null `provider_request_id`, tokens > 0 and cost > 0.
- `LangGraphRuntime.run` with `diagnostic.structured_echo` returns `OUTPUT_PRODUCED` and streams the expected event types.
- `cancel` during a run results in `CANCELLED`.
- Resume after **truncating** `langgraph_runtime.*` tables, using only the continuation package, still produces valid output (runtime state is non-authoritative).
- Embedding (if the `embedding` alias is configured) returns vectors of the configured dimension.

### Security Tests
- No log line or `model_calls` column contains the API key (grep test over captured logs).
- `agents/*` imports are still clean (`lint-imports`).

### Commands
```
make check
LLM_LIVE_TESTS=1 uv run pytest -m live_llm --live-required tests/integration/live_llm
```

## 13. Milestone

A real configured provider returns schema-validated structured output through `LangGraphRuntime → ModelRouter → provider`. Every call (successful or failed) is persisted with alias, model, prompt version/hash, tokens, latency, cost and provider request ID. Wiping LangGraph runtime state does not prevent resume from a continuation package.

## 14. Acceptance Criteria

- [ ] All model selection goes through aliases, and no model ID literal appears outside `config/`.
- [ ] A live structured-output call succeeds and is persisted with `provider_request_id`, tokens and cost.
- [ ] Schema-invalid output is retried with validation feedback up to the bound, then fails with a persisted record.
- [ ] Transient, rate-limit and auth errors are classified and retried or failed according to policy (unit-tested with FakeProvider).
- [ ] Budget enforcement blocks calls that would exceed the configured budget.
- [ ] `FakeProvider` cannot be constructed when `OLYMPUS_ENV` is `integration` or `journey`.
- [ ] `--live-required` turns skipped live tests into failures.
- [ ] `LangGraphRuntime` supports run, stream, cancel and resume. Resume works after LangGraph checkpoint tables are truncated.
- [ ] No secrets appear in logs or `model_calls`.

## 15. Exit Criteria

- §14 criteria are green, and the live suite has passed at least once with real credentials (evidence: CI run ID or local command output recorded in `STATUS.md`).
- The `AgentRuntime`, `ModelRouter`, `AgentProfile` and `ToolGatewayClient` interfaces are frozen for Phase 03/04 consumption.
- `STATUS.md` §10 Live LLM Readiness is updated (provider, aliases, credentials, validation, retry, token and cost tracking).

## 16. Dependencies

### Depends On
- 01: `TaskContractBody`, events/audit, immutability trigger.

### Blocks
- 03 (the worker invokes AgentRuntime) and every agent phase.

### Can Run In Parallel With
- 07 (Code Intelligence Index). It shares no modules and only depends on 01.

## 17. Risks / Implementation Notes

- **Model risk:** structured-output reliability differs by provider. Keep schemas flat where possible and use `extra="forbid"`.
- **Embedding provider (Q-04):** Anthropic has no embeddings API. Phase 13 needs an `embedding` alias backed by OpenAI or a local model (`fastembed`). Decide before Phase 13.
- **LangGraph version churn:** pin versions. Isolate all LangGraph imports inside `langgraph_runtime.py` and the `agents/*/graph.py` files.
- **Cost:** live suites must use small fixtures. Enforce `LLM_TEST_BUDGET_USD`.
- **Concurrency:** the provider client must be shared per process with connection pooling.

## 18. Deliverables

- Code: `core/runtime/*`, `core/runtime/providers/*`, `core/runtime/profiles/diagnostic.py`.
- Migration: `0005_p02_model_calls.py`.
- Config: `config/models.yaml`, `config/model_pricing.yaml`, `.env.example` additions.
- Contracts: `ModelRequest/Result`, `AgentRunRequest/Result`, `AgentEvent`, `AgentProfile`, `ToolGatewayClient`.
- Events: `model_call.completed`, `model_call.failed`.
- Tests: unit (FakeProvider), persistence, live_llm suite, `tests/plugins/live_guard.py`.
- CI: the `live` job.
