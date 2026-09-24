"""Bearing/azimuth and great-circle interpolation -- exactly the geometry
aei-geo-features' own README says is out of scope for that package.
Distance itself is NOT reimplemented here; see terrain.py, which imports
``haversine_distance`` from ``aei_geo_features`` directly.
"""
from __future__ import annotations

from math import asin, atan2, cos, degrees, radians, sin


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial (forward) great-circle bearing from point 1 to point 2, in
    degrees clockwise from true north, 0-360.

    Standard great-circle bearing formula (the same one behind, e.g., Ed
    Williams' Aviation Formulary and most GIS bearing calculators):

        theta = atan2(sin(dlon) * cos(lat2),
                       cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon))
    """
    phi1, phi2 = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    y = sin(dlon) * cos(phi2)
    x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dlon)
    theta = atan2(y, x)
    return (degrees(theta) + 360) % 360


def great_circle_intermediate_point(
    lat1: float, lon1: float, lat2: float, lon2: float, fraction: float
) -> tuple[float, float]:
    """The point a given ``fraction`` (0.0 = point 1, 1.0 = point 2) of the
    way along the great-circle path between two points.

    Standard spherical interpolation ("intermediate point on a great
    circle"), same family of formula as bearing_deg above -- not a linear
    lat/lon interpolation, which would be a poor approximation at higher
    latitudes.
    """
    phi1, lam1 = radians(lat1), radians(lon1)
    phi2, lam2 = radians(lat2), radians(lon2)

    d = 2 * asin(
        min(
            1.0,
            (sin((phi2 - phi1) / 2) ** 2 + cos(phi1) * cos(phi2) * sin((lam2 - lam1) / 2) ** 2) ** 0.5,
        )
    )
    if d == 0:
        return lat1, lon1

    a = sin((1 - fraction) * d) / sin(d)
    b = sin(fraction * d) / sin(d)
    x = a * cos(phi1) * cos(lam1) + b * cos(phi2) * cos(lam2)
    y = a * cos(phi1) * sin(lam1) + b * cos(phi2) * sin(lam2)
    z = a * sin(phi1) + b * sin(phi2)

    lat_i = degrees(atan2(z, (x * x + y * y) ** 0.5))
    lon_i = degrees(atan2(y, x))
    return lat_i, lon_i
