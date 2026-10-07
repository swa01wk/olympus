from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from core.runtime.agent_profiles import get_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import (
    AgentEvent,
    AgentResumeRequest,
    AgentRunRequest,
    AgentRunResult,
    ContextItem,
    RuntimeErrorInfo,
)
from core.runtime.errors import RuntimeCancelled
from core.runtime.model_router import ModelRouter
from core.runtime.profiles.diagnostic import register_diagnostic_profile
from core.runtime.tool_client import DenyAllToolGateway, ToolGatewayClient


class LangGraphRuntime:
    def __init__(
        self,
        session: AsyncSession,
        model_router: ModelRouter,
        tool_gateway: ToolGatewayClient | None = None,
    ) -> None:
        self._session = session
        self._model_router = model_router
        self._tool_gateway = tool_gateway or DenyAllToolGateway()
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._event_queues: dict[str, asyncio.Queue[AgentEvent]] = {}
        self._seq: dict[str, int] = {}
        register_diagnostic_profile()

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        cancel_event = asyncio.Event()
        self._cancel_events[str(request.run_id)] = cancel_event
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._event_queues[str(request.run_id)] = queue
        self._seq[str(request.run_id)] = 0

        profile = get_profile(request.agent_profile)
        deps = GraphDeps(
            model_router=self._model_router,
            tool_gateway=self._tool_gateway,
            profile=profile,
            request=request,
            cancel_event=cancel_event,
            session=self._session,
        )

        initial_state = self._state_from_request(request)
        await self._emit(request.run_id, "PROGRESS", {"phase": "start"})

        try:
            compiled = profile.graph_factory(deps)
            config = {"configurable": {"thread_id": str(request.run_id)}}
            final_state = await compiled.ainvoke(initial_state, config=config)
            if cancel_event.is_set():
                return AgentRunResult(run_id=request.run_id, status="CANCELLED")

            checkpoint_raw = final_state.get("checkpoint_request")
            if checkpoint_raw is not None:
                from core.runtime.contracts import CheckpointRequest

                checkpoint = CheckpointRequest.model_validate(checkpoint_raw)
                await self._emit(
                    request.run_id,
                    "CHECKPOINT_REQUESTED",
                    {"questions": checkpoint.questions},
                )
                return AgentRunResult(
                    run_id=request.run_id,
                    status="CHECKPOINT_REQUESTED",
                    checkpoint_request=checkpoint,
                    model_call_ids=list(deps.model_call_ids),
                    runtime_metadata={
                        "thread_id": str(request.run_id),
                        "continuation": self._continuation_package(request, final_state),
                    },
                )

            output = final_state.get("output")
            await self._emit(request.run_id, "OUTPUT_PROPOSED", {"output": output})
            return AgentRunResult(
                run_id=request.run_id,
                status="OUTPUT_PRODUCED",
                output=output,
                output_schema=profile.output_schema.__name__ if profile.output_schema else None,
                model_call_ids=list(deps.model_call_ids),
                runtime_metadata={
                    "thread_id": str(request.run_id),
                    "continuation": self._continuation_package(request, final_state),
                },
            )
        except RuntimeCancelled:
            return AgentRunResult(run_id=request.run_id, status="CANCELLED")
        except Exception as exc:
            await self._emit(
                request.run_id,
                "ERROR",
                {"message": str(exc), "type": exc.__class__.__name__},
            )
            return AgentRunResult(
                run_id=request.run_id,
                status="FAILED",
                error=RuntimeErrorInfo(
                    code=getattr(exc, "code", "RUNTIME_FAILED"),
                    message=str(exc),
                ),
            )
        finally:
            self._cancel_events.pop(str(request.run_id), None)

    async def resume(self, request: AgentResumeRequest) -> AgentRunResult:
        run = AgentRunRequest(
            run_id=request.run_id,
            agent_profile=request.agent_profile,
            contract=request.contract,
            snapshot=request.snapshot,
            context=request.context,
            workspace_path=request.workspace_path,
            continuation=request.continuation,
        )
        if request.continuation.get("source_text"):
            run = run.model_copy(
                update={
                    "context": [
                        ContextItem(
                            kind="TEXT",
                            content=str(request.continuation["source_text"]),
                            provenance="DETERMINISTIC",
                        )
                    ]
                }
            )
        return await self.run(run)

    async def cancel(self, run_id: str) -> None:
        event = self._cancel_events.get(run_id)
        if event is not None:
            event.set()

    async def stream(self, run_id: str) -> AsyncIterator[AgentEvent]:
        queue = self._event_queues.get(run_id)
        if queue is None:
            return
        while True:
            event = await queue.get()
            yield event
            if event.type in ("OUTPUT_PROPOSED", "ERROR"):
                break

    def _state_from_request(self, request: AgentRunRequest) -> dict[str, Any]:
        if request.continuation and request.continuation.get("source_text"):
            source = str(request.continuation["source_text"])
        elif request.context:
            source = request.context[0].content
        else:
            source = ""
        return {"source_text": source, "model_call_ids": []}

    def _continuation_package(
        self, request: AgentRunRequest, state: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "run_id": str(request.run_id),
            "agent_profile": request.agent_profile,
            "source_text": state.get("source_text", ""),
            "output": state.get("output"),
        }

    async def _emit(
        self,
        run_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        key = str(run_id)
        seq = self._seq.get(key, 0) + 1
        self._seq[key] = seq
        event = AgentEvent(
            run_id=run_id,
            seq=seq,
            type=cast(
                Literal[
                    "MODEL_CALL_STARTED",
                    "MODEL_CALL_COMPLETED",
                    "TOOL_REQUESTED",
                    "TOOL_RESULT",
                    "PROGRESS",
                    "CHECKPOINT_REQUESTED",
                    "OUTPUT_PROPOSED",
                    "ERROR",
                ],
                event_type,
            ),
            payload=payload,
            at=datetime.now(tz=UTC),
        )
        queue = self._event_queues.get(key)
        if queue is not None:
            await queue.put(event)
