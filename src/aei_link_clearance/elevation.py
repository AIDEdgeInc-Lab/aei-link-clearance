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
from typing import List, Sequence, Tuple

ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
MAX_COORDS_PER_REQUEST = 100
SOURCE = "Open-Meteo Elevation API (Copernicus DEM GLO-90, 90m, surface model)"


class ElevationDataError(ValueError):
    """The elevation service returned data that cannot be used as it is: the wrong number of values, or a value that is missing or not a
    finite number (null, NaN, infinity, text). A missing elevation is never treated as 0 m. Subclasses ValueError, so code that already
    catches the wrong-count ValueError keeps working."""


def _is_finite_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def get_elevations(points: Sequence[Tuple[float, float]], timeout: float = 15.0) -> List[float]:
    """Elevation in metres for each (lat, lon) in ``points``, same order.

    Batches into requests of at most ``MAX_COORDS_PER_REQUEST`` points, one
    HTTP call per batch (a single link's profile fits in one call at this
    package's default sample count; only a very long/densely-sampled
    profile would need a second request).
    """
    import requests

    if not points:
        return []

    elevations: List[float] = []
    for start in range(0, len(points), MAX_COORDS_PER_REQUEST):
        batch = points[start : start + MAX_COORDS_PER_REQUEST]
        lats = ",".join(str(p[0]) for p in batch)
        lons = ",".join(str(p[1]) for p in batch)
        resp = requests.get(ELEVATION_URL, params={"latitude": lats, "longitude": lons}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
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
