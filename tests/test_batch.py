import pytest

from aei_link_clearance.batch import REQUIRED_COLUMNS, parse_links_csv

VALID_CSV = """link_id,site_a_lat,site_a_lon,site_a_height_m,site_b_lat,site_b_lon,site_b_height_m,frequency_ghz
L1,43.6426,-79.3871,30,43.6532,-79.3832,30,7.0
L2,44.0592,-79.4613,40,44.3894,-79.6903,40,11.0
"""


def test_valid_csv_parses_all_rows():
    rows, errors = parse_links_csv(VALID_CSV)
    assert len(rows) == 2
    assert errors == []
    assert rows[0]["link_id"] == "L1"
    assert rows[0]["frequency_ghz"] == 7.0


def test_empty_file_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_links_csv("")


def test_missing_column_raises():
    header = ",".join(c for c in REQUIRED_COLUMNS if c != "frequency_ghz")
    with pytest.raises(ValueError, match="frequency_ghz"):
        parse_links_csv(header + "\nL1,43.6,-79.3,30,43.7,-79.4,30\n")


def test_empty_link_id_is_skipped_and_reported():
    csv_text = VALID_CSV + ",43.1,-79.1,10,43.2,-79.2,10,7.0\n"
    rows, errors = parse_links_csv(csv_text)
    assert len(rows) == 2
    assert len(errors) == 1
    assert "empty link_id" in errors[0]


def test_non_numeric_value_is_skipped_and_reported():
    csv_text = VALID_CSV + "L3,not-a-number,-79.1,10,43.2,-79.2,10,7.0\n"
    rows, errors = parse_links_csv(csv_text)
    assert len(rows) == 2
    assert len(errors) == 1
    assert "L3" in errors[0]
