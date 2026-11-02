"""Writes tests/fixtures/seam_parity.json: links whose ground heights come from a provider, with the Python result.

The JS side (parity/seam_parity.mjs) feeds the SAME heights to the Map's analyzeLinkFromElevations() and must agree. Because a provider only
decides where the heights come from, this proves the seam changes nothing downstream and that Python and JS keep matching for any source.
    python tests/fixtures/make_seam_parity.py            # rewrite
    python tests/fixtures/make_seam_parity.py --check    # exit 1 if the committed file differs
--check compares numbers within the file's own "tolerance" (1e-6) and everything else exactly: the last digits of a float printed by
math.exp / sin / atan2 differ between platforms (macOS and Linux libm), which an exact text comparison reported as "stale" in CI.
"""
import json
import math
import sys
from pathlib import Path

from aei_link_clearance import LocalDEMProvider, analyze_link
from aei_link_clearance.geometry import great_circle_intermediate_point

OUT = Path(__file__).with_name("seam_parity.json")
N = 50


def hump(lat, lon):
    return 100.0 + 60.0 * math.exp(-(((lat - 45.1) / 0.03) ** 2 + ((lon + 75.15) / 0.05) ** 2))


CASES = [
    ("flat-short", dict(site_a_lat=45.0, site_a_lon=-75.0, site_b_lat=45.05, site_b_lon=-75.05, frequency_ghz=7.0), lambda la, lo: 100.0),
    ("hump-mid", dict(site_a_lat=45.0, site_a_lon=-75.0, site_b_lat=45.2, site_b_lon=-75.3, frequency_ghz=7.0), hump),
    ("slope-long-low-ghz", dict(site_a_lat=45.0, site_a_lon=-75.0, site_b_lat=46.2, site_b_lon=-73.9, frequency_ghz=1.0), lambda la, lo: 50.0 + 400.0 * (la - 45.0)),
    ("high-ghz", dict(site_a_lat=45.0, site_a_lon=-75.0, site_b_lat=45.1, site_b_lon=-75.1, frequency_ghz=38.0), hump),
]


def build():
    cases = []
    for name, link, fn in CASES:
        full = dict(link_id=name, site_a_height_m=30.0, site_b_height_m=40.0, **link)
        pts = [great_circle_intermediate_point(link["site_a_lat"], link["site_a_lon"], link["site_b_lat"], link["site_b_lon"], i / (N - 1)) for i in range(N)]
        r = analyze_link(**full, elevation_provider=LocalDEMProvider(fn, "parity.tif"))
        cases.append({
            "name": name, "link": full, "points": pts, "elevations": [p.ground_elevation_m for p in r.profile],
            "expected": {"los_status": r.los_status, "clearance_ratio": r.clearance_ratio, "terrain_clearance_m": r.terrain_clearance_m,
                         "percent_fresnel_clear": r.percent_fresnel_clear, "near_threshold": r.near_threshold, "distance_km": r.distance_km,
                         "clearance_m": [p.clearance_m for p in r.profile]},
        })
    return {"schema": "aei-link-clearance/seam-parity/1", "tolerance": 1e-6, "cases": cases}


def same(a, b, tol):
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None:
        return a is b or a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y, tol) for x, y in zip(a, b))
    return a == b


if __name__ == "__main__":
    data = build()
    if "--check" in sys.argv:
        sys.exit(0 if OUT.exists() and same(json.loads(OUT.read_text()), json.loads(json.dumps(data)), data["tolerance"]) else 1)   # JSON round trip: tuples become lists
    OUT.write_text(json.dumps(data, indent=1) + "\n")
