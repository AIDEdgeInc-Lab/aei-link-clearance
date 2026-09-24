# Contributing

This is intentionally a small library. Most changes touch one module.

## Where things live

| You want to... | Edit... |
|---|---|
| Change the Fresnel-zone formula | `src/aei_link_clearance/fresnel.py` |
| Change bearing or great-circle sampling | `src/aei_link_clearance/geometry.py` |
| Change clearance thresholds, earth-bulge, or the per-link result | `src/aei_link_clearance/terrain.py` |
| Change the elevation source | `src/aei_link_clearance/elevation.py` |
| Change the plain-language explanation | `src/aei_link_clearance/explain.py` |
| Change batch CSV input/output or GeoJSON export | `src/aei_link_clearance/batch.py` |

Distance and coordinate validation come from
[`aei-geo-features`](https://github.com/AIDEdgeInc-Lab/aei-geo-features);
don't reimplement them here.

## Ground rules

- **No hidden calculations.** Expose the inputs and method behind any
  computed value; don't return a bare label without the numbers behind it.
- **State simplifications and judgment calls.** Thresholds that aren't from
  a standard must say so in a comment (see `OBSTRUCTED_THRESHOLD`).
- **Don't claim compliance** with a named standard the package doesn't
  actually implement.
- **Keep dependencies minimal.** New third-party packages belong behind an
  optional extra in `pyproject.toml`.

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

Tests must be deterministic and offline -- no live network calls in `tests/`.
