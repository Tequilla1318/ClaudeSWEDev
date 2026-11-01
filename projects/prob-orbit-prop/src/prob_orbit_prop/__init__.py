"""Probabilistic orbit propagation under EGM2008 gravity.

The numerics (force model, integrators, ensembles) live in the compiled C++
core, :mod:`prob_orbit_prop._core`; this package re-exports its public API and
will hold the Python-side sampling, metrics and plotting code.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from . import _core

__all__ = ["__version__", "build_info", "core_version", "cross", "norm"]

__version__ = "0.1.0"


def core_version() -> str:
    """Return the version string of the compiled C++ core."""
    return _core.version()


def build_info() -> str:
    """Return the compiler and C++ standard the core was built with."""
    return _core.build_info()


def norm(v: npt.ArrayLike) -> float:
    """Euclidean norm of a length-3 vector, computed in the C++ core.

    Args:
        v: Any array-like of shape ``(3,)``; converted to float64.

    Returns:
        The norm ``sqrt(x**2 + y**2 + z**2)``.

    Raises:
        ValueError: If ``v`` does not have shape ``(3,)``.
    """
    return _core.norm(np.asarray(v, dtype=np.float64))


def cross(a: npt.ArrayLike, b: npt.ArrayLike) -> np.ndarray:
    """Cross product ``a x b`` of two length-3 vectors, computed in the C++ core.

    Args:
        a: Array-like of shape ``(3,)``.
        b: Array-like of shape ``(3,)``.

    Returns:
        Array of shape ``(3,)`` with the right-handed cross product.

    Raises:
        ValueError: If either input does not have shape ``(3,)``.
    """
    return np.asarray(
        _core.cross(np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64))
    )
