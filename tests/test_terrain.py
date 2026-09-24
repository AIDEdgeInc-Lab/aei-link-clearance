import pytest

from aei_link_clearance.terrain import earth_bulge_m


def test_earth_bulge_symmetric():
    assert earth_bulge_m(10, 10) == earth_bulge_m(10, 10)


def test_earth_bulge_zero_at_either_endpoint():
    assert earth_bulge_m(0, 20) == 0.0
    assert earth_bulge_m(20, 0) == 0.0


def test_earth_bulge_matches_hand_calculation():
    # h = d1*d2 / (2 * k * R), R = 6371 km, k = 4/3, d1=d2=10km -> ~5.9 m,
    # a commonly-cited approximate figure for a 20 km path at k=4/3.
    assert earth_bulge_m(10, 10, k_factor=4 / 3) == pytest.approx(5.886, abs=0.01)


def test_lower_k_factor_increases_bulge():
    # A lower k-factor means less favourable refraction -- more apparent
    # curvature, so the bulge should be larger, not smaller.
    assert earth_bulge_m(10, 10, k_factor=1.0) > earth_bulge_m(10, 10, k_factor=4 / 3)


def test_rejects_non_positive_k_factor():
    with pytest.raises(ValueError):
        earth_bulge_m(10, 10, k_factor=0)
