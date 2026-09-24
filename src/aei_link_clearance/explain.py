"""Plain-language explanation string per link result. A batch tool that
just prints "clear"/"obstructed" per row loses exactly the margin
information this package exists to surface.

All numbers used here are already computed on LinkClearanceResult; this
module only formats them into a sentence. No new thresholds are invented
except one wording judgment call (COMFORTABLE_MARGIN_RATIO), flagged as
such below -- it changes only which sentence is shown, never los_status or
near_threshold themselves.
"""
from __future__ import annotations

from .terrain import LinkClearanceResult

# Below this clearance_ratio, a "clear" link is described as having
# "limited headroom" rather than "comfortable margin." A wording judgment
# call, not a sourced threshold -- 1.3 means "at least 30% more margin
# than the bare 60%-of-Fresnel-zone minimum," picked as a round number,
# nothing more.
COMFORTABLE_MARGIN_RATIO = 1.3


def explain(result: LinkClearanceResult) -> str:
    """One sentence, plain language, for the batch results table."""
    if result.near_threshold:
        return (
            "Near threshold -- a ~10-15m elevation difference could change this "
            "result; verify with a survey before relying on it."
        )

    pct_vs_minimum = (result.clearance_ratio - 1) * 100  # +5 = 5% above minimum, -24 = 24% below

    if result.los_status == "clear":
        if result.clearance_ratio < COMFORTABLE_MARGIN_RATIO:
            return f"Clear, but only {pct_vs_minimum:.0f}% above minimum clearance -- limited headroom."
        return f"Clear, {pct_vs_minimum:.0f}% above minimum -- comfortable margin."

    if result.los_status == "marginal":
        return (
            f"Marginal -- {abs(pct_vs_minimum):.0f}% below standard microwave link clearance "
            f"practice (60% of the first Fresnel zone); some risk of degraded performance."
        )

    # obstructed
    where = f" (~{result.obstruction_distance_km:.1f} km from Site A)" if result.obstruction_distance_km is not None else ""
    return f"Obstructed -- ground is {abs(result.terrain_clearance_m):.0f} m above the line of sight{where}; link is unlikely to perform reliably as specified."
