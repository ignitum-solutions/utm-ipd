import axelrod as axl
from strategies.utm_tft import UTMTFT


def test_first_move_cooperates():
    p1, p2 = UTMTFT(), axl.TitForTat()
    p1.play(p2, 1)
    assert p1.history[-1] == "C"