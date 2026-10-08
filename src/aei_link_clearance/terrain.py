"""Earth-curvature-adjusted terrain clearance for a microwave link --
orchestrates aei_geo_features (distance, validation), this package's own
geometry (bearing, great-circle sampling) and fresnel (zone radius), and
the Open-Meteo elevation client, into one per-link result.

No custom interpolation or estimation of weather/RF conditions happens
here -- every elevation value is a value Open-Meteo's API returned for a
queried point; the only "modelling" is the standard, cited earth-bulge
geometry below.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

from aei_geo_features.geo import EARTH_RADIUS_KM, haversine_distance, validate_coordinate

from .elevation import get_elevations
from .fresnel import fresnel_radius_m
from .geometry import bearing_deg, great_circle_intermediate_point

LosStatus = Literal["clear", "marginal", "obstructed"]

# The 60%-of-first-Fresnel-zone "clear" threshold is standard microwave
# link engineering practice (see README.md Methodology) -- NOT an ITU-R
# compliance figure, and should not be described as one in downstream copy.
CLEAR_THRESHOLD = 0.60
# The 30% marginal/obstructed split is not sourced from any standard -- it
# is a judgment call, a reasonable middle bucket between "clearly fine" and
# "clearly blocked," nothing more.
OBSTRUCTED_THRESHOLD = 0.30

DEFAULT_K_FACTOR = 4.0 / 3.0  # ITU-R P.530 median value for a standard/temperate atmosphere
DEFAULT_SAMPLE_COUNT = 50  # points along the path; keeps one link to one Open-Meteo request (limit: 100)

# From a validation check against an independent tool (see README.md):
# two real coordinate pairs on the same terrain feature showed
# a ~13-14m gap between this package's Copernicus DEM GLO-90 reading and
# the other tool's AWS Terrain Tiles reading, at the SAME location, after
# ruling out our own sampling density as the cause. 15m is used here as a
# deliberately conservative (round up, not down) estimate of "how much
# could a different, equally-legitimate DEM source disagree with us at one
# point" -- not a statistically derived confidence interval, and not
# claimed as one anywhere this constant is used.
ELEVATION_UNCERTAINTY_M = 15.0

# Names the earth-curvature sign convention this module implements. A program that depends on this package (for example one that must not
# mix results from releases with different conventions) can read ``aei_link_clearance.terrain.CLEARANCE_CONVENTION`` and refuse to run if
# it is missing or different. Releases before 0.2.0 do not define it and used the opposite sign.
#   "bulge-added-to-terrain": the effective-earth bulge is added to the terrain elevation (terrain_adjusted = ground + bulge), i.e. it is
#   subtracted from the geometric clearance. The value changes only if the convention changes.
CLEARANCE_CONVENTION = "bulge-added-to-terrain"


def earth_bulge_m(d1_km: float, d2_km: float, k_factor: float = DEFAULT_K_FACTOR) -> float:
    """Earth-curvature bulge height, in metres, at a point ``d1_km`` from
    one end and ``d2_km`` from the other of a path, using the standard
    effective-earth-radius approximation:

        h = (d1 * d2) / (2 * k * R)

    with d1, d2, R in the same units (km here), converted to metres.

    Sign convention: the bulge is ADDED to the terrain elevation, so a
    straight line between the antenna tops on the ADJUSTED profile
    represents the true curved-earth line of sight; equivalently the bulge
    is SUBTRACTED from the geometric clearance. Releases before 0.2.0
    subtracted it from the terrain instead, which overstated clearance by
    twice the bulge (about 42.7 m at the middle of a 38.1 km path).
    """
    if k_factor <= 0:
        raise ValueError(f"k_factor must be positive: {k_factor}")
    return (d1_km * d2_km) / (2 * k_factor * EARTH_RADIUS_KM) * 1000.0


@dataclass(frozen=True)
class ProfilePoint:
    distance_from_a_km: float
    latitude: float
    longitude: float
    ground_elevation_m: float
    earth_bulge_m: float
    terrain_adjusted_m: float  # ground_elevation_m + earth_bulge_m
    los_height_m: float  # straight line between the two antenna tops, at this point
    fresnel_radius_m: float
    clearance_m: float  # los_height_m - terrain_adjusted_m
    percent_fresnel_clear: Optional[float]  # clearance_m / fresnel_radius_m; None where fresnel_radius_m == 0 (at the endpoints)


@dataclass(frozen=True)
class LinkClearanceResult:
    link_id: str
    distance_km: float
    bearing_deg: float
    frequency_ghz: float
    k_factor: float
    first_fresnel_radius_m: float  # at the critical (worst-clearance) point
    required_clearance_m: float  # CLEAR_THRESHOLD * first_fresnel_radius_m, at the critical point
    terrain_clearance_m: float  # actual clearance at the critical point
    clearance_ratio: float  # terrain_clearance_m / required_clearance_m -- the risk-ranking metric
    los_status: LosStatus
    obstruction_distance_km: Optional[float]  # distance from site A to the critical point, when not clear
    percent_fresnel_clear: float  # terrain_clearance_m / first_fresnel_radius_m, at the critical point
    near_threshold: bool  # see _is_near_threshold() -- an elevation-uncertainty check, not a new los_status
    profile: List[ProfilePoint] = field(default_factory=list)


def _classify(percent_fresnel_clear: float) -> LosStatus:
    if percent_fresnel_clear >= CLEAR_THRESHOLD:
        return "clear"
    if percent_fresnel_clear >= OBSTRUCTED_THRESHOLD:
        return "marginal"
    return "obstructed"


def _is_near_threshold(percent_fresnel_clear: float, fresnel_radius_m: float) -> bool:
    """True when a plausible elevation-data disagreement (see
    ELEVATION_UNCERTAINTY_M) could flip this link's los_status across
    either the 60% (clear/marginal) or 30% (marginal/obstructed)
    boundary -- i.e. when the classification isn't robust to the kind of
    DEM-source discrepancy the README's validation check actually measured.

    Geometry-dependent by construction: the same 15m absolute elevation
    uncertainty is a much bigger swing in percent-of-Fresnel-zone terms for
    a link with a small Fresnel radius (short path and/or high frequency)
    than for one with a large radius (long path and/or low frequency) --
    computed here per-link from that link's own fresnel_radius_m, not a
    single hardcoded ratio band applied to every link regardless of its
    geometry.
    """
    if fresnel_radius_m <= 0:
        return False
    swing = ELEVATION_UNCERTAINTY_M / fresnel_radius_m
    lower, upper = percent_fresnel_clear - swing, percent_fresnel_clear + swing
    return (lower < CLEAR_THRESHOLD < upper) or (lower < OBSTRUCTED_THRESHOLD < upper)


def analyze_link(
    link_id: str,
    site_a_lat: float,
    site_a_lon: float,
    site_a_height_m: float,
    site_b_lat: float,
    site_b_lon: float,
    site_b_height_m: float,
    frequency_ghz: float,
    k_factor: float = DEFAULT_K_FACTOR,
    n_samples: int = DEFAULT_SAMPLE_COUNT,
) -> LinkClearanceResult:
    """Full terrain-clearance analysis for one microwave link.

    Coordinate validation and the total path distance are both reused
    directly from aei_geo_features, not reimplemented. Elevation profile
    sampling, bearing, Fresnel geometry, and the earth-curvature-adjusted
    clearance check are this package's own, composed on top.
    """
    validate_coordinate(site_a_lat, site_a_lon)
    validate_coordinate(site_b_lat, site_b_lon)
    if frequency_ghz <= 0:
        raise ValueError(f"frequency_ghz must be positive: {frequency_ghz}")
    if n_samples < 2:
        raise ValueError(f"n_samples must be at least 2: {n_samples}")

    distance_km = haversine_distance(site_a_lat, site_a_lon, site_b_lat, site_b_lon)
    bearing = bearing_deg(site_a_lat, site_a_lon, site_b_lat, site_b_lon)

    fractions = [i / (n_samples - 1) for i in range(n_samples)]
    sample_points = [
        great_circle_intermediate_point(site_a_lat, site_a_lon, site_b_lat, site_b_lon, f) for f in fractions
    ]
    ground_elevations = get_elevations(sample_points)

    antenna_a_top_m = ground_elevations[0] + site_a_height_m
    antenna_b_top_m = ground_elevations[-1] + site_b_height_m

    profile: List[ProfilePoint] = []
    for f, (lat, lon), ground_elev in zip(fractions, sample_points, ground_elevations):
        d1 = distance_km * f
        d2 = distance_km * (1 - f)
        bulge = earth_bulge_m(d1, d2, k_factor)
        terrain_adjusted = ground_elev + bulge
        los_height = antenna_a_top_m + f * (antenna_b_top_m - antenna_a_top_m)
        f1_radius = fresnel_radius_m(d1, d2, frequency_ghz)
        clearance = los_height - terrain_adjusted
        percent_clear = (clearance / f1_radius) if f1_radius > 0 else None
        profile.append(
            ProfilePoint(
                distance_from_a_km=d1,
                latitude=lat,
                longitude=lon,
                ground_elevation_m=ground_elev,
                earth_bulge_m=bulge,
                terrain_adjusted_m=terrain_adjusted,
                los_height_m=los_height,
                fresnel_radius_m=f1_radius,
                clearance_m=clearance,
                percent_fresnel_clear=percent_clear,
            )
        )

    # The critical point is the one with the lowest percent-of-Fresnel-zone
    # clearance -- a link is only as good as its worst point. Points at the
    # very endpoints have fresnel_radius_m == 0 (percent_fresnel_clear is
    # None there) and are excluded from this search on purpose: a zero-radius
    # zone can't be meaningfully "cleared," and clearance right at the mast
    # base isn't the geometry this analysis is meant to catch.
    interior = [p for p in profile if p.percent_fresnel_clear is not None]
    critical = min(interior, key=lambda p: p.percent_fresnel_clear) if interior else profile[len(profile) // 2]

    percent_clear_critical = critical.percent_fresnel_clear if critical.percent_fresnel_clear is not None else 1.0
    los_status = _classify(percent_clear_critical)
    near_threshold = _is_near_threshold(percent_clear_critical, critical.fresnel_radius_m)
    required_clearance = CLEAR_THRESHOLD * critical.fresnel_radius_m
    clearance_ratio = (critical.clearance_m / required_clearance) if required_clearance > 0 else float("inf")

    return LinkClearanceResult(
        link_id=link_id,
        distance_km=distance_km,
        bearing_deg=bearing,
        frequency_ghz=frequency_ghz,
        k_factor=k_factor,
        first_fresnel_radius_m=critical.fresnel_radius_m,
        required_clearance_m=required_clearance,
        terrain_clearance_m=critical.clearance_m,
        clearance_ratio=clearance_ratio,
        los_status=los_status,
        obstruction_distance_km=None if los_status == "clear" else critical.distance_from_a_km,
        percent_fresnel_clear=percent_clear_critical,
        near_threshold=near_threshold,
        profile=profile,
    )
