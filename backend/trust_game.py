"""Seeded investment game using the trust meter and standard Python arithmetic."""
from __future__ import annotations

import random
from typing import Callable

from backend.models import TrustRequest
from backend.provenance import provenance
from utm.trust_meter import TrustMeter


def trust_game(cfg: TrustRequest, emit: Callable[[dict], None], checkpoint: Callable) -> dict:
    metadata = provenance("trust")
    rng = random.Random(cfg.seed)
    trust = TrustMeter(cfg.theta, cfg.alpha_pos, cfg.alpha_neg, cfg.delta)
    values, payoffs, cumulative, sends = [], [], [], []
    for index in range(cfg.rounds):
        checkpoint()
        betrayed = rng.random() < cfg.betrayal_probability
        sent = cfg.send if trust.value >= cfg.threshold else 0.0
        payoff = sent * 3 * (cfg.return_bad if betrayed else cfg.return_good) - sent
        trust.observe(1 if payoff >= 0 else -1)
        values.append(trust.value)
        payoffs.append(payoff)
        cumulative.append(sum(payoffs))
        sends.append(sent)
        emit({"type": "progress", "phase": "Playing investment rounds", "completed": index + 1,
              "total": cfg.rounds, "percent": round(100 * (index + 1) / cfg.rounds, 1)})
    return {"kind": "trust", "config": cfg.model_dump(), "metadata": metadata, "series": values,
            "payoffs": payoffs, "cumulative": cumulative, "investments": sends,
            "summary": {"Final trust": values[-1], "Cumulative payoff": cumulative[-1],
                        "Nonnegative payoff fraction": sum(p >= 0 for p in payoffs) / cfg.rounds,
                        "Investment fraction": sum(s > 0 for s in sends) / cfg.rounds}}
