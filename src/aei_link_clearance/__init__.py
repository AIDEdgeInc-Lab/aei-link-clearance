"""aei_link_clearance: batch microwave link terrain-clearance and
margin-based risk ranking.

Built on top of ``aei-geo-features`` (distance, coordinate validation) via a
real package dependency, not a copy -- this module adds only what
aei-geo-features deliberately excludes: bearing/azimuth, elevation-profile
sampling, Fresnel-zone geometry, and earth-curvature-adjusted terrain
clearance. See README.md for the methodology and its sources.
"""

from .explain import explain
from .fresnel import fresnel_radius_m
from .elevation import (
    DEMCrsMismatchError,
    ElevationCoverageError,
    ElevationDataError,
    ElevationServiceUnavailable,
    RetryPolicy,
)
from .geometry import bearing_deg
from .providers import ElevationProvider, LocalDEMProvider, OpenMeteoProvider
from .terrain import (
    LosStatus,
    LinkClearanceResult,
    ProfilePoint,
    analyze_link,
    earth_bulge_m,
)

__version__ = "0.3.0"

__all__ = [
    "__version__",
    "bearing_deg",
    "fresnel_radius_m",
    "earth_bulge_m",
    "analyze_link",
    "ElevationProvider",
    "OpenMeteoProvider",
    "LocalDEMProvider",
    "RetryPolicy",
    "ElevationDataError",
    "ElevationCoverageError",
    "DEMCrsMismatchError",
    "ElevationServiceUnavailable",
    "explain",
    "LinkClearanceResult",
    "ProfilePoint",
    "LosStatus",
]
