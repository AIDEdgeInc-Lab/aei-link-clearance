"""Open-Meteo Elevation API client -- Copernicus DEM GLO-90, 90 m
resolution, global, free, no API key. Confirmed live to accept
up to 100 comma-separated coordinate pairs per request; this module never
sends more than that in one call.

Copernicus DEM GLO-90 is a DIGITAL SURFACE MODEL, not a bare-earth DEM --
see README.md's Methodology section. Nothing in this module claims
otherwise.

Licensing notice: Open-Meteo's free tier, which this module uses, is for
non-commercial use only (data CC-BY 4.0). Commercial use requires your own
paid Open-Meteo subscription (https://open-meteo.com/en/pricing); this
package does not include or imply one.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
MAX_COORDS_PER_REQUEST = 100
SOURCE = "Open-Meteo Elevation API (Copernicus DEM GLO-90, 90m, surface model)"


class ElevationDataError(ValueError):
    """The elevation service returned data that cannot be used as it is: the wrong number of values, or a value that is missing or not a
    finite number (null, NaN, infinity, text). A missing elevation is never treated as 0 m. Subclasses ValueError, so code that already
    catches the wrong-count ValueError keeps working."""


class ElevationCoverageError(ElevationDataError):
    """A provider has no elevation for one or more requested points (outside the raster, on a nodata cell). The profile is refused: a missing
    elevation is never replaced by 0 m, by a neighbour, or by another source."""


class DEMCrsMismatchError(ElevationCoverageError):
    """A local DEM is not in a coordinate system the provider can use (it is not geographic WGS84 and no reprojection was set up), so any
    height read from it would be wrong. Raised before a single value is read."""


class ElevationServiceUnavailable(ElevationDataError):
    """The online elevation service failed after the bounded retries (or while the provider's cool-down after a rate limit was running).
    Says something about the SERVICE, never about the link. ``transient`` is True when trying again later may work; ``daily`` is True for a
    per-day quota (no retry today helps); ``kind`` is one of "rate limit", "daily limit", "server error", "network", "client error",
    "other"; ``status`` is the HTTP status when there was one."""

    def __init__(self, message: str, *, transient: bool, daily: bool, kind: str, status: Optional[int] = None):
        super().__init__(message)
        self.transient, self.daily, self.kind, self.status = transient, daily, kind, status


# --- failure classification and bounded retry ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Failure:
    transient: bool
    daily: bool
    status: Optional[int]
    retry_after: Optional[float]
    kind: str


def classify_failure(exc: BaseException) -> Failure:
    """What kind of failure is this? Only HTTP 429, 5xx, timeouts and connection errors are transient; a *daily* 429 is transient but not
    worth retrying today. Everything else (other 4xx, bad data) is deterministic."""
    import requests
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status is None:
        match = re.match(r"\s*(\d{3})\b", str(exc))
        status = int(match.group(1)) if match else None
    try:
        text = (getattr(response, "text", "") or "").lower()
    except (requests.exceptions.RequestException, RuntimeError, ValueError):
        text = ""
    retry_after = None
    try:
        header = (getattr(response, "headers", None) or {}).get("Retry-After")
        retry_after = float(header) if header is not None else None
    except (TypeError, ValueError):
        retry_after = None
    if status == 429:
        daily = "daily" in text
        return Failure(True, daily, status, retry_after, "daily limit" if daily else "rate limit")
    if status is not None and 500 <= status <= 599:
        return Failure(True, False, status, retry_after, "server error")
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return Failure(True, False, status, retry_after, "network")
    if status is not None and 400 <= status <= 499:
        return Failure(False, False, status, None, "client error")
    return Failure(False, False, status, None, "other")


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded backoff. ``delays_s`` has one entry per extra attempt; a server ``Retry-After`` longer than ``max_retry_after_s`` is not waited
    for (the failure is reported instead). ``cooldown_s``: after a rate limit that outlasted the retries, the provider refuses further
    requests for this long WITHOUT calling the service (a batch of links must not hammer a service that has just said no)."""
    delays_s: Tuple[float, ...] = (1.0, 3.0)
    max_retry_after_s: float = 10.0
    cooldown_s: float = 30.0


DEFAULT_RETRY = RetryPolicy()


def _is_finite_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _get_json(url: str, params: dict, timeout: float, retry: Optional[RetryPolicy], sleep: Callable[[float], None]):
    import requests
    attempt = 0
    while True:
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            failure = classify_failure(exc)
            if retry is None or not failure.transient or failure.daily or attempt >= len(retry.delays_s):
                raise
            wait = retry.delays_s[attempt]
            if failure.retry_after is not None:
                if failure.retry_after > retry.max_retry_after_s:
                    raise
                wait = max(wait, failure.retry_after)
            sleep(wait)
            attempt += 1


def get_elevations(
    points: Sequence[Tuple[float, float]],
    timeout: float = 15.0,
    retry: Optional[RetryPolicy] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> List[float]:
    """Elevation in metres for each (lat, lon) in ``points``, same order.

    ``retry=None`` (the default) keeps the historical behaviour: one attempt per request, any failure raised as it happened. Pass a
    ``RetryPolicy`` to retry transient failures; ``OpenMeteoProvider`` does that.

    Batches into requests of at most ``MAX_COORDS_PER_REQUEST`` points, one
    HTTP call per batch (a single link's profile fits in one call at this
    package's default sample count; only a very long/densely-sampled
    profile would need a second request).
    """
    if not points:
        return []

    elevations: List[float] = []
    for start in range(0, len(points), MAX_COORDS_PER_REQUEST):
        batch = points[start : start + MAX_COORDS_PER_REQUEST]
        lats = ",".join(str(p[0]) for p in batch)
        lons = ",".join(str(p[1]) for p in batch)
        data = _get_json(ELEVATION_URL, {"latitude": lats, "longitude": lons}, timeout, retry, sleep)
        batch_elevations = data.get("elevation")
        if batch_elevations is None or len(batch_elevations) != len(batch):
            raise ElevationDataError(
                f"Open-Meteo Elevation API returned {len(batch_elevations or [])} values "
                f"for {len(batch)} requested points -- refusing to guess which is which."
            )
        if not all(_is_finite_number(e) for e in batch_elevations):
            raise ElevationDataError(
                "Open-Meteo Elevation API returned a missing or non-numeric elevation (null/NaN) -- "
                "it is never treated as 0 m."
            )
        elevations.extend(float(e) for e in batch_elevations)
    return elevations
