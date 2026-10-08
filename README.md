# aei-link-clearance

[![PyPI version](https://img.shields.io/pypi/v/aei-link-clearance.svg)](https://pypi.org/project/aei-link-clearance/)
[![Python versions](https://img.shields.io/pypi/pyversions/aei-link-clearance.svg)](https://pypi.org/project/aei-link-clearance/)
[![License](https://img.shields.io/pypi/l/aei-link-clearance.svg)](https://github.com/AIDEdgeInc-Lab/aei-link-clearance/blob/main/LICENSE)
[![CI](https://github.com/AIDEdgeInc-Lab/aei-link-clearance/actions/workflows/ci.yml/badge.svg)](https://github.com/AIDEdgeInc-Lab/aei-link-clearance/actions/workflows/ci.yml)

Batch microwave link terrain-clearance and margin-based risk ranking. Built
on top of [`aei-geo-features`](https://github.com/AIDEdgeInc-Lab/aei-geo-features)
(distance, coordinate validation) via a real package dependency, not a
copy -- this package adds only what aei-geo-features deliberately excludes:
bearing/azimuth, elevation-profile sampling, Fresnel-zone geometry, and
earth-curvature-adjusted terrain clearance.

## What this is not

- Not "is this link clear right now" -- single-link planning checklists
  already exist (Pathloss, uptowhere.com). This batch-processes many
  candidate links and ranks them by clearance margin, surfacing
  low-margin links as elevated risk even when they're technically
  "clear" under a binary pass/fail.
- Not a predictor. No time-series or change-detection data exists in this
  version -- it does not forecast future obstruction.
- Not a claim of compliance with any named standard. Described here as
  "based on standard microwave link engineering practice," with sources
  below -- not "ITU-R P.530 compliant."
- Not a replacement for a site survey or professional link design.

## Methodology

**Fresnel zone radius** -- ITU-R P.526 diffraction theory, general form
`r_n = sqrt(n * lambda * d1 * d2 / (d1 + d2))`. This package uses the
practical engineering form (first zone, n=1, d in km, f in GHz, r in m):

    r1 = 17.3 * sqrt(d1 * d2 / (f * (d1 + d2)))

Cross-checked at the path midpoint against the well-known
`8.656 * sqrt(D/f)` constant (matches exactly) and against a live,
independent implementation (uptowhere.com's calculator) -- see the
validation check below.

**k-factor** -- 4/3, the ITU-R P.530 median/standard-atmosphere value for
temperate climates, exposed as a parameter (`k_factor=` on
`analyze_link()`), not hardcoded. Earth bulge: `h = d1*d2 / (2*k*R)`,
R = 6371 km (the same Earth-radius constant `aei_geo_features` uses).

**Clearance criterion** -- >=60% of the first Fresnel zone clear is
standard microwave link engineering practice (converging, consistent
citations across RF engineering references), not an ITU-R-numbered
compliance figure -- described as such throughout this package. Bands used
throughout: **clear** >=60%, **marginal** 30-60%,
**obstructed** <30%. The 30% marginal/obstructed split is a
judgement call, not independently sourced -- see the comment at
`terrain.OBSTRUCTED_THRESHOLD`.

**Elevation data** -- Open-Meteo Elevation API, backed by Copernicus DEM
GLO-90 (90 m resolution, global, free, batched, no API key). **This is a
Digital Surface Model, not a bare-earth DEM** -- it may already reflect
tree canopy or rooftop height in some areas. Treat results accordingly, and
verify against a survey before relying on them.

**Open-Meteo's free tier (used here) is licensed for non-commercial use only
(data: CC-BY 4.0, attribution required). Any commercial use of this feature
requires you to obtain your own paid Open-Meteo subscription
(https://open-meteo.com/en/pricing) -- this package does not include or
imply one.**

## Validation check (against uptowhere.com/line-of-sight-calculator)

Three real Southern Ontario coordinate pairs, all at 5.8 GHz (the closest
frequency both tools support), k=4/3 in both:

| Case | Path | This package | uptowhere.com | Agreement |
|---|---|---|---|---|
| 1: clear, urban, short | CN Tower area, 1.22 km, 30 m/30 m towers | clear, ratio 6.78, F1(midpoint) 3.97 m | clear, 100% F1 clear, F1(midpoint) 4.0 m | **Exact match** on distance, F1 formula, and verdict |
| 2: obstructed, escarpment | Niagara Escarment crossing, 14.46 km, 15 m/15 m towers | obstructed, ground 62.2 m above sightline at 4.43 km, F1 12.6 m / required 7.55 m | blocked, ground 76 m above sightline at 4.35 km, F1 13 m / required 7.5 m | Same verdict, F1/required nearly identical; obstruction **magnitude** differs by ~14 m |
| 3: marginal (this pkg) / blocked (theirs) | Same escarpment path, 83 m/83 m towers | marginal, ratio 0.76, clearance +5.8 m (LOS geometrically clear) | blocked, ground 7.6 m above sightline | **Verdict disagreement** -- same ~13-14 m gap as case 2, same location |

**Diagnosis**: distance, bearing and the first-Fresnel-zone formula agree
with the other tool (case 1's exact formula match; case 2's near-identical
F1/required figures; both tools agree on bearing and total distance).
Case 1 is too short (1.22 km, earth bulge about 0.04 m) to test the
earth-curvature term at all, and cases 2 and 3 were computed with releases
before 0.2.0, which applied the curvature in the wrong direction (see the
note below), so this table does not validate the curvature term. The
remaining ~13-14 m gap in cases 2/3, consistent in both magnitude and
location, was attributed to the **elevation data source**: this package uses
Copernicus DEM GLO-90 (90 m), uptowhere.com uses AWS Terrain Tiles (~30 m)
-- two different DEM products that commonly diverge by this much on steep,
sharp local relief like an escarpment edge. Doubling this package's sample
count (50 -> 100 points) changed the result by <1 m, not ~14 m, so the gap
is not an artifact of under-sampling. That attribution is no longer
complete: the wrong-direction curvature accounted for about 5 m of the gap
at the critical point (twice the bulge, 4.43 km from one end of a 14.46 km
path), and the remaining gap has not been re-measured with 0.2.0.

**Conclusion**: distance, bearing and the Fresnel-zone calculation agree with
an independent implementation, and from 0.2.0 the sign and size of the
earth-curvature term are checked against an independent straight-line
geometry (`tests/test_curvature_convention.py`). That check covers the
curvature term only; the table above has not been re-run with 0.2.0, and the
model as a whole has not been validated beyond what is stated here. The
elevation-data layer carries real uncertainty -- estimated at the order of
10-15 m at steep terrain features, from the comparison above before the
curvature correction, and not re-measured -- and the DEM is a surface model.
A real RF engineer should be aware of both before this is used for anything
beyond a demo -- exactly what the mandatory DSM disclaimer exists to
communicate, not boilerplate.

> **Note on the earth-curvature convention (0.2.0).** Releases before 0.2.0 applied the effective-earth bulge in the wrong direction (it
> added clearance instead of removing it). From 0.2.0 the bulge is added to the terrain (`terrain_adjusted = ground + bulge`), so clearance
> is lower by twice the bulge: approximately `D^2 / (4 * k * R)` at the middle of a path of `D` km (see `CHANGELOG.md`). The validation
> table above was produced before this correction and has not been re-derived.
> `aei_link_clearance.terrain.CLEARANCE_CONVENTION` names the convention in use.

## Install

```bash
pip install aei-link-clearance   # from PyPI (once published)
pip install -e .                 # core library, depends only on aei-geo-features
pip install -e ".[elevation]"    # + requests, for the Open-Meteo client (see the Open-Meteo licensing notice above)
pip install -e ".[dev]"          # + pytest
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
