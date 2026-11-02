"""Elevation providers -- the seam ``analyze_link(..., elevation_provider=...)`` takes.

A provider is any object with a ``source`` string (what the evidence says the heights came from) and a ``get_elevations(points)`` method
returning one elevation in metres per ``(lat, lon)`` point, same order. It either returns a finite number for EVERY point or raises an
``ElevationDataError``; it never returns 0 m, a neighbour's value, or another source's value for a point it does not have.

Two are provided:

* ``OpenMeteoProvider`` -- the online service this package has always used (Copernicus DEM GLO-90 through Open-Meteo), plus an in-memory
  cache and bounded backoff on HTTP 429/5xx/timeouts, with a cool-down after a rate limit that outlasted the retries.
* ``LocalDEMProvider`` -- a raster the user holds. The raster is read by a caller-supplied ``sampler(lat, lon) -> metres | None`` (so this
  package stays free of GDAL/rasterio); points outside the raster, on nodata cells, or a raster in the wrong coordinate system are refused.
"""
from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from typing import Callable, Dict, List, Optional, Sequence, Tuple

try:  # typing.Protocol is 3.8+, this package needs 3.9+
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    Protocol = object  # type: ignore

    def runtime_checkable(cls):  # type: ignore
        return cls

from . import elevation as _elevation
from .elevation import (
    DEFAULT_RETRY,
    SOURCE as OPEN_METEO_SOURCE,
    DEMCrsMismatchError,
    ElevationCoverageError,
    ElevationDataError,
    ElevationServiceUnavailable,
    RetryPolicy,
    classify_failure,
)

Point = Tuple[float, float]


@runtime_checkable
class ElevationProvider(Protocol):
    source: str

    def get_elevations(self, points: Sequence[Point]) -> List[float]: ...


def validate_elevations(values, n_expected: int, source: str) -> List[float]:
    """The contract every provider's output must meet (``analyze_link`` applies it to custom providers too)."""
    values = list(values)
    if len(values) != n_expected:
        raise ElevationDataError(f"{source} returned {len(values)} values for {n_expected} points -- refusing to guess which is which.")
    if not all(_elevation._is_finite_number(v) for v in values):
        raise ElevationDataError(f"{source} returned a missing or non-numeric elevation -- it is never treated as 0 m.")
    return [float(v) for v in values]


class OpenMeteoProvider:
    """Online elevations (Open-Meteo, Copernicus DEM GLO-90 surface model) with a cache and bounded backoff.

    * Cache: successful values only, keyed by the point rounded to 5 decimals (~1 m); LRU, ``cache_size`` points. Elevation does not change
      between runs, so a repeated analysis of the same link (or a what-if with other heights) makes no request. A failure is never cached.
    * Backoff: ``RetryPolicy`` (default 1 s then 3 s) on HTTP 429, 5xx, timeouts and connection errors. A daily quota is not retried.
    * Cool-down: when a rate limit outlasts the retries, further calls fail at once for ``retry.cooldown_s`` without touching the service.
    * Clock skew: the cool-down uses a monotonic clock, so a changed system time cannot extend or cancel it.
    Thread-safe (the plugin runs analyses in background tasks).
    """

    source = OPEN_METEO_SOURCE

    def __init__(
        self,
        cache_size: int = 20000,
        retry: Optional[RetryPolicy] = DEFAULT_RETRY,
        timeout: float = 15.0,
        fetch: Optional[Callable[..., List[float]]] = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._cache: "OrderedDict[Point, float]" = OrderedDict()
        self._cache_size = max(0, int(cache_size))
        self._retry, self._timeout = retry, timeout
        self._fetch = fetch
        self._clock, self._sleep = clock, sleep
        self._lock = threading.Lock()
        self._blocked_until = 0.0
        self._blocked_error: Optional[ElevationServiceUnavailable] = None
        self.requests_made = 0   # service calls, for tests and diagnostics

    @staticmethod
    def _key(p: Point) -> Point:
        return (round(float(p[0]), 5), round(float(p[1]), 5))

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def get_elevations(self, points: Sequence[Point]) -> List[float]:
        points = [(float(p[0]), float(p[1])) for p in points]
        if not points:
            return []
        keys = [self._key(p) for p in points]
        with self._lock:
            known: Dict[Point, float] = {}
            for k in keys:
                if k in self._cache:
                    self._cache.move_to_end(k)
                    known[k] = self._cache[k]
        missing = [(k, p) for k, p in dict.fromkeys(zip(keys, points)) if k not in known]
        if missing:
            fetched = self._fetch_missing([p for _, p in missing])
            with self._lock:
                for (k, _), v in zip(missing, fetched):
                    known[k] = v
                    if self._cache_size:
                        self._cache[k] = v
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
        return [known[k] for k in keys]

    def _fetch_missing(self, pts: List[Point]) -> List[float]:
        now = self._clock()
        if now < self._blocked_until and self._blocked_error is not None:
            left = int(self._blocked_until - now) + 1
            err = self._blocked_error
            raise ElevationServiceUnavailable(
                f"{err} (not retried for another {left} s so the service is not hammered)",
                transient=True, daily=err.daily, kind=err.kind, status=err.status,
            )
        import requests
        fetch = self._fetch or _elevation.get_elevations
        try:
            self.requests_made += 1
            values = fetch(pts, timeout=self._timeout, retry=self._retry, sleep=self._sleep) if self._fetch is None else fetch(pts)
        except ElevationDataError:
            raise                                    # bad data (count, null, NaN): deterministic, not a service outage
        except requests.exceptions.RequestException as exc:
            f = classify_failure(exc)
            err = ElevationServiceUnavailable(self._describe(f, exc), transient=f.transient, daily=f.daily, kind=f.kind, status=f.status)
            if f.kind in ("rate limit", "daily limit") and self._retry is not None:
                self._blocked_until = self._clock() + (self._retry.cooldown_s if not f.daily else max(self._retry.cooldown_s, 300.0))
                self._blocked_error = err
            raise err from exc
        return validate_elevations(values, len(pts), self.source)

    @staticmethod
    def _describe(f, exc: BaseException) -> str:
        detail = str(exc)
        detail = (detail[:117] + "...") if len(detail) > 120 else detail
        if f.daily:
            return f"the elevation service's daily request limit is used up (HTTP {f.status}); try again after 00:00 UTC. {detail}"
        if f.kind == "rate limit":
            return f"the elevation service is rate-limiting requests (HTTP {f.status}); try again in a minute. {detail}"
        if f.kind == "server error":
            return f"the elevation service answered a server error (HTTP {f.status}); try again later. {detail}"
        if f.kind == "network":
            return f"the elevation service could not be reached; check the connection. {detail}"
        return detail


WGS84_AUTHIDS = ("EPSG:4326", "OGC:CRS84", "CRS:84")


class LocalDEMProvider:
    """Heights from a raster the user holds, read through ``sampler(lat, lon) -> metres | None``.

    ``sampler`` receives WGS84 latitude/longitude and returns the cell value in metres, or ``None`` (or NaN/inf) where the raster has no
    value. If the raster is not in WGS84 the *sampler* must reproject (the plugin's does, with QgsCoordinateTransform), and the provider is
    told so with ``sampler_reprojects=True``; otherwise a ``dem_crs`` other than WGS84 raises ``DEMCrsMismatchError`` at construction.
    ``bounds`` = (min_lat, min_lon, max_lat, max_lon) in WGS84 is an optional quick pre-check that names the points outside the raster.

    Every requested point must have a value, else ``ElevationCoverageError`` lists how many do not and where the first is. The metres are
    taken as the raster states them: whether the raster is a surface or bare-earth model, and its vertical datum, are the user's to know and
    are echoed in ``source`` so they appear in the evidence.
    """

    def __init__(
        self,
        sampler: Callable[[float, float], Optional[float]],
        source: str,
        dem_crs: str = "EPSG:4326",
        sampler_reprojects: bool = False,
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ):
        if not source or not str(source).strip():
            raise ValueError("a local DEM needs a source description (file name) for the evidence")
        if dem_crs and dem_crs.upper() not in WGS84_AUTHIDS and not sampler_reprojects:
            raise DEMCrsMismatchError(
                f"The DEM is in {dem_crs}, not geographic WGS84 (EPSG:4326), and no reprojection is set up, so heights read from it would "
                "be wrong. Nothing was read. Reproject the raster to EPSG:4326 or use a reader that reprojects.")
        self._sampler, self.source = sampler, f"Local DEM: {source}"
        self.dem_crs, self._bounds = dem_crs, bounds

    def get_elevations(self, points: Sequence[Point]) -> List[float]:
        values: List[float] = []
        outside: List[int] = []
        for i, (lat, lon) in enumerate(points):
            lat, lon = float(lat), float(lon)
            v = None
            inside = True
            if self._bounds is not None:
                s, w, n, e = self._bounds
                inside = s <= lat <= n and w <= lon <= e
            if inside:
                v = self._sampler(lat, lon)
            if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                outside.append(i)
                values.append(math.nan)
            else:
                values.append(float(v))
        if outside:
            lat, lon = points[outside[0]]
            raise ElevationCoverageError(
                f"{self.source} has no elevation for {len(outside)} of {len(points)} points on this path (first: {float(lat):.5f}, {float(lon):.5f}; "
                "outside the raster or on a nodata cell). The profile was not computed and nothing was substituted: use a DEM that covers the "
                "whole path, or the online source.")
        return values
