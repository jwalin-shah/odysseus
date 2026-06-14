"""Cumulative sum of pairwise Euclidean distances between missions.

The public entry point is :func:`missions_pairwise_distance_cumulative_summer`.
Given an iterable of missions (each carrying an ``(x, y)`` position) it returns
the sum of the Euclidean distances over all ``N * (N - 1) / 2`` unique pairs.
The result is a single non-negative ``float`` that is invariant with respect to
the input order.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, List, Tuple

# A "mission" can be expressed in any of the common coordinate-bearing shapes.
Mission = Any

__all__ = ["missions_pairwise_distance_cumulative_summer"]


def _extract_coordinates(mission: Mission) -> Tuple[float, float]:
    """Return the ``(x, y)`` pair encoded in *mission*.

    Supported encodings:

    * ``dict`` with numeric ``"x"`` and ``"y"`` keys,
    * any object that exposes numeric ``.x`` and ``.y`` attributes,
    * a ``tuple``/``list`` of at least two numeric elements.
    """
    if isinstance(mission, dict):
        try:
            return float(mission["x"]), float(mission["y"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TypeError(
                "Mission dict must contain numeric 'x' and 'y' keys, "
                "got: {!r}".format(mission)
            ) from exc

    # Use ``hasattr`` to detect arbitrary objects with .x/.y attributes
    # (covers namedtuples, dataclasses, simple custom classes, ...).
    if hasattr(mission, "x") and hasattr(mission, "y"):
        try:
            return float(mission.x), float(mission.y)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "Mission .x and .y must be numeric, got: {!r}".format(mission)
            ) from exc

    if isinstance(mission, (list, tuple)) and len(mission) >= 2:
        try:
            return float(mission[0]), float(mission[1])
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "Mission sequence must have numeric coordinates, "
                "got: {!r}".format(mission)
            ) from exc

    raise TypeError(
        "Unsupported mission format: {}. Expected a tuple/list (x, y), a "
        "dict with 'x'/'y' keys, or an object with .x/.y attributes.".format(
            type(mission).__name__
        )
    )


def missions_pairwise_distance_cumulative_summer(
    missions: Iterable[Mission],
) -> float:
    """Return the sum of Euclidean distances over all unique mission pairs.

    Parameters
    ----------
    missions:
        Iterable of missions.  Each mission may be supplied as a ``(x, y)``
        tuple/list, a ``dict`` with ``"x"`` and ``"y"`` keys, or any object
        that exposes numeric ``.x`` and ``.y`` attributes.

    Returns
    -------
    float
        Cumulative Euclidean distance across every unordered pair of missions.
        Returns ``0.0`` for ``None``, an empty container, or fewer than two
        missions.

    Raises
    ------
    TypeError
        If a mission cannot be interpreted as a pair of numeric coordinates.

    Examples
    --------
    >>> missions_pairwise_distance_cumulative_summer([(0, 0), (3, 4)])
    5.0
    >>> missions_pairwise_distance_cumulative_summer([(0, 0), (1, 0), (3, 0)])
    6.0
    >>> missions_pairwise_distance_cumulative_summer([])
    0.0
    """
    if missions is None:
        return 0.0

    coords: List[Tuple[float, float]] = []
    for mission in missions:
        coords.append(_extract_coordinates(mission))

    n = len(coords)
    if n < 2:
        return 0.0

    total = 0.0
    for i in range(n):
        x1, y1 = coords[i]
        for j in range(i + 1, n):
            x2, y2 = coords[j]
            # ``math.hypot`` is numerically robust and reads cleanly.
            total += math.hypot(x1 - x2, y1 - y2)

    return total


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    sample = [(0, 0), (3, 4), (6, 8), (0, 0)]
    print(missions_pairwise_distance_cumulative_summer(sample))