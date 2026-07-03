from __future__ import annotations

import axelrod as axl

NO_EXTRA_OPPONENT = "None"

_APPROVED_EXTRA_NAMES: tuple[str, ...] = (
    "Cooperator",
    "Defector",
    "Tit For Tat",
    "Grudger",
    "Random",
    "Win-Stay Lose-Shift",
    "Alternator",
)


def approved_extra_opponents() -> dict[str, type[axl.Player]]:
    """Return the fixed public allowlist for optional extra opponents."""
    by_name = {cls.name: cls for cls in axl.strategies}
    return {name: by_name[name] for name in _APPROVED_EXTRA_NAMES if name in by_name}


def extra_opponent_options() -> list[str]:
    return [NO_EXTRA_OPPONENT, *approved_extra_opponents().keys()]


def build_extra_opponent(name: str | None, *, noise_wrap: bool = False) -> axl.Player | None:
    selected = (name or "").strip()
    if selected in {"", NO_EXTRA_OPPONENT}:
        return None

    opponents = approved_extra_opponents()
    try:
        player = opponents[selected]()
    except KeyError as exc:
        allowed = ", ".join(extra_opponent_options())
        raise ValueError(f"Unsupported opponent selection. Choose one of: {allowed}.") from exc

    if noise_wrap:
        return axl.Noise(player, noise=0.05)
    return player
