from __future__ import annotations

import asyncio
import random
import time
import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.canonical_json import sha256_hex
from core.domain.events.append import append_domain_event
from core.domain.model_calls.models import ModelCall
from core.runtime.budget import BudgetLedger, get_budget_ledger
from core.runtime.contracts import (
    ContextItem,
    EmbeddingRequest,
    EmbeddingResult,
    ModelRequest,
    ModelResult,
    ProviderRequest,
)
from core.runtime.errors import (
    BudgetExceeded,
    ProviderAuthError,
    ProviderRateLimited,
    ProviderTransientError,
    RuntimeCancelled,
    SchemaValidationFailed,
)
from core.runtime.model_policy import ModelPolicy, ResolvedModel
from core.runtime.providers.base import ModelProvider
from core.runtime.structured_output import (
    STRUCTURED_OUTPUT_TOOL,
    schema_hash,
    validate_or_feedback,
    validation_feedback_message,
)
from core.runtime.usage import estimate_cost_usd, estimate_max_cost_usd


def _context_to_user_text(context: list[ContextItem]) -> str:
    parts: list[str] = []
    for item in context:
        parts.append(f"[{item.kind}] {item.content}")
    return "\n\n".join(parts)


def _prompt_hash(system: str, context: list[ContextItem]) -> str:
    return sha256_hex({"system": system, "context": [c.model_dump() for c in context]})


class ModelRouter:
    def __init__(
        self,
        session: AsyncSession,
        *,
        actor_id: uuid.UUID,
        providers: dict[str, ModelProvider],
        policy: ModelPolicy | None = None,
        budget: BudgetLedger | None = None,
        default_correlation_id: str = "model-router",
    ) -> None:
        self._session = session
        self._actor_id = actor_id
        self._providers = providers
        self._policy = policy or ModelPolicy()
        self._budget = budget or get_budget_ledger()
        self._default_correlation_id = default_correlation_id

    def _provider(self, name: str) -> ModelProvider:
        if name not in self._providers:
            raise ProviderAuthError(f"No provider registered for {name}")
        return self._providers[name]

    async def invoke(self, req: ModelRequest) -> ModelResult:
        resolved = self._policy.resolve(req.alias)
        metadata_boot = dict(req.metadata)
        from core.observability.instrumentation import model_call_span

        exec_id = metadata_boot.get("execution_id")
        with model_call_span(
            alias=resolved.alias,
            provider=resolved.provider,
            model=resolved.model,
            execution_id=str(exec_id) if exec_id else None,
        ):
            return await self._invoke_inner(req, resolved)

    async def _invoke_inner(self, req: ModelRequest, resolved: ResolvedModel) -> ModelResult:
        provider = self._provider(resolved.provider)
        max_tokens = req.max_output_tokens or resolved.max_output_tokens
        temperature = req.temperature if req.temperature is not None else resolved.temperature

        metadata = dict(req.metadata)
        correlation_id = metadata.get("correlation_id", self._default_correlation_id)
        execution_key = metadata.get("execution_id", correlation_id)
        budget_key = execution_key

        if "budget_usd" in metadata:
            self._budget.set_limit(budget_key, float(metadata["budget_usd"]))

        prompt_hash = metadata.get("prompt_hash") or _prompt_hash(
            req.system_instructions, req.context
        )
        user_content = _context_to_user_text(req.context)

        schema_retries = 0
        transport_retries = 0
        validation_errors: list[dict[str, object]] | None = None
        feedback_suffix = ""
        model_call_id = uuid.uuid4()
        start = time.perf_counter()

        status = "SUCCEEDED"
        parsed: BaseModel | None = None
        raw_text: str | None = None
        provider_request_id: str | None = None
        input_tokens = 0
        output_tokens = 0
        cost = Decimal("0")

        try:
            while schema_retries <= resolved.max_schema_retries:
                attempt_user = user_content
                if feedback_suffix:
                    attempt_user = f"{user_content}\n\n{feedback_suffix}"

                estimate = estimate_max_cost_usd(resolved.model, len(attempt_user) // 4, max_tokens)
                self._budget.check_and_reserve(budget_key, estimate)

                provider_req = ProviderRequest(
                    model=resolved.model,
                    system=req.system_instructions,
                    user_content=attempt_user,
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    output_schema=req.output_schema,
                    tools=req.tools,
                )

                transport_retries_ref: dict[str, int] = {"count": transport_retries}
                response = await self._complete_with_transport_retries(
                    provider,
                    provider_req,
                    resolved,
                    transport_retries_ref,
                )
                transport_retries = transport_retries_ref["count"]

                input_tokens = response.input_tokens
                output_tokens = response.output_tokens
                provider_request_id = response.provider_request_id
                raw_text = response.raw_text

                gateway_tool_calls = [
                    tc for tc in response.tool_calls if tc.name != STRUCTURED_OUTPUT_TOOL
                ]
                if gateway_tool_calls and response.structured is None:
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    cost = estimate_cost_usd(resolved.model, input_tokens, output_tokens)
                    self._budget.record(budget_key, cost)
                    await self._persist_call(
                        model_call_id=model_call_id,
                        req=req,
                        resolved=resolved,
                        status=status,
                        prompt_hash=prompt_hash,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        cost=cost,
                        transport_retries=transport_retries,
                        schema_retries=schema_retries,
                        validation_errors=validation_errors,
                        provider_request_id=provider_request_id,
                        correlation_id=correlation_id,
                        response_payload={
                            "tool_calls": [t.model_dump() for t in gateway_tool_calls]
                        },
                    )
                    await self._emit_event(
                        succeeded=True,
                        model_call_id=model_call_id,
                        metadata=metadata,
                        correlation_id=correlation_id,
                        resolved=resolved,
                        cost=cost,
                    )
                    return ModelResult(
                        parsed_output=None,
                        raw_text=raw_text,
                        tool_calls=gateway_tool_calls,
                        provider=resolved.provider,
                        model=resolved.model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        provider_request_id=provider_request_id,
                        model_call_id=model_call_id,
                        cost_usd_estimate=cost,
                    )

                if req.output_schema is None:
                    parsed = None
                    break

                parsed_candidate, errors = validate_or_feedback(
                    req.output_schema, response.structured, raw_text
                )
                if parsed_candidate is not None:
                    parsed = parsed_candidate
                    break

                validation_errors = errors
                if schema_retries >= resolved.max_schema_retries:
                    status = "FAILED_SCHEMA"
                    raise SchemaValidationFailed(
                        "Structured output validation failed",
                        errors=errors,
                    )
                feedback_suffix = validation_feedback_message(errors)
                schema_retries += 1

            latency_ms = int((time.perf_counter() - start) * 1000)
            cost = estimate_cost_usd(resolved.model, input_tokens, output_tokens)
            self._budget.record(budget_key, cost)

            await self._persist_call(
                model_call_id=model_call_id,
                req=req,
                resolved=resolved,
                status=status,
                prompt_hash=prompt_hash,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost=cost,
                transport_retries=transport_retries,
                schema_retries=schema_retries,
                validation_errors=validation_errors,
                provider_request_id=provider_request_id,
                correlation_id=correlation_id,
                response_payload=parsed.model_dump() if parsed is not None else raw_text,
            )
            await self._emit_event(
                succeeded=True,
                model_call_id=model_call_id,
                metadata=metadata,
                correlation_id=correlation_id,
                resolved=resolved,
                cost=cost,
            )

            return ModelResult(
                parsed_output=parsed,
                raw_text=raw_text,
                provider=resolved.provider,
                model=resolved.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                provider_request_id=provider_request_id,
                model_call_id=model_call_id,
                cost_usd_estimate=cost,
            )
        except BudgetExceeded:
            status = "BUDGET_EXCEEDED"
            latency_ms = int((time.perf_counter() - start) * 1000)
            await self._persist_call(
                model_call_id=model_call_id,
                req=req,
                resolved=resolved,
                status=status,
                prompt_hash=prompt_hash,
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                cost=Decimal("0"),
                transport_retries=transport_retries,
                schema_retries=schema_retries,
                validation_errors=validation_errors,
                provider_request_id=None,
                correlation_id=correlation_id,
                response_payload=None,
            )
            await self._emit_event(
                succeeded=False,
                model_call_id=model_call_id,
                metadata=metadata,
                correlation_id=correlation_id,
                resolved=resolved,
                cost=Decimal("0"),
            )
            raise
        except SchemaValidationFailed as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            cost = estimate_cost_usd(resolved.model, input_tokens, output_tokens)
            self._budget.record(budget_key, cost)
            await self._persist_call(
                model_call_id=model_call_id,
                req=req,
                resolved=resolved,
                status="FAILED_SCHEMA",
                prompt_hash=prompt_hash,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost=cost,
                transport_retries=transport_retries,
                schema_retries=schema_retries,
                validation_errors=exc.errors,
                provider_request_id=provider_request_id,
                correlation_id=correlation_id,
                response_payload=raw_text,
            )
            await self._emit_event(
                succeeded=False,
                model_call_id=model_call_id,
                metadata=metadata,
                correlation_id=correlation_id,
                resolved=resolved,
                cost=cost,
            )
            raise
        except (ProviderAuthError, ProviderTransientError, RuntimeCancelled) as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            fail_status = "FAILED_PROVIDER"
            if isinstance(exc, RuntimeCancelled):
                fail_status = "CANCELLED"
            await self._persist_call(
                model_call_id=model_call_id,
                req=req,
                resolved=resolved,
                status=fail_status,
                prompt_hash=prompt_hash,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost=Decimal("0"),
                transport_retries=transport_retries,
                schema_retries=schema_retries,
                validation_errors=validation_errors,
                provider_request_id=provider_request_id,
                correlation_id=correlation_id,
                response_payload=None,
            )
            await self._emit_event(
                succeeded=False,
                model_call_id=model_call_id,
                metadata=metadata,
                correlation_id=correlation_id,
                resolved=resolved,
                cost=Decimal("0"),
            )
            raise

    async def embed(self, req: EmbeddingRequest) -> EmbeddingResult:
        resolved = self._policy.resolve(req.alias)
        provider = self._provider(resolved.provider)
        metadata = dict(req.metadata)
        correlation_id = metadata.get("correlation_id", self._default_correlation_id)
        budget_key = metadata.get("execution_id", correlation_id)
        model_call_id = uuid.uuid4()
        start = time.perf_counter()

        estimate = estimate_max_cost_usd(resolved.model, sum(len(t) for t in req.texts) // 4, 0)
        self._budget.check_and_reserve(budget_key, estimate)

        vectors, tokens, provider_request_id = await provider.embed(req.texts, resolved.model)
        latency_ms = int((time.perf_counter() - start) * 1000)
        cost = estimate_cost_usd(resolved.model, tokens, 0)
        self._budget.record(budget_key, cost)

        await self._persist_call(
            model_call_id=model_call_id,
            req=ModelRequest(
                purpose="embed",
                alias=req.alias,
                system_instructions="",
                context=[],
                metadata=metadata,
            ),
            resolved=resolved,
            status="SUCCEEDED",
            prompt_hash=sha256_hex({"texts": req.texts}),
            input_tokens=tokens,
            output_tokens=0,
            latency_ms=latency_ms,
            cost=cost,
            transport_retries=0,
            schema_retries=0,
            validation_errors=None,
            provider_request_id=provider_request_id,
            correlation_id=correlation_id,
            response_payload={"dimensions": len(vectors[0]) if vectors else 0},
        )
        await self._emit_event(
            succeeded=True,
            model_call_id=model_call_id,
            metadata=metadata,
            correlation_id=correlation_id,
            resolved=resolved,
            cost=cost,
        )

        return EmbeddingResult(
            vectors=vectors,
            provider=resolved.provider,
            model=resolved.model,
            input_tokens=tokens,
            latency_ms=latency_ms,
            provider_request_id=provider_request_id,
            model_call_id=model_call_id,
            cost_usd_estimate=cost,
        )

    async def _complete_with_transport_retries(
        self,
        provider: ModelProvider,
        req: ProviderRequest,
        resolved: ResolvedModel,
        transport_retries_ref: dict[str, int],
    ) -> Any:
        attempt = 0
        while True:
            try:
                return await provider.complete(req)
            except ProviderAuthError:
                raise
            except ProviderRateLimited as exc:
                if attempt >= resolved.max_transport_retries:
                    raise
                transport_retries_ref["count"] += 1
                attempt += 1
                await _sleep_backoff(attempt, exc.retry_after)
            except ProviderTransientError:
                if attempt >= resolved.max_transport_retries:
                    raise
                transport_retries_ref["count"] += 1
                attempt += 1
                await _sleep_backoff(attempt, None)

    async def _persist_call(
        self,
        *,
        model_call_id: uuid.UUID,
        req: ModelRequest,
        resolved: ResolvedModel,
        status: str,
        prompt_hash: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        cost: Decimal,
        transport_retries: int,
        schema_retries: int,
        validation_errors: list[dict[str, object]] | None,
        provider_request_id: str | None,
        correlation_id: str,
        response_payload: object | None,
    ) -> None:
        metadata = req.metadata
        retention = self._policy.retention
        response_ref: str | None = None
        if response_payload is not None:
            mode = retention.get("store_responses")
            if mode == "full" or (mode == "structured_only" and isinstance(response_payload, dict)):
                response_ref = sha256_hex(response_payload)

        output_schema_name = None
        output_schema_hash = None
        if req.output_schema is not None:
            output_schema_name = req.output_schema.__name__
            output_schema_hash = schema_hash(req.output_schema)

        execution_id = _uuid_or_none(metadata.get("execution_id"))
        project_id = _uuid_or_none(metadata.get("project_id"))
        delivery_cycle_id = _uuid_or_none(metadata.get("delivery_cycle_id"))
        if execution_id is not None:
            from core.domain.delivery_cycles.models import DeliveryCycle
            from core.domain.executions.models import Execution

            execution = await self._session.get(Execution, execution_id)
            if execution is None:
                execution_id = None
            else:
                if delivery_cycle_id is None:
                    delivery_cycle_id = execution.delivery_cycle_id
                if project_id is None:
                    cycle = await self._session.get(DeliveryCycle, execution.delivery_cycle_id)
                    if cycle is not None:
                        project_id = cycle.project_id

        from core.observability.metrics import LLM_SCHEMA_FAILURES, LLM_TOKENS
        from core.observability.retention import (
            retention_expires_at,
            should_store_raw_prompt,
            should_store_raw_response,
        )

        if validation_errors:
            LLM_SCHEMA_FAILURES.labels(alias=resolved.alias).inc()
        LLM_TOKENS.labels(alias=resolved.alias, direction="input").inc(input_tokens)
        LLM_TOKENS.labels(alias=resolved.alias, direction="output").inc(output_tokens)

        raw_prompt_ref: str | None = None
        raw_response_ref: str | None = None
        expires = retention_expires_at()
        if should_store_raw_prompt(retention):
            raw_prompt_ref = prompt_hash
        if should_store_raw_response(retention) and response_ref:
            raw_response_ref = response_ref

        row = ModelCall(
            id=model_call_id,
            execution_id=execution_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            agent_profile=metadata.get("agent_profile", "unknown"),
            purpose=req.purpose,
            alias=resolved.alias,
            provider=resolved.provider,
            model=resolved.model,
            prompt_template_id=metadata.get("prompt_template_id"),
            prompt_template_version=metadata.get("prompt_template_version"),
            prompt_hash=prompt_hash,
            output_schema=output_schema_name,
            output_schema_hash=output_schema_hash,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd_estimate=cost,
            transport_retries=transport_retries,
            schema_retries=schema_retries,
            validation_errors=validation_errors,
            provider_request_id=provider_request_id,
            correlation_id=correlation_id,
            response_artifact_ref=response_ref,
            raw_prompt_ref=raw_prompt_ref,
            raw_response_ref=raw_response_ref,
            retention_expires_at=expires if (raw_prompt_ref or raw_response_ref) else None,
        )
        self._session.add(row)
        await self._session.flush()

    async def _emit_event(
        self,
        *,
        succeeded: bool,
        model_call_id: uuid.UUID,
        metadata: dict[str, str],
        correlation_id: str,
        resolved: ResolvedModel,
        cost: Decimal,
    ) -> None:
        event_type = "model_call.completed" if succeeded else "model_call.failed"
        project_id = _uuid_or_none(metadata.get("project_id"))
        delivery_cycle_id = _uuid_or_none(metadata.get("delivery_cycle_id"))
        execution_id = _uuid_or_none(metadata.get("execution_id"))
        if execution_id is not None and (project_id is None or delivery_cycle_id is None):
            from core.domain.delivery_cycles.models import DeliveryCycle
            from core.domain.executions.models import Execution

            execution = await self._session.get(Execution, execution_id)
            if execution is not None:
                if delivery_cycle_id is None:
                    delivery_cycle_id = execution.delivery_cycle_id
                if project_id is None:
                    cycle = await self._session.get(DeliveryCycle, execution.delivery_cycle_id)
                    if cycle is not None:
                        project_id = cycle.project_id
        await append_domain_event(
            self._session,
            aggregate_type="model_call",
            aggregate_id=model_call_id,
            event_type=event_type,
            payload={
                "alias": resolved.alias,
                "provider": resolved.provider,
                "model": resolved.model,
                "cost_usd_estimate": str(cost),
            },
            actor_id=self._actor_id,
            correlation_id=correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )


async def _sleep_backoff(attempt: int, retry_after: float | None) -> None:
    if retry_after is not None:
        await asyncio.sleep(retry_after)
        return
    base = min(2**attempt, 30)
    jitter = random.uniform(0, 0.25 * base)
    await asyncio.sleep(base + jitter)


def _uuid_or_none(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    return uuid.UUID(value)


def build_providers(*, fake: ModelProvider | None = None) -> dict[str, ModelProvider]:
    if fake is not None:
        return {fake.name: fake}
    from core.config.settings import get_settings
    from core.runtime.providers.anthropic_provider import AnthropicProvider
    from core.runtime.providers.openai_provider import OpenAIProvider

    settings = get_settings()
    providers: dict[str, ModelProvider] = {}
    if settings.anthropic_api_key.get_secret_value():
        providers["anthropic"] = AnthropicProvider()
    if settings.openai_api_key.get_secret_value():
        providers["openai"] = OpenAIProvider()
    if not providers:
        raise ProviderAuthError(
            "No LLM providers configured (set API keys or use FakeProvider in tests)"
        )
    return providers
