"""Geometry task: distance from a point to a line segment.

This module exposes a single function, :func:`point_to_segment_distance`,
which computes the shortest Euclidean distance from a query point to a
line segment defined by two endpoints.  It works for 2D and 3D points.

The implementation uses the standard "clamped projection" technique:
the query point is projected onto the infinite line through the segment
endpoints, the resulting parameter ``t`` is clamped to ``[0, 1]`` so that
the projection stays on the segment, and the Euclidean distance from the
query point to that clamped projection is returned.
"""

from __future__ import annotations

import math
from typing import Sequence


def point_to_segment_distance(
    point: Sequence[float],
    segment_start: Sequence[float],
    segment_end: Sequence[float],
) -> float:
    """Return the shortest distance from ``point`` to the segment ``[start, end]``.

    Parameters
    ----------
    point:
        The query point.  Must be a 2- or 3-element sequence of numbers.
    segment_start:
        The first endpoint of the segment.  Same dimensionality as ``point``.
    segment_end:
        The second endpoint of the segment.  Same dimensionality as ``point``.

    Returns
    -------
    float
        The non-negative Euclidean distance from ``point`` to the closest
        point on the segment.  Returns ``0.0`` when the query point lies on
        the segment (including at either endpoint).

    Raises
    ------
    ValueError
        If the inputs do not all share the same dimensionality, or if the
        dimensionality is anything other than 2 or 3.
    """
    p = [float(c) for c in point]
    a = [float(c) for c in segment_start]
    b = [float(c) for c in segment_end]

    dim = len(p)
    if dim != len(a) or dim != len(b):
        raise ValueError(
            "Point and segment endpoints must all have the same dimension"
        )
    if dim not in (2, 3):
        raise ValueError(
            "Only 2D and 3D points are supported, got dimension {}".format(dim)
        )

    # Vector from start to end of the segment, and its squared length.
    ab = [b[i] - a[i] for i in range(dim)]
    ab_sq = sum(c * c for c in ab)

    # Degenerate segment (start == end): the closest point is the vertex itself.
    if ab_sq < 1e-15:
        return math.sqrt(sum((p[i] - a[i]) ** 2 for i in range(dim)))

    # Projection parameter t = (AP . AB) / |AB|^2, clamped to [0, 1].
    t = sum((p[i] - a[i]) * ab[i] for i in range(dim)) / ab_sq
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0

    # Distance from ``point`` to the closest point on the segment, which is
    # A + t * (B - A).  Expanded algebraically to avoid an intermediate list.
    return math.sqrt(
        sum((p[i] - a[i] - t * ab[i]) ** 2 for i in range(dim))
    )


__all__ = ["point_to_segment_distance"]