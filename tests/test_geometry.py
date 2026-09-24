import pytest

from aei_link_clearance.geometry import bearing_deg, great_circle_intermediate_point


def test_bearing_due_north():
    assert bearing_deg(43.0, -79.0, 44.0, -79.0) == pytest.approx(0.0, abs=0.1)


def test_bearing_due_east_at_equator():
    # Bearing formulas are only exactly 90 deg for due-east at the equator;
    # away from it, a great-circle "due east" bearing at departure isn't 90.
    assert bearing_deg(0.0, -79.0, 0.0, -78.0) == pytest.approx(90.0, abs=0.1)


def test_bearing_is_0_to_360():
    for lat2, lon2 in [(43.5, -79.5), (44.5, -78.5), (42.5, -80.5), (43.7, -79.7)]:
        b = bearing_deg(43.6, -79.6, lat2, lon2)
        assert 0.0 <= b < 360.0


def test_intermediate_point_endpoints():
    lat1, lon1, lat2, lon2 = 43.6426, -79.3871, 44.0592, -79.4613
    start = great_circle_intermediate_point(lat1, lon1, lat2, lon2, 0.0)
    end = great_circle_intermediate_point(lat1, lon1, lat2, lon2, 1.0)
    assert start == pytest.approx((lat1, lon1), abs=1e-6)
    assert end == pytest.approx((lat2, lon2), abs=1e-6)


def test_intermediate_point_midpoint_is_between():
    lat1, lon1, lat2, lon2 = 43.6426, -79.3871, 44.0592, -79.4613
    mid_lat, mid_lon = great_circle_intermediate_point(lat1, lon1, lat2, lon2, 0.5)
    assert min(lat1, lat2) < mid_lat < max(lat1, lat2)
    assert min(lon1, lon2) < mid_lon < max(lon1, lon2)
