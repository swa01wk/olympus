from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.domain.enums import ActorKind

GuardId = str
EffectId = str

AggregateKind = Literal["delivery_cycle", "task", "task_contract", "repository", "approval"]


@dataclass(frozen=True)
class Edge:
    to: str
    guards: tuple[GuardId, ...] = ()
    actor_kinds: tuple[ActorKind, ...] = (
        ActorKind.HUMAN,
        ActorKind.SYSTEM,
        ActorKind.INTEGRATION,
    )
    effects: tuple[EffectId, ...] = ()


@dataclass(frozen=True)
class Machine:
    name: str
    states: frozenset[str]
    initial: str
    terminal: frozenset[str]
    edges: dict[tuple[str, str], Edge]

    def edge(self, state: str, command: str) -> Edge | None:
        return self.edges.get((state, command))

    def validate(self) -> None:
        if self.initial not in self.states:
            raise ValueError(f"{self.name}: initial {self.initial} not in states")
        for (from_state, _cmd), edge in self.edges.items():
            if from_state not in self.states:
                raise ValueError(f"{self.name}: from state {from_state} not in states")
            if edge.to not in self.states:
                raise ValueError(f"{self.name}: to state {edge.to} not in states")
        for term in self.terminal:
            if term not in self.states:
                raise ValueError(f"{self.name}: terminal {term} not in states")
        for (from_state, _cmd), _edge in self.edges.items():
            if from_state in self.terminal:
                raise ValueError(f"{self.name}: outgoing edge from terminal {from_state}")
