"""First Fresnel zone radius -- ITU-R P.526 diffraction theory, in its
standard practical engineering form. See README.md's Methodology section
for the full sourcing; not repeated in full here.

    r1 [m] = 17.3 * sqrt(d1 * d2 / (f * (d1 + d2)))

with d1, d2 in km (distances from the point to each end of the path) and f
in GHz. Cross-checked against the well-known midpoint-case constant
(8.656 * sqrt(D/f), D = total path length) -- this general form reduces to
exactly that when d1 = d2 = D/2.
"""
from __future__ import annotations


def fresnel_radius_m(d1_km: float, d2_km: float, frequency_ghz: float) -> float:
    """Radius of the first Fresnel zone (n=1) at a point ``d1_km`` from one
    end and ``d2_km`` from the other, for a link operating at
    ``frequency_ghz``.

    Raises ValueError for non-positive distances or frequency -- a point
    exactly at either endpoint (d=0) has a Fresnel radius of 0, which is
    physically correct but a degenerate case callers should handle
    explicitly rather than divide by a total distance of zero here.
    """
    if d1_km < 0 or d2_km < 0:
        raise ValueError(f"Distances must be non-negative: d1_km={d1_km}, d2_km={d2_km}")
    if frequency_ghz <= 0:
        raise ValueError(f"frequency_ghz must be positive: {frequency_ghz}")
    total = d1_km + d2_km
    if total == 0:
        return 0.0
    return 17.3 * ((d1_km * d2_km) / (frequency_ghz * total)) ** 0.5
