"""Security baseline (Phase 4): non-finite input refused, spreadsheet-formula guard on text cells, malformed service responses refused.

Every test here would have passed silently-wrong output, or crashed with an unrelated error, on 0.3.0.
"""
import math

import numpy as np
import pytest

from aei_link_clearance import analyze_link
from aei_link_clearance import elevation as elevation_mod
from aei_link_clearance.batch import csv_text_cell, parse_links_csv, results_to_csv
from aei_link_clearance.elevation import ElevationDataError
from aei_link_clearance.terrain import earth_bulge_m

HEADER = "link_id,site_a_lat,site_a_lon,site_a_height_m,site_b_lat,site_b_lon,site_b_height_m,frequency_ghz\n"


class FlatProvider:
    source = "test flat 100 m"

    def __init__(self):
        self.calls = 0

    def get_elevations(self, points):
        self.calls += 1
        return [100.0] * len(points)


def _link(**overrides):
    args = dict(link_id="L1", site_a_lat=43.6, site_a_lon=-79.4, site_a_height_m=30.0, site_b_lat=43.7, site_b_lon=-79.3,
                site_b_height_m=30.0, frequency_ghz=7.0)
    args.update(overrides)
    return args


# --- non-finite and wrongly typed numeric input -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("field", ["site_a_height_m", "site_b_height_m", "frequency_ghz", "k_factor"])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_analyze_link_refuses_non_finite_before_any_request(field, bad):
    provider = FlatProvider()
    with pytest.raises(ValueError, match=field):
        analyze_link(**_link(**{field: bad}), elevation_provider=provider)
    assert provider.calls == 0  # refused before the elevation service is touched


@pytest.mark.parametrize("bad", [2.5, "50", None, True])
def test_analyze_link_refuses_non_integer_sample_count(bad):
    with pytest.raises(ValueError, match="n_samples"):
        analyze_link(**_link(), n_samples=bad, elevation_provider=FlatProvider())


def test_numpy_numbers_are_still_accepted():
    result = analyze_link(**_link(site_a_height_m=np.float32(30.0), frequency_ghz=np.float64(7.0)), n_samples=np.int64(10),
                          elevation_provider=FlatProvider())
    assert math.isfinite(result.clearance_ratio)


def test_earth_bulge_refuses_nan_k_factor_and_keeps_positive_message():
    with pytest.raises(ValueError, match="finite"):
        earth_bulge_m(1.0, 1.0, k_factor=math.nan)
    with pytest.raises(ValueError, match="must be positive"):
        earth_bulge_m(1.0, 1.0, k_factor=0)


@pytest.mark.parametrize("token", ["nan", "NaN", "inf", "-inf", "Infinity"])
def test_batch_reports_non_finite_rows_instead_of_accepting_them(token):
    text = HEADER + "OK,43.6,-79.4,30,43.7,-79.3,30,7\n" + f"BAD,43.6,-79.4,30,43.7,-79.3,30,{token}\n"
    rows, errors = parse_links_csv(text)
    assert [r["link_id"] for r in rows] == ["OK"]
    assert len(errors) == 1
    assert errors[0].startswith("Row 3 (BAD): not a finite number: frequency_ghz")  # format consumers parse: "Row N (id)"


# --- spreadsheet-formula guard -------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("=HYPERLINK(\"http://x\",\"y\")", "'=HYPERLINK(\"http://x\",\"y\")"),
    ("+1+1", "'+1+1"),
    ("-cmd", "'-cmd"),
    ("@SUM(A1)", "'@SUM(A1)"),
    (" \t=1+1", "' \t=1+1"),
    ("-3.5", "-3.5"),             # a plain number is not a formula
    ("-210.00 m", "-210.00 m"),   # "number unit" text is left alone
    ("LINK-42", "LINK-42"),
    ("", ""),
])
def test_csv_text_cell(text, expected):
    assert csv_text_cell(text) == expected


def test_results_csv_guards_link_id_only():
    rows, _ = parse_links_csv(HEADER + "=1+2,43.6,-79.4,30,43.7,-79.3,30,7\nplain,43.6,-79.4,30,43.7,-79.3,30,7\n")
    from aei_link_clearance.batch import analyze_link as batch_analyze  # same function the batch uses
    results = [batch_analyze(**r, elevation_provider=FlatProvider()) for r in rows]
    out = results_to_csv(results).splitlines()
    assert out[1].startswith("'=1+2,")
    assert out[2].startswith("plain,")


# --- malformed service responses -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("payload", [[1, 2, 3], "oops", None, {"elevation": "100"}, {"elevation": {"a": 1}}])
def test_elevation_client_refuses_malformed_json(monkeypatch, payload):
    monkeypatch.setattr(elevation_mod, "_get_json", lambda *a, **k: payload)
    with pytest.raises(ElevationDataError):
        elevation_mod.get_elevations([(43.6, -79.4), (43.7, -79.3)])


def test_elevation_client_still_refuses_null_heights(monkeypatch):
    monkeypatch.setattr(elevation_mod, "_get_json", lambda *a, **k: {"elevation": [100.0, None]})
    with pytest.raises(ElevationDataError, match="never treated as 0 m"):
        elevation_mod.get_elevations([(43.6, -79.4), (43.7, -79.3)])
