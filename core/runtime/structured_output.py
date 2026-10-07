from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from core.domain.canonical_json import sha256_hex
from core.runtime.errors import SchemaValidationFailed

STRUCTURED_OUTPUT_TOOL = "submit_structured_output"


def _prepare_openai_strict_schema(node: dict[str, Any]) -> None:
    """Recursively satisfy OpenAI strict json_schema rules on a Pydantic JSON schema."""
    defs = node.get("$defs")
    if isinstance(defs, dict):
        for sub in defs.values():
            if isinstance(sub, dict):
                _prepare_openai_strict_schema(sub)

    for key in ("anyOf", "oneOf", "allOf"):
        variants = node.get(key)
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, dict):
                    _prepare_openai_strict_schema(variant)

    is_object = node.get("type") == "object" or "properties" in node
    if is_object:
        props = node.get("properties")
        if isinstance(props, dict):
            node["additionalProperties"] = False
            node["required"] = list(props.keys())
            for prop_schema in props.values():
                if isinstance(prop_schema, dict):
                    _prepare_openai_strict_schema(prop_schema)
        elif node.get("additionalProperties") is True or (
            node.get("type") == "object" and "properties" not in node
        ):
            # Pydantic ``dict[str, Any]`` → OpenAI requires a closed object schema.
            node["additionalProperties"] = False
            node.setdefault("properties", {})

    if node.get("type") == "array":
        items = node.get("items")
        if isinstance(items, dict):
            _prepare_openai_strict_schema(items)


def pydantic_to_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    _prepare_openai_strict_schema(schema)
    return schema


def schema_hash(model: type[BaseModel]) -> str:
    return sha256_hex(pydantic_to_json_schema(model))


def validate_or_feedback(
    model: type[BaseModel],
    payload: dict[str, Any] | None,
    raw_text: str | None,
) -> tuple[BaseModel | None, list[dict[str, object]]]:
    if payload is None:
        return None, [{"msg": "No structured payload", "raw": raw_text or ""}]
    try:
        return model.model_validate(payload), []
    except ValidationError as exc:
        errors: list[dict[str, object]] = []
        for err in exc.errors():
            errors.append(dict(err))
        return None, errors


def validation_feedback_message(errors: list[dict[str, object]]) -> str:
    lines = ["Previous response failed schema validation. Fix the output and try again."]
    for err in errors:
        loc = err.get("loc", ())
        msg = err.get("msg", "invalid")
        lines.append(f"- {loc}: {msg}")
    return "\n".join(lines)


def ensure_valid_or_raise(
    model: type[BaseModel],
    payload: dict[str, Any] | None,
    raw_text: str | None,
) -> BaseModel:
    parsed, errors = validate_or_feedback(model, payload, raw_text)
    if parsed is None:
        raise SchemaValidationFailed("Structured output validation failed", errors=errors)
    return parsed
