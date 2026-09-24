from aei_link_clearance.explain import explain
from aei_link_clearance.terrain import LinkClearanceResult


def _result(**overrides) -> LinkClearanceResult:
    defaults = dict(
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
        profile=[],
    )
    defaults.update(overrides)
    return LinkClearanceResult(**defaults)


def test_near_threshold_overrides_everything_else():
    r = _result(los_status="clear", near_threshold=True)
    text = explain(r)
    assert "Near threshold" in text
    assert "survey" in text


def test_clear_with_limited_headroom():
    r = _result(los_status="clear", clearance_ratio=1.05, near_threshold=False)
    text = explain(r)
    assert "Clear" in text
    assert "limited headroom" in text
    assert "5%" in text


def test_clear_with_comfortable_margin():
    r = _result(los_status="clear", clearance_ratio=1.5, near_threshold=False)
    text = explain(r)
    assert "Clear" in text
    assert "comfortable margin" in text
    assert "50%" in text


def test_marginal_states_percent_below():
    r = _result(los_status="marginal", clearance_ratio=0.76, near_threshold=False)
    text = explain(r)
    assert "Marginal" in text
    assert "24%" in text  # (0.76 - 1) * 100 = -24


def test_obstructed_states_ground_height_and_location():
    r = _result(
        los_status="obstructed",
        clearance_ratio=-8.24,
        terrain_clearance_m=-62.24,
        obstruction_distance_km=4.43,
        near_threshold=False,
    )
    text = explain(r)
    assert "Obstructed" in text
    assert "62" in text
    assert "4.4" in text
