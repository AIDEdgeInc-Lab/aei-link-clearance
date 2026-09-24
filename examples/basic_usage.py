"""Runnable example: the three real coordinate pairs used in the README's
validation check, analyzed with analyze_link()
directly -- no CSV, no batch processing, just the core library.
"""
from aei_link_clearance import analyze_link

CASES = [
    ("CN-TOWER-SHORT", 43.6426, -79.3871, 30, 43.6532, -79.3832, 30, 5.8),
    ("ESCARPMENT-LOW", 43.29, -79.88, 15, 43.42, -79.88, 15, 5.8),
    ("ESCARPMENT-MED", 43.29, -79.88, 83, 43.42, -79.88, 83, 5.8),
]

for link_id, lat_a, lon_a, h_a, lat_b, lon_b, h_b, freq in CASES:
    result = analyze_link(
        link_id=link_id,
        site_a_lat=lat_a, site_a_lon=lon_a, site_a_height_m=h_a,
        site_b_lat=lat_b, site_b_lon=lon_b, site_b_height_m=h_b,
        frequency_ghz=freq,
    )
    print(f"{result.link_id}: {result.los_status}  "
          f"distance={result.distance_km:.2f}km  "
          f"clearance_ratio={result.clearance_ratio:.3f}  "
          f"obstruction_km={result.obstruction_distance_km}")
