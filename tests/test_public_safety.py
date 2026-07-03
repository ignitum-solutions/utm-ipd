import pytest
import axelrod as axl

from dash.opponents import NO_EXTRA_OPPONENT, build_extra_opponent, extra_opponent_options
from dash.sweep_guard import (
    ENABLE_SWEEP_ENV,
    SweepBusyError,
    SweepDisabledError,
    SweepTimeoutError,
    MAX_SWEEP_SECONDS,
    ensure_sweep_time_remaining,
    ensure_sweep_execution_allowed,
    sweep_execution_guard,
)
from main import approved_player_ids, build_approved_player
from strategies.utm_pure import TrustOnlyIPDStrategy
from utm.trust_meter import get_ipd_reward_values, temporary_ipd_reward_values


def test_extra_opponent_allowlist_accepts_none():
    assert build_extra_opponent(NO_EXTRA_OPPONENT) is None


def test_extra_opponent_allowlist_rejects_module_paths():
    with pytest.raises(ValueError, match="Unsupported opponent selection"):
        build_extra_opponent("os.system")


def test_extra_opponent_allowlist_builds_approved_strategy():
    options = extra_opponent_options()
    assert "Defector" in options
    player = build_extra_opponent("Defector")
    assert player is not None
    assert player.name == "Defector"


def test_cli_player_allowlist_rejects_module_paths():
    with pytest.raises(ValueError, match="Unsupported player"):
        build_approved_player("os.system")


def test_cli_player_allowlist_builds_approved_strategy():
    assert "tft" in approved_player_ids()
    player = build_approved_player("tft")
    assert player.name == "Tit For Tat"


def test_sweeps_disabled_by_default(monkeypatch):
    monkeypatch.delenv(ENABLE_SWEEP_ENV, raising=False)
    with pytest.raises(SweepDisabledError):
        ensure_sweep_execution_allowed()


def test_sweep_lock_allows_one_runner(monkeypatch):
    monkeypatch.setenv(ENABLE_SWEEP_ENV, "true")
    with sweep_execution_guard():
        with pytest.raises(SweepBusyError):
            with sweep_execution_guard():
                pass


def test_sweep_timeout_guard():
    with pytest.raises(SweepTimeoutError):
        ensure_sweep_time_remaining(-(MAX_SWEEP_SECONDS + 1))


def test_ipd_reward_matrix_defaults_restore_after_temporary_override():
    defaults = get_ipd_reward_values()
    assert defaults == (1.0, 0.5, -0.2, -1.0)
    with temporary_ipd_reward_values(1.1, 0.4, -0.3, -1.2):
        assert get_ipd_reward_values() == (1.1, 0.4, -0.3, -1.2)
    assert get_ipd_reward_values() == defaults


def test_trust_only_ipd_strategy_is_ipd_scoped():
    player = TrustOnlyIPDStrategy(theta=0.6, threshold=0.5)
    assert player.name == "Trust-only IPD"
    assert player.strategy(axl.TitForTat()) == axl.Action.C
