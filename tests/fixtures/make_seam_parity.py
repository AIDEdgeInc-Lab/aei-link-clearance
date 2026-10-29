"""Writes tests/fixtures/seam_parity.json: links whose ground heights come from a provider, with the Python result.

The JS side (parity/seam_parity.mjs) feeds the SAME heights to the Map's analyzeLinkFromElevations() and must agree. Because a provider only
decides where the heights come from, this proves the seam changes nothing downstream and that Python and JS keep matching for any source.
    python tests/fixtures/make_seam_parity.py            # rewrite
    python tests/fixtures/make_seam_parity.py --check    # exit 1 if the committed file differs
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


if __name__ == "__main__":
    text = json.dumps(build(), indent=1) + "\n"
    if "--check" in sys.argv:
        sys.exit(0 if OUT.exists() and OUT.read_text() == text else 1)
    OUT.write_text(text)
