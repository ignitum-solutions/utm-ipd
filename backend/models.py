"""Bounded public inputs. Server validation also applies to local HTTP runs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Variant = Literal["TFT", "WSLS", "TFT→WSLS", "Trust-only IPD"]


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    theta: float = Field(default=0.6, ge=0, le=1)
    alpha_pos: float = Field(default=0.02, ge=0, le=0.5)
    alpha_neg: float = Field(default=0.675, ge=0, le=1)
    delta: float = Field(default=0.45, ge=0, le=1)
    threshold: float = Field(default=0.5, ge=0.05, le=1)
    variant: Variant = "TFT"
    seed: int = Field(default=42, ge=0, le=9999, strict=True)


DEFAULT_OPPONENTS = [
    "Tit For Tat", "Defector", "Win-Stay Lose-Shift", "Random",
    "ZD-Extort-2", "EvolvedLookerUp2_2_2", "AON2", "Adaptive Pavlov 2011", "Meta Hunter",
]
MAX_TOURNAMENT_WORK = 2_000_000
MAX_MORAN_WORK = 20_000_000


class TournamentRequest(Parameters):
    rounds: int = Field(default=200, ge=1, le=1000, strict=True)
    repetitions: int = Field(default=30, ge=1, le=100, strict=True)
    opponents: list[str] = Field(default_factory=lambda: DEFAULT_OPPONENTS.copy(), max_length=19)
    presets: list[str] = Field(default_factory=list, max_length=8)
    extra_opponent: str = Field(default="None", max_length=80)
    noise_wrap: bool = False
    noise_pct: int = Field(default=0, ge=0, le=20, strict=True)

    @model_validator(mode="after")
    def bound_work(self):
        count = 1 + len(self.opponents) + len(self.presets) + (self.extra_opponent != "None")
        if not 2 <= count <= 20:
            raise ValueError("Choose between 2 and 20 total players, including your UTM strategy.")
        if len(set(self.opponents)) != len(self.opponents) or len(set(self.presets)) != len(self.presets):
            raise ValueError("Select each opponent or preset only once.")
        work = count * (count + 1) // 2 * self.rounds * self.repetitions
        if work > MAX_TOURNAMENT_WORK:
            raise ValueError("This run is too large for the demo. Reduce players, rounds, or repetitions; run larger experiments locally using the Python CLI.")
        return self


class MoranRequest(Parameters):
    generations: int = Field(default=200, ge=1, le=1000, strict=True)
    population: int = Field(default=20, ge=5, le=50, strict=True)
    rounds: int = Field(default=200, ge=1, le=1000, strict=True)

    @model_validator(mode="after")
    def bound_work(self):
        if self.population * (self.population - 1) // 2 * self.generations * self.rounds > MAX_MORAN_WORK:
            raise ValueError("Reduce the population, generations, or rounds for the demo. Larger experiments can run locally using Python.")
        return self


class TrustRequest(Parameters):
    # Preserve the original Trust Game defaults; now expose them for research.
    theta: float = Field(default=0.5, ge=0, le=1)
    alpha_pos: float = Field(default=0.05, ge=0, le=0.5)
    alpha_neg: float = Field(default=0.5, ge=0, le=1)
    delta: float = Field(default=0.55, ge=0, le=1)
    threshold: float = Field(default=0.45, ge=0.05, le=1)
    rounds: int = Field(default=50, ge=1, le=500, strict=True)
    send: float = Field(default=5, ge=0, le=10)
    return_good: float = Field(default=0.5, ge=0, le=1)
    return_bad: float = Field(default=0, ge=0, le=1)
    betrayal_probability: float = Field(default=0, ge=0, le=1)


class Suggestion(Parameters):
    name: str = Field(min_length=1, max_length=80)
    creator: str = Field(default="", max_length=80)
    description: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def nonblank(self):
        if not self.name.strip() or not self.description.strip():
            raise ValueError("Include a preset name and description.")
        return self
