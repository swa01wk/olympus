from __future__ import annotations

from core.tools.context import ToolExecutionContext

ToolParams = dict[str, object]
ToolOutput = dict[str, object]


async def olympus_ask_question(ctx: ToolExecutionContext, params: ToolParams) -> ToolOutput:
    _ = ctx
    raw = params.get("questions", [])
    questions = list(raw) if isinstance(raw, list) else []
    return {"questions": questions, "recorded": True}


async def olympus_request_approval(ctx: ToolExecutionContext, params: ToolParams) -> ToolOutput:
    _ = ctx
    return {"approval_requested": True, "reason": str(params.get("reason", ""))}


async def olympus_submit_artifact(ctx: ToolExecutionContext, params: ToolParams) -> ToolOutput:
    _ = ctx
    return {"artifact_kind": str(params.get("kind", "GENERIC")), "submitted": True}
