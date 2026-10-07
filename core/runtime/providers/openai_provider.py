from __future__ import annotations

import json
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)

from core.config.settings import get_settings
from core.runtime.contracts import ProviderRequest, ProviderResponse, ToolCall
from core.runtime.errors import ProviderAuthError, ProviderRateLimited, ProviderTransientError
from core.runtime.structured_output import STRUCTURED_OUTPUT_TOOL, pydantic_to_json_schema


def _openai_tool_name(catalog_name: str) -> str:
    return catalog_name.replace(".", "__")


def _catalog_tool_name(openai_name: str) -> str:
    if openai_name == STRUCTURED_OUTPUT_TOOL:
        return openai_name
    return openai_name.replace("__", ".")


class OpenAIProvider:
    name = "openai"

    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        settings = get_settings()
        api_key = settings.openai_api_key.get_secret_value()
        if client is None:
            if not api_key:
                raise ProviderAuthError("OPENAI_API_KEY is not configured")
            self._client = AsyncOpenAI(api_key=api_key)
        else:
            self._client = client

    async def complete(self, req: ProviderRequest) -> ProviderResponse:
        openai_tools: list[dict[str, Any]] = []
        for spec in req.tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": _openai_tool_name(spec.name),
                        "description": spec.description,
                        "parameters": spec.parameters_schema,
                    },
                }
            )

        response_format: dict[str, Any] | None = None
        use_tools = bool(req.tools)
        if req.output_schema is not None:
            schema = req.json_schema or pydantic_to_json_schema(req.output_schema)
            if use_tools:
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": STRUCTURED_OUTPUT_TOOL,
                            "description": (
                                "Submit the final structured result when implementation is complete."
                            ),
                            "parameters": schema,
                        },
                    }
                )
            else:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": req.output_schema.__name__,
                        "schema": schema,
                        "strict": True,
                    },
                }

        token_limit: dict[str, int] = (
            {"max_completion_tokens": req.max_output_tokens}
            if req.model.startswith(("gpt-5", "gpt-6", "o"))
            else {"max_tokens": req.max_output_tokens}
        )
        create_kwargs: dict[str, Any] = {
            "model": req.model,
            "temperature": req.temperature,
            "messages": [
                {"role": "system", "content": req.system},
                {"role": "user", "content": req.user_content},
            ],
            **token_limit,
        }
        if response_format is not None:
            create_kwargs["response_format"] = response_format
        if openai_tools:
            create_kwargs["tools"] = openai_tools
            create_kwargs["tool_choice"] = "auto"

        try:
            completion = await self._client.chat.completions.create(**create_kwargs)
        except AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except RateLimitError as exc:
            raise ProviderRateLimited(str(exc), retry_after=_retry_after(exc)) from exc
        except (APIConnectionError, APIStatusError) as exc:
            status = getattr(exc, "status_code", None)
            if status in (429, 500, 502, 503, 504):
                raise ProviderTransientError(str(exc)) from exc
            if status == 401:
                raise ProviderAuthError(str(exc)) from exc
            raise ProviderTransientError(str(exc)) from exc

        choice = completion.choices[0].message
        raw_text = choice.content
        structured: dict[str, Any] | None = None
        tool_calls: list[ToolCall] = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                fn = tc.function
                try:
                    args = json.loads(fn.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                tool_calls.append(
                    ToolCall(id=tc.id, name=_catalog_tool_name(fn.name), arguments=args),
                )
                if fn.name == STRUCTURED_OUTPUT_TOOL:
                    structured = args
        elif raw_text:
            try:
                structured = json.loads(raw_text)
            except json.JSONDecodeError:
                structured = None

        usage = completion.usage
        return ProviderResponse(
            raw_text=raw_text,
            structured=structured,
            tool_calls=tool_calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            provider_request_id=completion.id,
        )

    async def embed(
        self, texts: list[str], model: str
    ) -> tuple[list[list[float]], int, str | None]:
        try:
            response = await self._client.embeddings.create(model=model, input=texts)
        except AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except RateLimitError as exc:
            raise ProviderRateLimited(str(exc), retry_after=_retry_after(exc)) from exc
        except (APIConnectionError, APIStatusError) as exc:
            raise ProviderTransientError(str(exc)) from exc

        vectors = [list(row.embedding) for row in response.data]
        tokens = response.usage.total_tokens if response.usage else 0
        return vectors, tokens, response.model


def _retry_after(exc: BaseException) -> float | None:
    response = getattr(exc, "response", None)
    if response is not None:
        retry = response.headers.get("retry-after")
        if retry:
            try:
                return float(retry)
            except ValueError:
                return None
    return None
