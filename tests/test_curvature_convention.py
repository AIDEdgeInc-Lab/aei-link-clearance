"""Earth-curvature sign: the effective-earth bulge is SUBTRACTED from the geometric clearance (equivalently, ADDED to the terrain).

The reference values come from a closed-form straight-chord geometry written out below, not from the code under test: two antenna tops on a
sphere of effective radius k*R, the straight chord between them, and the radial gap between that chord and the ground. This checks the sign
and size of the curvature term only; it is not a validation of the rest of the propagation model.
Constants: k = 4/3 (``DEFAULT_K_FACTOR``), R = 6371 km (``aei_geo_features.geo.EARTH_RADIUS_KM``).
"""
import math

import pytest

import aei_link_clearance.terrain as terrain

RE_M = (4.0 / 3.0) * 6371.0 * 1000.0


def chord_clearance_m(distance_km, fraction, ground_m, mast_m):
    """Radial gap between the straight chord joining two antenna tops and the ground, on a sphere of effective radius k*R."""
    theta = distance_km * 1000.0 / RE_M
    ra = RE_M + ground_m + mast_m
    ax, ay = ra, 0.0
    bx, by = ra * math.cos(theta), ra * math.sin(theta)
    t = fraction * theta
    ux, uy = math.cos(t), math.sin(t)
    dx, dy = bx - ax, by - ay
    s = (ay * ux - ax * uy) / (dx * uy - dy * ux)
    return math.hypot(ax + s * dx, ay + s * dy) - (RE_M + ground_m)


def _flat_link(monkeypatch, km, ground=100.0, mast=30.0, f_ghz=6.35):
    monkeypatch.setattr(terrain, "get_elevations", lambda pts: [ground] * len(pts))
    return terrain.analyze_link("flat", 45.0, -75.0, mast, 45.0 + km / 111.195, -75.0, mast, f_ghz)


def test_marker_names_the_convention():
    assert terrain.CLEARANCE_CONVENTION == "bulge-added-to-terrain"


def test_38km_flat_ground_matches_independent_geometry(monkeypatch):
    r = _flat_link(monkeypatch, 38.1)
    crit = min((p for p in r.profile if p.percent_fresnel_clear is not None), key=lambda p: p.percent_fresnel_clear)
    f = crit.distance_from_a_km / r.distance_km
    assert crit.clearance_m == pytest.approx(chord_clearance_m(r.distance_km, f, 100.0, 30.0), abs=0.01)
    assert crit.clearance_m == pytest.approx(8.648, abs=0.02)          # about 8.6 m; releases before 0.2.0 gave about 51.4 m
    assert crit.clearance_m < 30.0                                      # a straight ray cannot clear flat ground by more than the mast height


@pytest.mark.parametrize("km", [10.0, 100.0, 203.3])
def test_every_sample_matches_independent_geometry(monkeypatch, km):
    r = _flat_link(monkeypatch, km)
    for p in r.profile[1:-1]:
        f = p.distance_from_a_km / r.distance_km
        assert p.clearance_m == pytest.approx(chord_clearance_m(r.distance_km, f, 100.0, 30.0), abs=0.02)


def test_terrain_adjusted_is_ground_plus_bulge(monkeypatch):
    r = _flat_link(monkeypatch, 38.1)
    mid = r.profile[len(r.profile) // 2]
    assert mid.terrain_adjusted_m == pytest.approx(mid.ground_elevation_m + mid.earth_bulge_m)
    assert mid.clearance_m == pytest.approx(mid.los_height_m - mid.ground_elevation_m - mid.earth_bulge_m)


def test_longer_flat_paths_have_less_midpath_clearance(monkeypatch):
    mids = []
    for km in (5.0, 20.0, 40.0, 80.0):
        r = _flat_link(monkeypatch, km)
        mids.append(r.profile[len(r.profile) // 2].clearance_m)
    assert mids == sorted(mids, reverse=True)
