# Security Policy

## Supported versions

This project is published on PyPI (https://pypi.org/project/aei-link-clearance/).
Only the latest published version and the latest commit on `main` are
supported.

| Version | Supported |
|---|---|
| 0.3.x | Yes, best-effort |
| < 0.3.0 | No |

## Reporting a vulnerability

**Please do not open a public GitHub issue for a suspected security
vulnerability.**

Report vulnerabilities privately using GitHub's private vulnerability
reporting (Security tab -> "Report a vulnerability") on the repository,
which opens a private advisory visible only to maintainers. If that
channel is unavailable, contact the maintainers through a private channel
and avoid including exploit details in any public forum.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce, or a minimal proof of concept
- The affected version(s)

## What to expect

- We will acknowledge receipt as soon as reasonably possible.
- We do not commit to a specific response-time or fix-time service level
  agreement (SLA). This is a small, community-maintained-scale project,
  not a commercially supported product.
- We will credit reporters who wish to be credited, once a fix is
  released.

## Scope

## Scope

What this library does that has a security boundary, and the controls that exist for it. Each control is covered by tests; the test
file is named.

| Boundary | Control | Where | Tests |
|---|---|---|---|
| Network: Open-Meteo Elevation API (HTTPS, keyless) | Fixed HTTPS endpoint; timeout on every request; at most 100 points per request; bounded retry with `Retry-After` cap and a cool-down after rate limiting; a daily quota is never retried | `elevation.py`, `providers.py` | `test_providers.py`, `test_elevation_data.py` |
| Network responses | A response that is not a JSON object, an `elevation` field that is not a list, a wrong count, or a null/NaN/non-numeric height is refused (`ElevationDataError`); a missing height is never treated as 0 m | `elevation.py`, `providers.validate_elevations` | `test_elevation_data.py`, `test_security_baseline.py` |
| Caller input (`analyze_link`) | Coordinates validated by `aei_geo_features.validate_coordinate`; heights, frequency and k-factor must be finite numbers; `n_samples` must be an integer of at least 2. Refused before any request is made | `terrain.py` | `test_terrain.py`, `test_security_baseline.py` |
| Batch CSV input | Missing columns and empty files refused; rows with non-numeric or non-finite (`nan`, `inf`) values are reported and skipped, never analysed | `batch.parse_links_csv` | `test_batch.py`, `test_security_baseline.py` |
| CSV output opened in a spreadsheet | `link_id` (the only caller-supplied text cell) is written so a spreadsheet cannot evaluate it as a formula; same rule as aei-workflow-runner and the Velorona Web Map | `batch.csv_text_cell` | `test_security_baseline.py` |
| Local DEM | A raster point outside coverage, on nodata, or a raster in the wrong CRS is refused; nothing is substituted | `providers.LocalDEMProvider` | `test_providers.py` |

Privacy: an online elevation lookup sends the sampled path coordinates to Open-Meteo. When coordinates must not leave the machine,
use `LocalDEMProvider` with a raster you hold; no request is then made.

Not in scope: the library stores no credentials, reads no environment variables, writes no files and runs no code from its inputs.
Open-Meteo's free tier is for non-commercial use only; commercial use needs the caller's own subscription.
