"""Free-data loaders, on small synthetic files in each publisher's format."""

import io
import os
import time

import numpy as np
import pytest

from occheck import data, site

SPX = "DATE,SPX\n01/03/2000,1455.22\n01/04/2000,1399.42\n01/05/2000,1402.11\n01/06/2000,1403.45\n"
VIX = (
    "DATE,OPEN,HIGH,LOW,CLOSE\n"
    "01/03/2000,24.36,26.15,23.98,24.21\n01/05/2000,25.00,26.00,24.00,25.50\n"
)
PUT = "DATE,PUT\n01/03/2000,250.00\n01/04/2000,249.10\n"
DTB3 = "observation_date,DTB3\n2000-01-03,5.27\n2000-01-04,.\n2000-01-05,5.30\n"


@pytest.mark.parametrize(
    "text,kind", [(SPX, "SPX"), (VIX, "VIX"), (PUT, "PUT"), (DTB3, "DTB3"), ("DATE,BXM\n", "BXM")]
)
def test_detect_kind(text, kind):
    assert data.detect_kind(text) == kind


def test_load_cboe_and_vix_close():
    spx = data.load_csv(SPX)
    assert spx.kind == "SPX" and len(spx) == 4 and spx.start == "2000-01-03"
    assert spx.values[1] == pytest.approx(1399.42)
    vix = data.load_csv(VIX)
    assert vix.values.tolist() == [24.21, 25.50]  # CLOSE column


def test_fred_missing_values_dropped():
    s = data.load_csv(DTB3)
    assert [str(d) for d in s.dates] == ["2000-01-03", "2000-01-05"]


def test_unsorted_and_duplicate_rows():
    s = data.load_csv("DATE,SPX\n01/05/2000,3\n01/03/2000,1\n01/05/2000,4\n")
    assert s.values.tolist() == [1.0, 4.0]


def test_align_forward_fills_other_series():
    dates, (spx, vix, tb) = data.align(data.load_csv(SPX), data.load_csv(VIX), data.load_csv(DTB3))
    assert [str(d) for d in dates] == ["2000-01-03", "2000-01-04", "2000-01-05", "2000-01-06"]
    assert vix.tolist() == [24.21, 24.21, 25.50, 25.50]
    assert tb.tolist() == [5.27, 5.27, 5.30, 5.30]
    assert spx.dtype == np.float64


def test_align_drops_dates_before_other_starts():
    late_vix = "DATE,OPEN,HIGH,LOW,CLOSE\n01/05/2000,1,1,1,20\n"
    dates, _ = data.align(data.load_csv(SPX), data.load_csv(late_vix))
    assert str(dates[0]) == "2000-01-05"


def test_bad_files():
    with pytest.raises(data.DataFormatError, match="expected one of"):
        data.load_csv("Symbol,Quantity\nX,1\n")
    with pytest.raises(data.DataFormatError, match="no data rows"):
        data.load_csv("DATE,SPX\n")


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_download_and_cache(tmp_path, monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        return _Resp(SPX.encode())

    monkeypatch.setattr(data.urllib.request, "urlopen", fake_urlopen)
    path = data.download("SPX", tmp_path)
    assert path.read_text() == SPX and calls == [data.SOURCES["SPX"]["url"]]
    assert site.local_data_file("SPX", directory=tmp_path) == path
    assert len(calls) == 1  # fresh cache: no second download
    old = time.time() - 48 * 3600
    os.utime(path, (old, old))
    site.local_data_file("SPX", directory=tmp_path)
    assert len(calls) == 2  # stale: refreshed
    with pytest.raises(ValueError):
        data.download("NOPE", tmp_path)


def test_download_refuses_unparseable(tmp_path, monkeypatch):
    monkeypatch.setattr(
        data.urllib.request, "urlopen", lambda req, timeout: _Resp(b"<html>blocked</html>")
    )
    with pytest.raises(data.DataFormatError):
        data.download("VIX", tmp_path)
    assert not (tmp_path / "VIX.csv").exists()
