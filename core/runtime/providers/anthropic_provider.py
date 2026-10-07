from __future__ import annotations

from typing import Any

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic, AuthenticationError
from anthropic import RateLimitError as AnthropicRateLimitError

from core.config.settings import get_settings
from core.runtime.contracts import ProviderRequest, ProviderResponse
from core.runtime.errors import ProviderAuthError, ProviderRateLimited, ProviderTransientError
from core.runtime.structured_output import pydantic_to_json_schema

_STRUCTURED_TOOL = "structured_output"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client: AsyncAnthropic | None = None) -> None:
        settings = get_settings()
        api_key = settings.anthropic_api_key.get_secret_value()
        if client is None:
            if not api_key:
                raise ProviderAuthError("ANTHROPIC_API_KEY is not configured")
            self._client = AsyncAnthropic(api_key=api_key)
        else:
            self._client = client

    async def complete(self, req: ProviderRequest) -> ProviderResponse:
        tools: list[dict[str, Any]] = []
        tool_choice: dict[str, Any] | None = None
        if req.output_schema is not None:
            schema = req.json_schema or pydantic_to_json_schema(req.output_schema)
            tools = [
                {
                    "name": _STRUCTURED_TOOL,
                    "description": "Return the final structured answer.",
                    "input_schema": schema,
                }
            ]
            tool_choice = {"type": "tool", "name": _STRUCTURED_TOOL}

        try:
            message = await self._client.messages.create(
                model=req.model,
                max_tokens=req.max_output_tokens,
                temperature=req.temperature,
                system=req.system,
                messages=[{"role": "user", "content": req.user_content}],
                tools=tools or None,
                tool_choice=tool_choice,
            )
        except AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except AnthropicRateLimitError as exc:
            retry_after = _retry_after(exc)
            raise ProviderRateLimited(str(exc), retry_after=retry_after) from exc
        except (APIConnectionError, APIStatusError) as exc:
            status = getattr(exc, "status_code", None)
            if status in (429, 500, 502, 503, 504):
                raise ProviderTransientError(str(exc)) from exc
            if status == 401:
                raise ProviderAuthError(str(exc)) from exc
            raise ProviderTransientError(str(exc)) from exc

        structured: dict[str, Any] | None = None
        raw_text: str | None = None
        for block in message.content:
            if block.type == "tool_use" and block.name == _STRUCTURED_TOOL:
                structured = block.input if isinstance(block.input, dict) else None
            elif block.type == "text":
                raw_text = block.text

        return ProviderResponse(
            raw_text=raw_text,
            structured=structured,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            provider_request_id=getattr(message, "id", None),
        )

    async def embed(
        self, texts: list[str], model: str
    ) -> tuple[list[list[float]], int, str | None]:
        raise NotImplementedError("Anthropic does not provide embeddings")


def _retry_after(exc: BaseException) -> float | None:
    headers = getattr(exc, "response", None)
    if headers is not None:
        retry = headers.headers.get("retry-after")
        if retry:
            try:
                return float(retry)
            except ValueError:
                return None
    return None
