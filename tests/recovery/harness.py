"""Recovery test harness — process control and fault points."""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass


@dataclass
class ManagedProcess:
    name: str
    popen: subprocess.Popen[bytes]

    def sigterm(self) -> None:
        self.popen.send_signal(signal.SIGTERM)

    def kill9(self) -> None:
        self.popen.kill()


class ChaosHarness:
    def __init__(self) -> None:
        self.processes: dict[str, ManagedProcess] = {}

    def start(self, name: str, argv: list[str], *, env: dict[str, str] | None = None) -> None:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        pop = subprocess.Popen(argv, env=merged)
        self.processes[name] = ManagedProcess(name=name, popen=pop)

    def kill9(self, name: str) -> None:
        self.processes[name].kill9()

    def stop_all(self) -> None:
        for proc in self.processes.values():
            with proc.popen:
                proc.sigterm()
