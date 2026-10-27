"""Independent strategy controls, scoring checks, and reproducibility tests."""
import csv
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
from threading import Barrier

import axelrod as axl
import pandas as pd
import pytest
import yaml

from backend.engine import player, preset_player, tournament, trust_game
from backend.models import Parameters, TournamentRequest, TrustRequest
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


@pytest.mark.parametrize("rewards", [(1, .5, -.2, -1), (.2, .8, -.4, -.7)])
def test_utm_can_lose_and_known_payoffs_are_not_boosted(rewards):
    # With the gate disabled, changing internal rewards cannot change game scores.
    p = UTMTFT(theta=1, alpha_pos=0, alpha_neg=0, delta=0, threshold=.05)
    with temporary_ipd_reward_values(*rewards):
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
    result = trust_game(TrustRequest(rounds=50, send=0), lambda _: None, lambda: None)
    assert result['metadata']['protocol']['no_investment_reward'] == 1
    assert result['payoffs'] == [0] * 50
    assert result['cumulative'] == [0] * 50
    assert result['investments'] == [0] * 50
    assert result['summary']['Investment fraction'] == 0
    assert result['summary']['Nonnegative payoff fraction'] == 1
    # Fifty reward-1 updates: T_50 = 1 - (1/2)(19/20)^50.
    expected = 1 - Fraction(1, 2) * Fraction(19, 20) ** 50
    assert result['summary']['Final trust'] == pytest.approx(float(expected), rel=0, abs=1e-15)
    assert not any('cooperation' in key.lower() for key in result['summary'])


def test_opponent_registry_uses_axelrods_rule_obeying_set():
    from backend.engine import STRATEGIES
    assert set(STRATEGIES) == {cls.name for cls in axl.strategies}
    assert all(axl.Classifiers.obey_axelrod(cls()) for cls in STRATEGIES.values())


def test_nonfinite_overflow_does_not_partially_update_trust_state():
    meter = TrustMeter(theta=.5, delta=1e308)
    with pytest.raises(ValueError, match='overflowed'):
        meter.observe(-1, severity=1e308)
    assert meter.value == .5 and meter._betrayals == 0


def test_guide_worked_update():
    meter = TrustMeter(theta=.6, alpha_pos=.02)
    meter.observe(1)
    # 3/5 + (1/50)(1 - 3/5) = 76/125, with no below-trust event.
    assert meter.value == pytest.approx(float(Fraction(76, 125)), rel=0, abs=1e-15)
    assert meter._betrayals == 0


def test_current_event_and_accumulated_counter_affect_both_update_directions():
    """Core mechanism with graded rewards, independent of any IPD policy."""
    meter = TrustMeter(theta=.5, alpha_pos=.25, alpha_neg=.5, delta=.5)
    # First gain: (1/2)(3/2); next: (1/4)(3/2); third: (1/2)(2).
    observations = [(.25, Fraction(5, 16), 1),
                    (.75, Fraction(61, 128), 1),
                    (.25, Fraction(1, 4), 2)]
    for reward, expected, counter in observations:
        meter.observe(reward)
        assert meter.value == pytest.approx(float(expected), rel=0, abs=1e-15)
        assert meter._betrayals == counter


def test_positive_reward_below_current_trust_reduces_trust():
    meter = TrustMeter(theta=.6, alpha_pos=.1, alpha_neg=.25, delta=.5)
    meter.observe(.2)
    # 3/5 + (1/4)(3/2)(1/5 - 3/5) = 9/20.
    assert meter.value == pytest.approx(float(Fraction(9, 20)), rel=0, abs=1e-15)
    assert meter._betrayals == 1


@pytest.mark.parametrize("history", [[], [.25]])
def test_equal_reward_changes_neither_trust_nor_counter(history):
    meter = TrustMeter(theta=.5, alpha_pos=.25, alpha_neg=.5, delta=.5)
    for reward in history:
        meter.observe(reward)
    before = meter.value, meter._betrayals
    meter.observe(meter.value)
    assert (meter.value, meter._betrayals) == before


@pytest.mark.parametrize("alpha_neg,rewards,boundary", [(1, [-1], 0), (0, [-1, 1], 1)])
def test_history_gain_can_reach_either_clipping_boundary(alpha_neg, rewards, boundary):
    meter = TrustMeter(theta=.5, alpha_pos=1, alpha_neg=alpha_neg, delta=2)
    # A counter of one gives a multiplier of three; these unbounded updates
    # would reach -4 or 2. Clipping produces the respective boundary instead.
    for reward in rewards:
        meter.observe(reward)
    assert meter.value == boundary
    assert meter._betrayals == 1


@pytest.mark.parametrize("rate", [Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)])
@pytest.mark.parametrize("initial", [Fraction(1, 2), Fraction(1, 10)])
def test_fixed_rate_single_cue_reduction_with_nonzero_graded_outcomes(rate, initial):
    """Compare with the closed-form fixed-rate solution, not a second UTM loop."""
    outcomes = [Fraction(1, 5), Fraction(4, 5), Fraction(1, 5), Fraction(1, 5),
                Fraction(4, 5), Fraction(4, 5), Fraction(1, 5)]
    meter = TrustMeter(theta=float(initial), alpha_pos=float(rate),
                       alpha_neg=float(rate), delta=0)
    for count, outcome in enumerate(outcomes, start=1):
        expected = ((1 - rate) ** count * initial
                    + rate * sum((1 - rate) ** (count - 1 - j) * value
                                 for j, value in enumerate(outcomes[:count])))
        assert 0 < expected < 1  # The comparison does not activate clipping.
        meter.observe(float(outcome))
        assert meter.value == pytest.approx(float(expected), rel=0, abs=1e-14)


def test_same_trust_different_history_produces_different_next_update():
    """Core-mechanism fixture with graded rewards, not an IPD performance result."""
    untouched = TrustMeter(theta=.5, alpha_pos=.05, alpha_neg=.5, delta=.3)
    experienced = TrustMeter(theta=.5, alpha_pos=.05, alpha_neg=.5, delta=.3)
    experienced.observe(.49)
    assert experienced.value == pytest.approx(.4935, rel=0, abs=1e-15)
    experienced.observe(.5935)
    assert experienced.value == pytest.approx(untouched.value, rel=0, abs=1e-15)
    assert (untouched._betrayals, experienced._betrayals) == (0, 1)
    untouched.observe(1)
    experienced.observe(1)
    assert untouched.value == pytest.approx(.525, rel=0, abs=1e-15)
    assert experienced.value == pytest.approx(.5325, rel=0, abs=1e-15)


def test_zero_severity_can_change_memory_and_is_not_a_missing_observation():
    meter = TrustMeter(theta=.5, alpha_pos=.05, alpha_neg=.5, delta=.3)
    meter.observe(.2, severity=0)
    assert meter.value == .5 and meter._betrayals == 1
    meter.observe(1)
    assert meter.value == pytest.approx(.5325, rel=0, abs=1e-15)


@pytest.mark.parametrize("theta,promotes", [(.55, False), (.6, True)])
def test_hybrid_promotion_is_strict_and_can_occur_on_first_decision(theta, promotes):
    player = UTMTFT_WSLS(theta=theta, promote_at=.55)
    player.strategy(axl.Cooperator())
    assert isinstance(player.inner, axl.WinStayLoseShift) == promotes


def test_hybrid_promotion_receives_gate_forced_history_and_reset_restores_tft():
    player = UTMTFT_WSLS(theta=.4, alpha_pos=1, alpha_neg=0, delta=0,
                         threshold=.45, promote_at=.45)
    trace = axl.Match((player, axl.Cooperator()), turns=3, seed=42).play()
    # First D is forced by the gate. After promotion, WSLS must observe DC,
    # rather than the original TFT proposal C, to keep proposing D.
    assert trace == [(axl.Action.D, axl.Action.C)] * 3
    assert isinstance(player.inner, axl.WinStayLoseShift)
    assert list(player.inner.history) == [axl.Action.D, axl.Action.D]
    assert player.trust.value == .5
    player.reset()
    assert not player.history and not player.inner.history
    assert isinstance(player.inner, axl.TitForTat)
    assert player.trust.value == .4 and player.trust._betrayals == 0
    assert player.promote_at == .45


def shipped_presets():
    return yaml.safe_load((Path(__file__).resolve().parents[1] / 'config/presets.yaml').read_text())


@pytest.mark.parametrize('name,variant,parameters,opening,after_dc,after_cd', [
    ('The Diplomat', UTMTFT, (.65, .03, .9, .8, .6), axl.Action.C, .407, 0),
    ('The Maverick', UTMWSLS, (.45, .03, .75, .65, .5), axl.Action.D, .4515, 0),
    ('The Guardian', UTMTFT, (.7, .02, .6, .4, .6), axl.Action.C, .532, 0),
    ('The Opportunist', UTMWSLS, (.3, .04, .55, .8, .45), axl.Action.D, .308, 0),
    ('The Visionary', UTMTFT, (.85, .05, .35, .4, .6), axl.Action.C, .6785, 0),
    ('The Sentinel', UTMTFT_WSLS, (.55, .02, .7, .25, .65), axl.Action.D, .50625, 0),
    ('The Altruist', UTMTFT, (.9, .04, .3, .5, .6), axl.Action.C, .72, .045),
    ('The Trickster', UTMWSLS, (.2, .01, .5, .85, .7), axl.Action.D, .203, 0),
])
def test_named_preset_configuration_and_independent_one_event_expectations(
    name, variant, parameters, opening, after_dc, after_cd
):
    """Published parameter configurations and hand-calculated mechanism controls."""
    spec = shipped_presets()[name]
    assert spec['creator'] == 'Ryan Carlisle'
    assert tuple(spec[key] for key in ['theta', 'alpha_pos', 'alpha_neg', 'delta', 'tau']) == parameters
    assert {'TFT': UTMTFT, 'WSLS': UTMWSLS, 'TFT→WSLS': UTMTFT_WSLS}[spec['variant']] is variant
    resolved = preset_player(spec, Parameters())
    assert type(resolved) is variant
    assert resolved.strategy(axl.Cooperator()) == opening
    # These are fresh-state DC/CD observations at severity 1, not performance
    # or personality claims. Expected values do not call the production rule.
    for moves, expected in [(('D', 'C'), after_dc), (('C', 'D'), after_cd)]:
        fresh = preset_player(spec, Parameters())
        fresh.trust.observe_moves(*moves)
        assert fresh.trust.value == pytest.approx(expected, rel=0, abs=1e-14)


def test_shipped_preset_descriptions_are_prose_without_em_dashes():
    presets = shipped_presets()
    assert len(presets) == 8
    for spec in presets.values():
        assert spec['description'].strip()
        assert '\u2014' not in spec['description']


@pytest.mark.parametrize('turns,expected,counter', [(1, .55, 0), (2, .50625, 1), (3, .4996875, 2)])
def test_sentinel_noiseless_cooperator_trace_does_not_promote_after_conflict(turns, expected, counter):
    sentinel = preset_player(shipped_presets()['The Sentinel'], Parameters())
    trace = axl.Match((sentinel, axl.Cooperator()), turns=turns, seed=42).play()
    assert trace == [(axl.Action.D, axl.Action.C)] * turns
    # A policy processes the previous round at its next decision.
    assert sentinel.trust.value == pytest.approx(expected, rel=0, abs=1e-14)
    assert sentinel.trust._betrayals == counter
    assert type(sentinel.inner) is axl.TitForTat


def test_incomplete_preset_keeps_focal_fallback_semantics():
    fallback = Parameters(theta=.8, alpha_pos=.1, alpha_neg=.2, delta=.3,
                          threshold=.4, variant='WSLS')
    inherited = preset_player({'theta': .7}, fallback)
    assert type(inherited) is UTMWSLS
    assert inherited.init_kwargs == {'theta': .7, 'alpha_pos': .1, 'alpha_neg': .2,
                                      'delta': .3, 'threshold': .4}


def test_bounded_ipd_preset_fixture_resolves_identity_before_checking_payoffs():
    config = TournamentRequest(
        variant='Trust-only IPD', theta=.6, alpha_pos=.02, alpha_neg=.675,
        delta=.45, threshold=.5, opponents=['Cooperator', 'Defector'],
        presets=['The Diplomat', 'The Sentinel'], rounds=20, repetitions=2,
        noise_pct=0, seed=42, extra_opponent='None', noise_wrap=False,
    )
    result = tournament(config, lambda _: None, lambda: None, shipped_presets())
    expected_order = ['Trust-only IPD', 'Cooperator', 'Defector', 'UTM-The Diplomat', 'UTM-The Sentinel']
    resolved = result['metadata']['resolved_players']
    actual_order = [entry['label'].split(':', 1)[0] for entry in resolved]
    assert actual_order == expected_order
    slots = {name: entry['slot'] for name, entry in zip(actual_order, resolved)}
    for entry in resolved:
        assert result['players'][entry['slot']] == entry['label']
    assert resolved[slots['UTM-The Diplomat']]['class'] == 'strategies.utm_tft.UTMTFT'
    assert resolved[slots['UTM-The Sentinel']]['class'] == 'strategies.utm_tft_wsls.UTMTFT_WSLS'
    expected = [
        [3, 3, .95, 3, .95],
        [3, 3, 0, 3, 0],
        [1.2, 5, 1, 1.2, 1],
        [3, 3, .95, 3, .95],
        [1.2, 5, 1, 1.2, 1],
    ]
    for row, name in enumerate(expected_order):
        observed = [result['payoff_matrix'][slots[name]][slots[opponent]] for opponent in expected_order]
        assert observed == pytest.approx(expected[row], rel=0, abs=1e-14)
    for row in result['leaderboard']:
        assert row['#C'] + row['#D'] == 160
    sentinel = next(row for row in result['leaderboard'] if row['Player index'] == slots['UTM-The Sentinel'])
    assert sentinel['#C'] == 0 and sentinel['#D'] == 160 and sentinel['C-rate'] == 0


def test_default_tft_policy_cooperative_field_has_no_payoff_advantage():
    utm = player(Parameters())
    trace = axl.Match((utm, axl.Cooperator()), turns=20, seed=42).play()
    assert trace == [(axl.Action.C, axl.Action.C)] * 20
    assert axl.Game(r=3, s=0, t=5, p=1).score(trace[0]) == (3, 3)
