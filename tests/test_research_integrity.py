"""Independent strategy controls, scoring checks, and reproducibility tests."""
import csv
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import axelrod as axl
import pandas as pd
import pytest

from backend.engine import tournament, trust_game
from backend.models import TournamentRequest, TrustRequest
from strategies.utm_pure import TrustOnlyIPDStrategy
from strategies.utm_tft import UTMTFT
from strategies.utm_tft_wsls import UTMTFT_WSLS
from strategies.utm_wsls import UTMWSLS
from tournaments.run_round_robin import focal_mean, run_tournament
from utm.trust_meter import TrustMeter, get_ipd_reward_values, temporary_ipd_reward_values, payoff_to_signed_reward


CONTROLS = [
    (UTMTFT, {}, axl.TitForTat),
    (UTMWSLS, {}, axl.WinStayLoseShift),
    (UTMTFT_WSLS, {"promote_at": 1}, axl.TitForTat),
    (UTMTFT_WSLS, {"promote_at": 0}, axl.WinStayLoseShift),
]


@pytest.mark.parametrize("wrapper,extra,classic", CONTROLS)
@pytest.mark.parametrize("opponent", [axl.Defector, axl.Alternator, axl.Random, axl.TitForTat])
@pytest.mark.parametrize("noise", [0, .2])
@pytest.mark.parametrize("seed", [3, 71])
def test_disabled_trust_gate_matches_classic_actions(wrapper, extra, classic, opponent, noise, seed):
    # Independent control: compare full played actions, not another UTM path.
    utm = wrapper(theta=1, alpha_pos=0, alpha_neg=0, delta=0, threshold=.05, **extra)
    actual = axl.Match((utm, opponent()), turns=25, noise=noise, seed=seed).play()
    baseline = axl.Match((classic(), opponent()), turns=25, noise=noise, seed=seed).play()
    assert actual == baseline


@pytest.mark.parametrize("wrapper,extra", [(UTMWSLS, {}), (UTMTFT_WSLS, {"promote_at": 0})])
def test_delegate_observes_gate_forced_moves(wrapper, extra):
    utm = wrapper(theta=.4, alpha_pos=1, alpha_neg=0, delta=0, threshold=.5, **extra)
    trace = axl.Match((utm, axl.Cooperator()), turns=3, seed=42).play()
    assert trace == [(axl.Action.D, axl.Action.C)] * 3
    assert list(utm.inner.history) == [axl.Action.D, axl.Action.D]


@pytest.mark.parametrize("strategy", [UTMTFT, UTMWSLS, UTMTFT_WSLS, TrustOnlyIPDStrategy])
def test_clone_and_reset_do_not_carry_trust_or_history_between_matches(strategy):
    p = strategy(theta=.7)
    axl.Match((p, axl.Defector()), turns=10, seed=3).play()
    clone = p.clone()
    assert not clone.history and clone.trust.value == .7 and clone.trust._betrayals == 0
    p.reset()
    assert not p.history and p.trust.value == .7 and p.trust._betrayals == 0
    assert axl.Match((p, axl.Random()), turns=15, seed=9).play() == axl.Match((strategy(theta=.7), axl.Random()), turns=15, seed=9).play()


def test_utm_can_lose_and_known_payoffs_are_not_boosted():
    p = UTMTFT(theta=1, alpha_pos=0, alpha_neg=0, delta=0, threshold=.05)
    frame = run_tournament([p, axl.Defector()], turns=6, repetitions=3, quiet=True)
    utm, opponent = frame.set_index("Player index").loc[0], frame.set_index("Player index").loc[1]
    assert utm["Mean"] == pytest.approx(5 / 6)
    assert opponent["Mean"] == pytest.approx(10 / 6)
    assert utm["Rank"] == 2 and opponent["Rank"] == 1
    assert utm["#C"] == 3 and utm["#D"] == 15


def test_equal_scores_share_rank_and_names_do_not_choose_focal_score():
    utm = TrustOnlyIPDStrategy(theta=1, alpha_pos=0, alpha_neg=0, delta=0)
    frame = run_tournament([utm, axl.Cooperator(), axl.Cooperator()], turns=7, repetitions=3, quiet=True)
    assert frame["Rank"].tolist() == [1, 1, 1]
    assert set(frame["Player index"]) == {0, 1, 2}
    assert frame["#C"].tolist() == [42, 42, 42]
    different_scores = pd.DataFrame([{"Player index": 1, "Player": "UTM-best-preset", "Mean": 5},
                                     {"Player index": 0, "Player": "Trust-only IPD", "Mean": 1}])
    assert focal_mean(different_scores) == 1


def test_reported_cooperation_counts_agree_with_retained_raw_moves(tmp_path):
    frame = run_tournament([UTMTFT(), axl.Random(), axl.Defector()], turns=17, repetitions=3,
                           noise=.2, seed=14, quiet=True, csv_dir=str(tmp_path))
    with next(tmp_path.glob('*.csv')).open() as source:
        rows = list(csv.DictReader(source))
    for slot, row in frame.set_index("Player index").iterrows():
        moves = ''.join(r['Actions'] for r in rows if int(r['Player index']) == slot and int(r['Opponent index']) != slot)
        assert row['#C'] == moves.count('C')
        assert row['#D'] == moves.count('D')
        assert row['C-rate'] == moves.count('C') / len(moves)


def test_zero_reward_mapping_is_rejected():
    previous = get_ipd_reward_values()
    with pytest.raises(ValueError, match='nonzero'):
        with temporary_ipd_reward_values(1, 0, -.2, -1):
            pass
    assert get_ipd_reward_values() == previous


def test_reward_overrides_are_isolated_across_concurrent_research_runs():
    barrier = Barrier(2)
    def run(value):
        with temporary_ipd_reward_values(value, .5, -.2, -1):
            barrier.wait(timeout=5)
            return payoff_to_signed_reward('C', 'C')
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, [.7, 1.2])) == [.7, 1.2]
    assert get_ipd_reward_values() == (1, .5, -.2, -1)


@pytest.mark.parametrize('reward,severity', [(float('nan'), 1), (float('inf'), 1), (0, 1), (1, -1), (1, float('inf'))])
def test_invalid_observations_cannot_silently_clip_into_favorable_trust(reward, severity):
    meter = TrustMeter(theta=.5)
    with pytest.raises(ValueError):
        meter.observe(reward, severity)
    assert meter.value == .5 and meter._betrayals == 0


def test_result_records_effective_presets_rules_and_source_version():
    cfg = TournamentRequest(opponents=['Defector'], presets=['Custom'], rounds=5, repetitions=2)
    preset = {'Custom': {'variant': 'WSLS', 'theta': .9, 'alpha_pos': .1, 'alpha_neg': .2, 'delta': .3, 'tau': .4}}
    result = tournament(cfg, lambda _: None, lambda: None, preset)
    metadata = result['metadata']
    assert metadata['resolved_players'][2]['constructor_parameters']['theta'] == .9
    assert metadata['stage_game_payoffs']['DC'] == [5, 0]
    assert metadata['signed_trust_rewards']['DC'] == .5
    assert metadata['protocol']['self_play_in_leaderboard'] is False
    assert len(metadata['source_file_sha256']['strategies/utm_wsls.py']) == 64
    assert metadata['dependencies']['axelrod'] == '4.13.1'


def test_zero_investment_rule_is_recorded_and_not_labeled_cooperation():
    result = trust_game(TrustRequest(rounds=3, send=0), lambda _: None, lambda: None)
    assert result['metadata']['protocol']['no_investment_reward'] == 1
    assert result['payoffs'] == [0, 0, 0]
    assert result['summary']['Investment fraction'] == 0
    assert result['summary']['Nonnegative payoff fraction'] == 1


def test_opponent_registry_uses_axelrods_rule_obeying_set():
    from backend.engine import STRATEGIES
    assert set(STRATEGIES) == {cls.name for cls in axl.strategies}
    assert all(axl.Classifiers.obey_axelrod(cls()) for cls in STRATEGIES.values())


def test_nonfinite_overflow_does_not_partially_update_trust_state():
    meter = TrustMeter(theta=.5, delta=1e308)
    with pytest.raises(ValueError, match='overflowed'):
        meter.observe(-1, severity=1e308)
    assert meter.value == .5 and meter._betrayals == 0
