import axelrod as axl
from strategies.utm_tft import UTMTFT


def test_first_move_cooperates():
    p1, p2 = UTMTFT(), axl.TitForTat()
    assert p1.strategy(p2) == axl.Action.C
