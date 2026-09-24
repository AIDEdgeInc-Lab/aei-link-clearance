import pytest

from aei_link_clearance.fresnel import fresnel_radius_m


def test_matches_known_midpoint_constant():
    # At the path midpoint (d1 == d2 == D/2), the general form reduces to
    # the well-known 8.656 * sqrt(D/f) constant -- cross-checked against
    # Wikipedia's Fresnel-zone article in Phase 0.
    D, f = 10.0, 7.0
    d1 = d2 = D / 2
    expected = 8.656 * (D / f) ** 0.5
    assert fresnel_radius_m(d1, d2, f) == pytest.approx(expected, rel=1e-3)


def test_zero_at_either_endpoint():
    assert fresnel_radius_m(0, 10, 7) == 0.0
    assert fresnel_radius_m(10, 0, 7) == 0.0


def test_larger_at_lower_frequency():
    assert fresnel_radius_m(5, 5, 2) > fresnel_radius_m(5, 5, 20)


def test_rejects_negative_distance():
    with pytest.raises(ValueError):
        fresnel_radius_m(-1, 5, 7)


def test_rejects_non_positive_frequency():
    with pytest.raises(ValueError):
        fresnel_radius_m(5, 5, 0)
