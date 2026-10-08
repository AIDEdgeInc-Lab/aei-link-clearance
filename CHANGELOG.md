# Changelog

All notable changes to this project are recorded here.

## [0.2.1] - 2026-10-08

### Changed

- README now carries the standard PyPI / Python / License / CI badge row, and the PyPI project links point Homepage to
  https://aidedgeinc.com/tools/ with a Source link to this repository. No code, API, dependency or result change: analysis results are
  identical to 0.2.0.

## [0.2.0] - 2026-10-08

### Changed -- clearance results are different (please re-run saved analyses)

- **Earth curvature is now applied in the correct direction.** Previously the effective-earth bulge was subtracted from the terrain
  elevation, which *added* clearance; it is now added to the terrain, i.e. subtracted from the geometric clearance
  (`terrain_adjusted = ground + bulge`). Clearance values from 0.1.0 were therefore too high.
- **Size of the change.** At a point `d1` km from one end and `d2` km from the other the change is `2 * d1 * d2 / (2 * k * R)` metres
  (twice the bulge). At the middle of a path of `D` km that is approximately `D^2 / (4 * k * R)` metres lower than 0.1.0 (k = 4/3,
  R = 6371 km): about 1 m at 6 km, 5 m at 13 km, 15 m at 23 km, 43 m at 38 km and 294 m at 100 km. Short paths barely change; long paths can
  change class (`clear` / `marginal` / `obstructed`). The endpoints are unchanged. Example: flat ground, 30 m masts at both ends, 38.1 km,
  6.35 GHz: tightest clearance 8.6 m (0.1.0: 51.4 m).
- `ProfilePoint.terrain_adjusted_m` is now `ground_elevation_m + earth_bulge_m` (it was `ground_elevation_m - earth_bulge_m`).
  `clearance_m`, `terrain_clearance_m`, `percent_fresnel_clear`, `los_status`, `near_threshold`, the explanation text and the batch/GeoJSON
  output follow from it.
- This release corrects the sign of the curvature term only. The Fresnel formula, the k = 4/3 default, the 60 % / 30 % limits, the
  elevation sampling and the elevation source are unchanged, and this release does not validate the propagation model as a whole.
  The sign was checked against an independent straight-line geometry on an effective-radius earth (agreement within 0.02 m on paths of
  10, 38.1, 100 and 203 km); see `tests/test_curvature_convention.py`.

### Added

- `aei_link_clearance.terrain.CLEARANCE_CONVENTION` (`"bulge-added-to-terrain"`), so a program that depends on this package can detect the
  convention in use. Releases before 0.2.0 do not define it.
- `aei_link_clearance.elevation.ElevationDataError` (a subclass of `ValueError`).

### Fixed

- `get_elevations()` now raises `ElevationDataError` if the elevation service returns a missing, `null`, NaN, infinite or non-numeric value,
  instead of passing it on. The existing wrong-number-of-values error is now also an `ElevationDataError`; code that catches `ValueError`
  is unaffected.

## [0.1.0] - 2026-09-24

Initial standalone release: Fresnel-zone geometry, earth-curvature-adjusted
terrain clearance, margin-based ranking, plain-language explanations, batch
CSV processing and GeoJSON export.
