import pytest
from utm import TrustMeter

def test_trust_update_positive():
    tm = TrustMeter(theta=0.5)
    tm.observe(1.0)
    assert tm.value > 0.5


def test_trust_update_negative():
    tm = TrustMeter(theta=0.5)
    tm.observe(-1.0)
    assert tm.value < 0.5