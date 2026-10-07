from __future__ import annotations

from decimal import Decimal
from threading import Lock

from core.config.settings import get_settings
from core.runtime.errors import BudgetExceeded


class BudgetLedger:
    """Tracks spend against per-run and session (live test) budgets."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._spent: dict[str, Decimal] = {}
        self._limits: dict[str, Decimal] = {}
        self._session_spent = Decimal("0")

    def set_limit(self, key: str, limit_usd: float | Decimal) -> None:
        with self._lock:
            self._limits[key] = Decimal(str(limit_usd))

    def session_limit(self) -> Decimal:
        return get_settings().llm_test_budget_usd

    def check_and_reserve(self, key: str, estimate_usd: Decimal) -> None:
        with self._lock:
            session_limit = self.session_limit()
            if self._session_spent + estimate_usd > session_limit:
                raise BudgetExceeded(
                    f"Session LLM budget would be exceeded ({self._session_spent} + {estimate_usd})"
                )
            if key in self._limits:
                spent = self._spent.get(key, Decimal("0"))
                if spent + estimate_usd > self._limits[key]:
                    raise BudgetExceeded(
                        f"Run budget would be exceeded for {key} ({spent} + {estimate_usd})"
                    )

    def record(self, key: str, actual_usd: Decimal) -> None:
        with self._lock:
            self._spent[key] = self._spent.get(key, Decimal("0")) + actual_usd
            self._session_spent += actual_usd

    @property
    def session_spent(self) -> Decimal:
        with self._lock:
            return self._session_spent

    def reset_session(self) -> None:
        with self._lock:
            self._session_spent = Decimal("0")
            self._spent.clear()
            self._limits.clear()


_GLOBAL_LEDGER = BudgetLedger()


def get_budget_ledger() -> BudgetLedger:
    return _GLOBAL_LEDGER
