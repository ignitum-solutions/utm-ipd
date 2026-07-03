from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from typing import Iterator

ENABLE_SWEEP_ENV = "ENABLE_SWEEP_UI"
MAX_SWEEP_COMBINATIONS = 32
MAX_SWEEP_ROUNDS = 100
MAX_SWEEP_REPETITIONS = 5
MAX_SWEEP_PLAYERS = 10
MAX_SWEEP_SECONDS = 60

_SWEEP_LOCK = threading.Lock()
_TRUE_VALUES = {"1", "true", "yes", "on"}


class SweepDisabledError(RuntimeError):
    pass


class SweepBusyError(RuntimeError):
    pass


class SweepTimeoutError(RuntimeError):
    pass


def sweep_ui_enabled() -> bool:
    return os.getenv(ENABLE_SWEEP_ENV, "false").strip().lower() in _TRUE_VALUES


def ensure_sweep_execution_allowed() -> None:
    if not sweep_ui_enabled():
        raise SweepDisabledError(
            "Sweep tools are disabled for this deployment. "
            f"Set {ENABLE_SWEEP_ENV}=true for local research runs."
        )


@contextmanager
def sweep_execution_guard() -> Iterator[None]:
    ensure_sweep_execution_allowed()
    if not _SWEEP_LOCK.acquire(blocking=False):
        raise SweepBusyError("Another sweep is already running in this Streamlit process.")
    try:
        yield
    finally:
        _SWEEP_LOCK.release()


def validate_sweep_budget(*, combinations: int, rounds: int, repetitions: int, players: int) -> None:
    if combinations > MAX_SWEEP_COMBINATIONS:
        raise ValueError(
            f"Sweep has {combinations} combinations; limit is {MAX_SWEEP_COMBINATIONS}."
        )
    if rounds > MAX_SWEEP_ROUNDS:
        raise ValueError(f"Sweep rounds per match must be <= {MAX_SWEEP_ROUNDS}.")
    if repetitions > MAX_SWEEP_REPETITIONS:
        raise ValueError(f"Sweep repetitions must be <= {MAX_SWEEP_REPETITIONS}.")
    if players > MAX_SWEEP_PLAYERS:
        raise ValueError(f"Sweep player count must be <= {MAX_SWEEP_PLAYERS}.")


def ensure_sweep_time_remaining(started_at: float) -> None:
    if time.monotonic() - started_at > MAX_SWEEP_SECONDS:
        raise SweepTimeoutError(
            f"Sweep stopped after {MAX_SWEEP_SECONDS} seconds. "
            "Use a smaller local/offline sweep."
        )
