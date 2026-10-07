from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache
def load_pricing_config() -> dict[str, Any]:
    path = _repo_root() / "config" / "model_pricing.yaml"
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        return {"models": {}, "default": {}}
    return data


def clear_pricing_cache() -> None:
    load_pricing_config.cache_clear()


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    cfg = load_pricing_config()
    models = cfg.get("models", {})
    default = cfg.get("default", {})
    rates = models.get(model, default) if isinstance(models, dict) else default
    if not isinstance(rates, dict):
        rates = {}
    in_rate = Decimal(str(rates.get("input_per_million", 3.0)))
    out_rate = Decimal(str(rates.get("output_per_million", 15.0)))
    cost = (Decimal(input_tokens) / Decimal(1_000_000)) * in_rate
    cost += (Decimal(output_tokens) / Decimal(1_000_000)) * out_rate
    return cost.quantize(Decimal("0.000001"))


def estimate_max_cost_usd(model: str, input_tokens: int, max_output_tokens: int) -> Decimal:
    return estimate_cost_usd(model, input_tokens, max_output_tokens)
