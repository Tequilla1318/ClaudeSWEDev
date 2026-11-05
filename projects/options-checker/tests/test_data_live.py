"""Opt-in check against the real publishers: OCCHECK_LIVE=1 pytest tests/test_data_live.py."""

import os

import pytest

from occheck import data

pytestmark = pytest.mark.skipif(not os.environ.get("OCCHECK_LIVE"), reason="network test")


@pytest.mark.parametrize("kind,first", [("SPX", "1975"), ("VIX", "1990"), ("PUT", "1991"),
                                        ("BXM", "2002"), ("DTB3", "1954")])  # fmt: skip
def test_real_files_parse(tmp_path, kind, first):
    s = data.load_csv(data.download(kind, tmp_path).read_text())
    assert s.start.startswith(first) and len(s) > 4000
