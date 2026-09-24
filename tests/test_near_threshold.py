from aei_link_clearance.terrain import ELEVATION_UNCERTAINTY_M, _is_near_threshold


def test_comfortably_clear_is_not_near_threshold():
    # Well above 60%, and the swing doesn't reach it.
    assert _is_near_threshold(percent_fresnel_clear=0.95, fresnel_radius_m=50.0) is False


def test_just_above_clear_boundary_is_near_threshold():
    # 0.62 with a big fresnel radius still isn't near, but a SMALL fresnel
    # radius makes the same 15m uncertainty a much bigger percent swing.
    small_radius_swing = ELEVATION_UNCERTAINTY_M / 5.0  # radius=5m -> swing=3.0 (300%)
    assert small_radius_swing > 0.02  # sanity: this swing easily reaches 0.60 from 0.62
    assert _is_near_threshold(percent_fresnel_clear=0.62, fresnel_radius_m=5.0) is True


def test_large_fresnel_radius_is_robust_to_uncertainty():
    # Comfortably clear (0.75) with a large Fresnel radius (long/low-freq
    # link): 15m is only a 0.03 swing here (15/500), nowhere near enough
    # to reach the 0.60 boundary -- not near threshold.
    swing = ELEVATION_UNCERTAINTY_M / 500.0
    assert 0.75 - swing > 0.60  # sanity: confirms this case shouldn't cross the boundary
    assert _is_near_threshold(percent_fresnel_clear=0.75, fresnel_radius_m=500.0) is False


def test_near_obstructed_boundary_also_flagged():
    assert _is_near_threshold(percent_fresnel_clear=0.31, fresnel_radius_m=10.0) is True


def test_deep_in_obstructed_band_is_not_near_threshold():
    assert _is_near_threshold(percent_fresnel_clear=-5.0, fresnel_radius_m=10.0) is False


def test_zero_fresnel_radius_is_never_near_threshold():
    # Avoid a division by zero; a degenerate case, not a real link geometry.
    assert _is_near_threshold(percent_fresnel_clear=0.5, fresnel_radius_m=0.0) is False
