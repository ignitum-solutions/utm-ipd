"""Record simulation inputs, scoring protocol, and implementation identifiers."""
from __future__ import annotations

import hashlib
import importlib.metadata
import math
import os
from pathlib import Path
import platform

from utm.trust_meter import get_ipd_reward_values

ROOT = Path(__file__).resolve().parent.parent
ENGINE_REVISION = "1"


def _parameter(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return value
    if isinstance(value, type):
        return f"{value.__module__}.{value.__qualname__}"
    if isinstance(value, dict):
        return {str(k): _parameter(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_parameter(v) for v in value]
    return str(value)


def provenance(kind: str, players=()) -> dict:
    files = sorted(path for directory in ("utm", "strategies", "tournaments", "backend")
                   for path in (ROOT / directory).glob("*.py"))
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    lock = ROOT / "poetry.lock"
    versions = {name: importlib.metadata.version(name) for name in ("axelrod", "numpy", "pandas", "scipy", "dask", "pyarrow", "pydantic")}
    protocol = {
        "tournament": {"score": "mean per-turn payoff against non-self slots, then mean across repetitions",
                       "dispersion": "population standard deviation of repetition means; ddof=0",
                       "self_play_simulated": True, "self_play_in_leaderboard": False,
                       "ties": "equal exact means share competition rank; tied rows sort by label then input slot",
                       "cooperation": "exact non-self cooperation count / exact non-self turns",
                       "rng": "Axelrod master seed; player order is part of the configuration"},
        "moran": {"initial_population": "one UTM agent and N-1 distinct Cooperator instances",
                  "selection": "Axelrod birth-death, payoff-proportional birth, random replacement",
                  "stop": "fixation or requested generation cap", "initial_state_in_series": True,
                  "rng": "Axelrod MoranProcess seed"},
        "trust": {"payoff": "sent * (3 * return_fraction - 1)",
                  "reward": "+1 for payoff >= 0, -1 for payoff < 0",
                  "zero_payoff_reward": 1, "no_investment_reward": 1,
                  "variant_used": False, "rng": "request-local Python random.Random(seed)"},
    }[kind]
    return {
        "schema_version": 1, "engine_revision": ENGINE_REVISION,
        "build_revision": os.getenv("GIT_SHA", "unrecorded-local-build"),
        "python": platform.python_version(), "platform": platform.platform(), "dependencies": versions,
        "source_file_sha256": hashes,
        "poetry_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else None,
        "protocol": protocol,
        "stage_game_payoffs": {"CC": [3, 3], "CD": [0, 5], "DC": [5, 0], "DD": [1, 1]} if kind != "trust" else None,
        "signed_trust_rewards": dict(zip(("CC", "DC", "DD", "CD"), get_ipd_reward_values())) if kind != "trust" else None,
        "resolved_players": [{"slot": i, "label": str(p), "class": f"{type(p).__module__}.{type(p).__qualname__}",
                              "constructor_parameters": _parameter(p.init_kwargs)} for i, p in enumerate(players)],
    }
