"""Tests for the Python <-> C++ binding layer of the scaffold."""

import numpy as np
import pytest

import prob_orbit_prop as pop


def test_core_version_matches_package_version() -> None:
    assert pop.core_version() == pop.__version__ == "0.1.0"


def test_build_info_reports_cpp20() -> None:
    assert "C++ 2020" in pop.build_info()


def test_norm_matches_numpy() -> None:
    rng = np.random.default_rng(1)
    for v in rng.normal(scale=7e6, size=(100, 3)):
        assert pop.norm(v) == pytest.approx(np.linalg.norm(v), rel=1e-15)


def test_norm_accepts_lists_and_ints() -> None:
    assert pop.norm([3, 4, 12]) == 13.0


def test_cross_matches_numpy() -> None:
    rng = np.random.default_rng(2)
    a, b = rng.normal(size=(2, 50, 3))
    for ai, bi in zip(a, b, strict=True):
        np.testing.assert_allclose(pop.cross(ai, bi), np.cross(ai, bi), rtol=1e-14)


@pytest.mark.parametrize("bad", [[1.0, 2.0], [1.0, 2.0, 3.0, 4.0], [[1.0, 2.0, 3.0]]])
def test_wrong_shape_raises_value_error(bad: list) -> None:
    with pytest.raises(ValueError, match=r"shape \(3,\)"):
        pop.norm(bad)
