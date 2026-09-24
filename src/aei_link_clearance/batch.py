"""Batch CSV processing: many candidate microwave links in, one row of
clearance results per link out, ranked by clearance_ratio (the margin-based
risk metric -- not just pass/fail).

Input columns (required, exact names): link_id, site_a_lat, site_a_lon,
site_a_height_m, site_b_lat, site_b_lon, site_b_height_m, frequency_ghz

stdlib csv only -- no pandas dependency for this module.
"""
from __future__ import annotations

import csv
import io
import json
from typing import List, Tuple

from .explain import explain
from .terrain import DEFAULT_K_FACTOR, DEFAULT_SAMPLE_COUNT, LinkClearanceResult, analyze_link

REQUIRED_COLUMNS = [
    "link_id",
    "site_a_lat",
    "site_a_lon",
    "site_a_height_m",
    "site_b_lat",
    "site_b_lon",
    "site_b_height_m",
    "frequency_ghz",
]


def parse_links_csv(csv_text: str) -> Tuple[List[dict], List[str]]:
    """Parses the batch-input CSV. Returns (rows, row_errors) -- a row with
    bad/missing values is skipped and named in row_errors, never silently
    dropped or guessed. Raises ValueError for a missing required column or
    an empty file (a whole-file problem, not a per-row one).
    """
    if not csv_text.strip():
        raise ValueError("The uploaded file is empty.")

    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("The uploaded file has no header row.")
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")

    rows: List[dict] = []
    errors: List[str] = []
    for i, raw in enumerate(reader, start=2):  # header is row 1
        link_id = (raw.get("link_id") or "").strip()
        if not link_id:
            errors.append(f"Row {i}: empty link_id, skipped.")
            continue
        try:
            row = {
                "link_id": link_id,
                "site_a_lat": float(raw["site_a_lat"]),
                "site_a_lon": float(raw["site_a_lon"]),
                "site_a_height_m": float(raw["site_a_height_m"]),
                "site_b_lat": float(raw["site_b_lat"]),
                "site_b_lon": float(raw["site_b_lon"]),
                "site_b_height_m": float(raw["site_b_height_m"]),
                "frequency_ghz": float(raw["frequency_ghz"]),
            }
        except (TypeError, ValueError):
            errors.append(f"Row {i} ({link_id}): non-numeric coordinate, height, or frequency, skipped.")
            continue
        rows.append(row)
    return rows, errors


def analyze_links(
    rows: List[dict],
    k_factor: float = DEFAULT_K_FACTOR,
    n_samples: int = DEFAULT_SAMPLE_COUNT,
) -> List[LinkClearanceResult]:
    """Runs analyze_link() for every row, ranked by clearance_ratio
    ascending -- the lowest-margin (highest-risk) link first, which is the
    point of ranking by margin: a 65%-clear link and a 95%-clear link
    are both "clear" under a binary pass/fail, but the first has far less
    headroom before a minor change pushes it to marginal.
    """
    results = [
        analyze_link(
            link_id=row["link_id"],
            site_a_lat=row["site_a_lat"],
            site_a_lon=row["site_a_lon"],
            site_a_height_m=row["site_a_height_m"],
            site_b_lat=row["site_b_lat"],
            site_b_lon=row["site_b_lon"],
            site_b_height_m=row["site_b_height_m"],
            frequency_ghz=row["frequency_ghz"],
            k_factor=k_factor,
            n_samples=n_samples,
        )
        for row in rows
    ]
    results.sort(key=lambda r: r.clearance_ratio)
    return results


def results_to_csv(results: List[LinkClearanceResult]) -> str:
    """One CSV row per link: distance, Fresnel and clearance figures, ranking
    ratio, status, near_threshold flag, and a plain-language explanation --
    no internal Python objects."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "link_id",
            "distance_km",
            "first_fresnel_radius_m",
            "required_clearance_m",
            "terrain_clearance_m",
            "clearance_ratio",
            "los_status",
            "near_threshold",
            "obstruction_distance_km",
            "explanation",
        ]
    )
    for r in results:
        writer.writerow(
            [
                r.link_id,
                f"{r.distance_km:.3f}",
                f"{r.first_fresnel_radius_m:.2f}",
                f"{r.required_clearance_m:.2f}",
                f"{r.terrain_clearance_m:.2f}",
                f"{r.clearance_ratio:.3f}",
                r.los_status,
                r.near_threshold,
                "" if r.obstruction_distance_km is None else f"{r.obstruction_distance_km:.3f}",
                explain(r),
            ]
        )
    return output.getvalue()


def results_to_geojson(results: List[LinkClearanceResult]) -> dict:
    """Same results as results_to_csv(), as a GeoJSON FeatureCollection --
    one LineString feature per link (the actual sampled great-circle path,
    not just a straight 2-point line), with every computed field as a
    property, so this can be pulled directly into QGIS or another GIS tool
    without reformatting. No PyQGIS/plugin work here -- just a standard,
    valid GeoJSON document.
    """
    features = []
    for r in results:
        # GeoJSON coordinate order is [longitude, latitude], the opposite
        # of how this package writes coordinates everywhere else -- easy
        # to get backwards, called out explicitly here.
        coordinates = [[p.longitude, p.latitude] for p in r.profile]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {
                    "link_id": r.link_id,
                    "distance_km": r.distance_km,
                    "bearing_deg": r.bearing_deg,
                    "frequency_ghz": r.frequency_ghz,
                    "k_factor": r.k_factor,
                    "first_fresnel_radius_m": r.first_fresnel_radius_m,
                    "required_clearance_m": r.required_clearance_m,
                    "terrain_clearance_m": r.terrain_clearance_m,
                    "clearance_ratio": r.clearance_ratio,
                    "percent_fresnel_clear": r.percent_fresnel_clear,
                    "los_status": r.los_status,
                    "near_threshold": r.near_threshold,
                    "obstruction_distance_km": r.obstruction_distance_km,
                    "explanation": explain(r),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def results_to_geojson_str(results: List[LinkClearanceResult]) -> str:
    return json.dumps(results_to_geojson(results), indent=2)
