"""The elevation-provider seam: default behaviour unchanged, local DEM refuses to guess, online provider caches and backs off."""
import math

import pytest
import requests

import aei_link_clearance.terrain as terrain
from aei_link_clearance import (
    DEMCrsMismatchError,
    ElevationCoverageError,
    ElevationDataError,
    ElevationServiceUnavailable,
    LocalDEMProvider,
    OpenMeteoProvider,
    RetryPolicy,
    analyze_link,
)
from aei_link_clearance.elevation import SOURCE, get_elevations

LINK = dict(link_id="L1", site_a_lat=45.0, site_a_lon=-75.0, site_a_height_m=30.0,
            site_b_lat=45.2, site_b_lon=-75.3, site_b_height_m=40.0, frequency_ghz=7.0)


def hump(lat, lon):
    """Deterministic synthetic terrain: 100 m plus a 60 m hump centred between the sites."""
    return 100.0 + 60.0 * math.exp(-(((lat - 45.1) / 0.03) ** 2 + ((lon + 75.15) / 0.05) ** 2))


class Stub:
    source = "stub terrain"

    def __init__(self, fn=hump):
        self.fn, self.calls = fn, 0

    def get_elevations(self, pts):
        self.calls += 1
        return [self.fn(la, lo) for la, lo in pts]


# --- default path -------------------------------------------------------------------------------------------------------------------

def test_default_path_calls_module_get_elevations_once_and_names_open_meteo(monkeypatch):
    seen = []
    monkeypatch.setattr(terrain, "get_elevations", lambda pts: seen.append(len(pts)) or [hump(*p) for p in pts])
    r = analyze_link(**LINK)
    assert seen == [50]
    assert r.elevation_source == SOURCE


def test_provider_with_same_heights_gives_identical_result_to_default(monkeypatch):
    monkeypatch.setattr(terrain, "get_elevations", lambda pts: [hump(*p) for p in pts])
    default = analyze_link(**LINK)
    seamed = analyze_link(**LINK, elevation_provider=Stub())
    assert seamed.profile == default.profile                       # every field of every sample, exactly
    for f in ("distance_km", "clearance_ratio", "los_status", "terrain_clearance_m", "percent_fresnel_clear", "near_threshold"):
        assert getattr(seamed, f) == getattr(default, f)
    assert seamed.elevation_source == "stub terrain" and default.elevation_source == SOURCE


def test_hump_is_found_as_the_critical_point():
    r = analyze_link(**LINK, elevation_provider=Stub())
    assert r.los_status in ("marginal", "obstructed")
    assert 0 < r.obstruction_distance_km < r.distance_km


def test_provider_output_is_validated():
    class Short(Stub):
        def get_elevations(self, pts):
            return [1.0] * (len(pts) - 1)

    class Nulls(Stub):
        def get_elevations(self, pts):
            return [None] + [1.0] * (len(pts) - 1)

    with pytest.raises(ElevationDataError):
        analyze_link(**LINK, elevation_provider=Short())
    with pytest.raises(ElevationDataError):
        analyze_link(**LINK, elevation_provider=Nulls())


# --- get_elevations: retry is opt-in ------------------------------------------------------------------------------------------------

class Resp:
    def __init__(self, status=200, body=None, headers=None, text=""):
        self.status_code, self.body, self.headers, self.text = status, body, headers or {}, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} error", response=self)

    def json(self):
        return self.body


def script(monkeypatch, *responses):
    """requests.get returns/raises the scripted items in order; the last repeats."""
    calls = []

    def fake(url, params=None, timeout=None):
        calls.append(params)
        item = responses[min(len(calls), len(responses)) - 1]
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(requests, "get", fake)
    return calls


def ok(n, v=10.0):
    return Resp(200, {"elevation": [v] * n})


def test_legacy_get_elevations_does_not_retry(monkeypatch):
    calls = script(monkeypatch, Resp(429))
    with pytest.raises(requests.exceptions.HTTPError):
        get_elevations([(1.0, 1.0)])
    assert len(calls) == 1


def test_get_elevations_retries_when_asked(monkeypatch):
    calls = script(monkeypatch, Resp(429), ok(1, 7.0))
    waits = []
    assert get_elevations([(1.0, 1.0)], retry=RetryPolicy(), sleep=waits.append) == [7.0]
    assert len(calls) == 2 and waits == [1.0]


# --- OpenMeteoProvider --------------------------------------------------------------------------------------------------------------

def provider(**kw):
    clock = kw.pop("clock", None) or Clock()
    waits = []
    p = OpenMeteoProvider(clock=clock, sleep=waits.append, **kw)
    p.waits, p.clock = waits, clock
    return p


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


PTS = [(45.0, -75.0), (45.1, -75.1), (45.2, -75.2)]


def test_cache_serves_repeat_without_a_request(monkeypatch):
    calls = script(monkeypatch, ok(3))
    p = provider()
    assert p.get_elevations(PTS) == [10.0, 10.0, 10.0]
    assert p.get_elevations(PTS) == [10.0, 10.0, 10.0]
    assert len(calls) == 1 and p.requests_made == 1


def test_only_missing_points_are_requested_and_order_is_kept(monkeypatch):
    calls = script(monkeypatch, Resp(200, {"elevation": [1.0, 3.0]}), Resp(200, {"elevation": [2.0]}))
    p = provider()
    p.get_elevations([PTS[0], PTS[2]])
    out = p.get_elevations(PTS)
    assert out == [1.0, 2.0, 3.0]
    assert calls[1] == {"latitude": "45.1", "longitude": "-75.1"}


def test_duplicate_points_in_one_call_are_requested_once(monkeypatch):
    calls = script(monkeypatch, Resp(200, {"elevation": [5.0]}))
    assert provider().get_elevations([PTS[0], PTS[0]]) == [5.0, 5.0]
    assert calls[0]["latitude"] == "45.0"


def test_lru_evicts_oldest(monkeypatch):
    script(monkeypatch, ok(1, 1.0))
    p = provider(cache_size=2)
    for pt in PTS:
        p.get_elevations([pt])
    assert p.requests_made == 3
    p.get_elevations([PTS[2]])
    assert p.requests_made == 3        # newest kept
    p.get_elevations([PTS[0]])
    assert p.requests_made == 4        # oldest was evicted


def test_429_is_retried_with_backoff_then_succeeds(monkeypatch):
    calls = script(monkeypatch, Resp(429), Resp(429), ok(3))
    p = provider()
    assert p.get_elevations(PTS) == [10.0] * 3
    assert len(calls) == 3 and p.waits == [1.0, 3.0]


def test_retry_after_header_is_honoured_within_the_cap(monkeypatch):
    script(monkeypatch, Resp(429, headers={"Retry-After": "5"}), ok(3))
    p = provider()
    p.get_elevations(PTS)
    assert p.waits == [5.0]


def test_retry_after_beyond_the_cap_is_reported_not_waited(monkeypatch):
    calls = script(monkeypatch, Resp(429, headers={"Retry-After": "120"}))
    p = provider()
    with pytest.raises(ElevationServiceUnavailable) as e:
        p.get_elevations(PTS)
    assert e.value.kind == "rate limit" and e.value.transient and p.waits == [] and len(calls) == 1


def test_daily_limit_is_not_retried(monkeypatch):
    calls = script(monkeypatch, Resp(429, text="Daily API request limit exceeded"))
    with pytest.raises(ElevationServiceUnavailable) as e:
        provider().get_elevations(PTS)
    assert e.value.daily and e.value.kind == "daily limit" and len(calls) == 1


def test_429_storm_cooldown_stops_hammering_then_recovers(monkeypatch):
    calls = script(monkeypatch, Resp(429), Resp(429), Resp(429), ok(3))
    p = provider()
    with pytest.raises(ElevationServiceUnavailable) as first:
        p.get_elevations(PTS)
    assert first.value.status == 429 and len(calls) == 3           # 1 try + 2 retries
    for _ in range(5):                                             # a batch of links keeps asking
        with pytest.raises(ElevationServiceUnavailable) as e:
            p.get_elevations(PTS)
        assert "not retried" in str(e.value) and e.value.transient
    assert len(calls) == 3                                         # the service was not touched again
    p.clock.t += 31                                                # cool-down over
    assert p.get_elevations(PTS) == [10.0] * 3
    assert len(calls) == 4


def test_5xx_and_timeouts_are_retried(monkeypatch):
    calls = script(monkeypatch, Resp(503), requests.exceptions.ConnectTimeout("t"), ok(3))
    assert provider().get_elevations(PTS) == [10.0] * 3 and len(calls) == 3


def test_other_4xx_is_not_retried_and_not_a_cooldown(monkeypatch):
    calls = script(monkeypatch, Resp(400), ok(3))
    p = provider()
    with pytest.raises(ElevationServiceUnavailable) as e:
        p.get_elevations(PTS)
    assert not e.value.transient and len(calls) == 1
    assert p.get_elevations(PTS) == [10.0] * 3                     # no cool-down after a non-rate-limit failure


def test_failures_are_never_cached(monkeypatch):
    script(monkeypatch, Resp(503), Resp(503), Resp(503), ok(3, 42.0))
    p = provider(retry=RetryPolicy(cooldown_s=0))
    with pytest.raises(ElevationServiceUnavailable):
        p.get_elevations(PTS)
    assert p.get_elevations(PTS) == [42.0] * 3


def test_bad_data_is_a_data_error_not_a_service_outage(monkeypatch):
    script(monkeypatch, Resp(200, {"elevation": [1.0, None, 3.0]}))
    with pytest.raises(ElevationDataError) as e:
        provider().get_elevations(PTS)
    assert not isinstance(e.value, ElevationServiceUnavailable)


def test_clock_skew_cooldown_uses_the_injected_monotonic_clock(monkeypatch):
    # The wall clock is not consulted: moving it cannot lengthen or cancel the cool-down.
    import time
    calls = script(monkeypatch, Resp(429))
    p = provider()
    with pytest.raises(ElevationServiceUnavailable):
        p.get_elevations(PTS)
    monkeypatch.setattr(time, "time", lambda: 0.0)
    with pytest.raises(ElevationServiceUnavailable):
        p.get_elevations(PTS)
    assert len(calls) == 3


def test_analyze_link_through_online_provider_reports_open_meteo(monkeypatch):
    script(monkeypatch, Resp(200, {"elevation": [hump(*p) for p in terrain_points()]}))
    r = analyze_link(**LINK, elevation_provider=provider())
    assert r.elevation_source == SOURCE


def terrain_points():
    from aei_link_clearance.geometry import great_circle_intermediate_point as g
    return [g(45.0, -75.0, 45.2, -75.3, i / 49) for i in range(50)]


# --- LocalDEMProvider ---------------------------------------------------------------------------------------------------------------

def test_local_dem_gives_the_raster_heights_and_names_the_file():
    p = LocalDEMProvider(hump, "dem.tif")
    assert p.get_elevations([(45.1, -75.15)]) == [pytest.approx(160.0)]
    r = analyze_link(**LINK, elevation_provider=p)
    assert r.elevation_source == "Local DEM: dem.tif"
    assert r.profile == analyze_link(**LINK, elevation_provider=Stub()).profile    # same heights -> same maths


@pytest.mark.parametrize("bad", [None, math.nan, math.inf, -math.inf, "x", True])
def test_local_dem_nodata_is_refused_never_zero(bad):
    p = LocalDEMProvider(lambda la, lo: bad if la > 45.1 else 50.0, "dem.tif")
    with pytest.raises(ElevationCoverageError) as e:
        p.get_elevations([(45.0, -75.0), (45.15, -75.1), (45.2, -75.2)])
    assert "2 of 3 points" in str(e.value) and "nothing was substituted" in str(e.value)


def test_local_dem_outside_bounds_never_calls_the_sampler():
    called = []
    p = LocalDEMProvider(lambda la, lo: called.append((la, lo)) or 1.0, "dem.tif", bounds=(44.9, -75.4, 45.1, -75.0))
    with pytest.raises(ElevationCoverageError):
        p.get_elevations([(45.0, -75.1), (45.2, -75.1)])
    assert called == [(45.0, -75.1)]


def test_local_dem_partial_coverage_fails_the_whole_analysis():
    p = LocalDEMProvider(lambda la, lo: hump(la, lo) if la < 45.15 else None, "dem.tif")
    with pytest.raises(ElevationCoverageError):
        analyze_link(**LINK, elevation_provider=p)


def test_local_dem_crs_mismatch_is_refused_before_reading():
    called = []
    with pytest.raises(DEMCrsMismatchError):
        LocalDEMProvider(lambda la, lo: called.append(1) or 1.0, "dem.tif", dem_crs="EPSG:32618")
    assert not called


def test_local_dem_projected_crs_is_allowed_when_the_sampler_reprojects():
    p = LocalDEMProvider(hump, "utm.tif", dem_crs="EPSG:32618", sampler_reprojects=True)
    assert p.get_elevations([(45.1, -75.15)]) == [pytest.approx(160.0)]


def test_local_dem_requires_a_source_description():
    with pytest.raises(ValueError):
        LocalDEMProvider(hump, "  ")
