"""get_elevations() validates what the elevation service returns; a missing elevation is never treated as 0 m."""
import pytest
import requests

from aei_link_clearance.elevation import ElevationDataError, get_elevations


class _Resp:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.exceptions.HTTPError("HTTP %d" % self.status)

    def json(self):
        return self.body


def _patch(monkeypatch, body, status=200):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(body, status))


PTS = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]


def test_valid_response(monkeypatch):
    _patch(monkeypatch, {"elevation": [10, 20.5, 30]})
    assert get_elevations(PTS) == [10.0, 20.5, 30.0]


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), "12", True])
def test_missing_or_non_numeric_elevation_is_refused(monkeypatch, bad):
    _patch(monkeypatch, {"elevation": [10, bad, 30]})
    with pytest.raises(ElevationDataError, match="never treated as 0 m"):
        get_elevations(PTS)


def test_wrong_count_is_refused(monkeypatch):
    _patch(monkeypatch, {"elevation": [10, 20]})
    with pytest.raises(ElevationDataError, match="refusing to guess"):
        get_elevations(PTS)


def test_http_error_is_not_swallowed(monkeypatch):
    _patch(monkeypatch, {}, status=503)
    with pytest.raises(requests.exceptions.HTTPError):
        get_elevations(PTS)


def test_elevation_data_error_is_still_a_value_error():
    assert issubclass(ElevationDataError, ValueError)             # callers that catch the earlier ValueError keep working
