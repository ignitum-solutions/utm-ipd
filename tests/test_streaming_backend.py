import asyncio
import json
import multiprocessing

import axelrod as axl
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import app
from backend.engine import moran, player, tournament, trust_game
from backend.models import MoranRequest, Parameters, TournamentRequest, TrustRequest
from backend.streaming import stream_run


@pytest.mark.parametrize("variant", ["TFT", "WSLS", "TFT→WSLS", "Trust-only IPD"])
def test_streamed_engine_preserves_seeded_tournament_scores(variant):
    cfg = TournamentRequest(variant=variant, opponents=["Tit For Tat", "Random"], rounds=15, repetitions=2)
    events = []
    actual = tournament(cfg, events.append, lambda: None, {})
    baseline_players = [player(cfg), axl.TitForTat(), axl.Random()]
    baseline = axl.Tournament(baseline_players, turns=15, repetitions=2, seed=42).play(progress_bar=False)
    expected = {str(p): float(np.mean(scores)) for p, scores in zip(baseline_players, baseline.normalised_scores)}
    assert {row["Player"]: row["Mean"] for row in actual["leaderboard"]} == pytest.approx(expected)
    measured = [e for e in events if e.get("completed") is not None]
    assert [e["completed"] for e in measured] == list(range(1, 7))
    assert measured[-1]["total"] == 6
    json.dumps(actual, allow_nan=False)


def test_moran_caps_generations_and_tracks_trust_only_variant():
    cfg = MoranRequest(variant="Trust-only IPD", population=5, generations=3, rounds=5)
    result = moran(cfg, lambda event: None, lambda: None)
    assert len(result["series"]) <= 4
    assert result["series"][0] == .2
    assert result == moran(cfg, lambda event: None, lambda: None)


def test_moran_agrees_with_bounded_axelrod_iteration():
    cfg = MoranRequest(population=5, generations=5, rounds=5)
    utm = player(cfg)
    process = axl.MoranProcess([utm] + [axl.Cooperator() for _ in range(4)], turns=5, seed=42)
    expected = [.2]
    for _ in range(cfg.generations):
        try:
            next(process)
        except StopIteration:
            break
        expected.append(process.populations[-1].get(str(utm), 0) / 5)
    assert moran(cfg, lambda e: None, lambda: None)["series"] == expected


def test_trust_game_is_seeded_and_state_is_fresh():
    cfg = TrustRequest(rounds=40, betrayal_probability=.4)
    first = trust_game(cfg, lambda e: None, lambda: None)
    assert first == trust_game(cfg, lambda e: None, lambda: None)
    assert len(first["series"]) == 40
    assert first["cumulative"][-1] == sum(first["payoffs"])


def test_noise_wrapper_works_with_the_pinned_engine():
    cfg = TournamentRequest(opponents=["Tit For Tat"], extra_opponent="Defector", noise_wrap=True, rounds=10, repetitions=2)
    result = tournament(cfg, lambda e: None, lambda: None, {})
    assert len(result["players"]) == 3
    assert "Noisy" in result["players"][-1]


def test_inputs_reject_nonfinite_and_excessive_work():
    with pytest.raises(ValidationError):
        Parameters(theta=float("nan"))
    with pytest.raises(ValidationError, match="too large"):
        TournamentRequest(rounds=1000, repetitions=100)
    with pytest.raises(ValidationError):
        TournamentRequest(rounds=True)
    with pytest.raises(ValidationError):
        TournamentRequest(opponents=["Defector", "Defector"])


def test_http_rejects_arbitrary_opponents_and_oversized_body():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/run/tournament", json={"opponents": ["os.system"]}).status_code == 422
        assert client.post("/api/run/trust", content=b" " * 17000, headers={"Content-Type": "application/json"}).status_code == 413


def test_submissions_disabled_without_storage_configuration(monkeypatch):
    monkeypatch.delenv("SUBMIT_PREFIX", raising=False)
    with TestClient(app) as client:
        assert client.post("/api/suggestions", json={"name": "Researcher", "description": "A preset"}).status_code == 404


def test_busy_service_rejects_instead_of_queuing(monkeypatch):
    import backend.app as api
    monkeypatch.setattr(api, "_active", api.CAPACITY)
    with TestClient(app) as client:
        response = client.post("/api/run/trust", json={"rounds": 10})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "5"


def test_request_stream_contains_real_terminal_result_and_releases_capacity():
    import backend.app as api
    before = api._active
    with TestClient(app) as client:
        response = client.post("/api/run/trust", json={"rounds": 10})
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0]["type"] == "started"
    assert any(e["type"] == "progress" for e in events)
    assert events[-1]["type"] == "result"
    assert len(events[-1]["result"]["series"]) == 10
    assert api._active == before


def test_run_timeout_terminates_child_and_returns_terminal_error():
    children = {p.pid for p in multiprocessing.active_children()}
    async def run():
        return [json.loads(data) async for data in stream_run("trust", {"rounds": 10}, seconds=.01)]
    events = asyncio.run(run())
    assert events[-1]["type"] == "error"
    assert "time limit" in events[-1]["message"]
    assert {p.pid for p in multiprocessing.active_children()} == children


def test_closing_a_local_stream_cleans_up_request_process():
    children = {p.pid for p in multiprocessing.active_children()}
    closed = []
    async def run():
        stream = stream_run("trust", {}, on_close=lambda: closed.append(True))
        assert json.loads(await anext(stream))["type"] == "started"
        await stream.aclose()
    asyncio.run(run())
    assert closed == [True]
    assert {p.pid for p in multiprocessing.active_children()} == children


def test_built_catalogue_and_trust_game_do_not_import_the_scientific_engine(tmp_path):
    import os
    import subprocess
    import sys
    from backend.catalogue import write_registry
    registry = tmp_path / "catalogue.json"
    write_registry(registry)
    # A fresh interpreter prevents imports elsewhere in the suite from masking
    # accidental engine imports on the metadata or validation request paths.
    source = '''
import sys
sys.modules['axelrod'] = None
sys.modules['backend.engine'] = None
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
import backend.app as api
from backend.models import TrustRequest
from backend.trust_game import trust_game
async def launch(kind, config, presets=None):
    return JSONResponse({'kind':kind})
api.launch = launch
with TestClient(api.app) as client:
    assert 'Defector' in client.get('/api/catalogue').json()['opponents']
    assert client.post('/api/run/tournament', json={'opponents':['Defector']}).json() == {'kind':'tournament'}
    assert client.post('/api/run/tournament', json={'opponents':['os.system']}).status_code == 422
result = trust_game(TrustRequest(rounds=3), lambda _:None, lambda:None)
assert len(result['series']) == 3
'''
    subprocess.run([sys.executable, "-c", source], env={**os.environ, "UTM_CATALOGUE_PATH": str(registry)},
                   check=True, capture_output=True, text=True, timeout=30)


def test_generated_catalogue_matches_the_installed_strategy_registry(tmp_path):
    from backend.catalogue import write_registry
    from backend.engine import REGISTRY, STRATEGIES
    from dash.opponents import extra_opponent_options
    target = tmp_path / "catalogue.json"
    write_registry(target)
    saved = json.loads(target.read_text())
    assert saved == {"variants": list(REGISTRY), "opponents": sorted(STRATEGIES),
                     "extra_opponents": extra_opponent_options()}
