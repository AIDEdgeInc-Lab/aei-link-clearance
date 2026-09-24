import json

from aei_link_clearance.batch import results_to_geojson, results_to_geojson_str
from aei_link_clearance.terrain import LinkClearanceResult, ProfilePoint


def _profile_point(lat, lon):
    return ProfilePoint(
        distance_from_a_km=0.0,
        latitude=lat,
        longitude=lon,
        ground_elevation_m=100.0,
        earth_bulge_m=0.0,
        terrain_adjusted_m=100.0,
        los_height_m=110.0,
        fresnel_radius_m=10.0,
        clearance_m=10.0,
        percent_fresnel_clear=1.0,
    )


def _result():
    return LinkClearanceResult(
        link_id="L1",
        distance_km=10.0,
        bearing_deg=45.0,
        frequency_ghz=7.0,
        k_factor=4 / 3,
        first_fresnel_radius_m=10.0,
        required_clearance_m=6.0,
        terrain_clearance_m=6.3,
        clearance_ratio=1.05,
        los_status="clear",
        obstruction_distance_km=None,
        percent_fresnel_clear=0.63,
        near_threshold=False,
        profile=[_profile_point(43.6, -79.4), _profile_point(43.7, -79.3)],
    )


def test_geojson_is_a_valid_feature_collection():
    fc = results_to_geojson([_result()])
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    feature = fc["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "LineString"


def test_geojson_coordinates_are_lon_lat_order():
    fc = results_to_geojson([_result()])
    coords = fc["features"][0]["geometry"]["coordinates"]
    # ProfilePoint 1 is (lat=43.6, lon=-79.4) -> GeoJSON [lon, lat] = [-79.4, 43.6]
    assert coords[0] == [-79.4, 43.6]


def test_geojson_properties_include_computed_fields():
    fc = results_to_geojson([_result()])
    props = fc["features"][0]["properties"]
    for key in ["link_id", "clearance_ratio", "los_status", "near_threshold", "explanation"]:
        assert key in props


def test_geojson_string_round_trips_through_json_parser():
    text = results_to_geojson_str([_result()])
    parsed = json.loads(text)  # would raise if the output weren't valid JSON
    assert parsed["type"] == "FeatureCollection"
