"""Distance utilities for points and line segments."""

import math


def euclidean(p1, p2):
    """Compute the Euclidean distance between two points.

    Parameters
    ----------
    p1, p2 : sequence of numbers
        Points with the same dimensionality.

    Returns
    -------
    float
        The Euclidean distance between ``p1`` and ``p2``.

    Raises
    ------
    ValueError
        If the points do not share the same dimension.
    """
    if len(p1) != len(p2):
        raise ValueError(
            "Points must have the same dimension: "
            f"{len(p1)} vs {len(p2)}"
        )
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))


def point_to_segment(p, a, b):
    """Compute the distance from point ``p`` to the line segment ``ab``.

    The closest point on the segment is found by projecting ``p`` onto the
    infinite line through ``a`` and ``b`` and clamping the projection
    parameter to ``[0, 1]`` so that the result always lies on the segment
    (not its extension).

    Parameters
    ----------
    p : sequence of numbers
        The point.
    a, b : sequence of numbers
        The endpoints of the segment.

    Returns
    -------
    float
        The minimum Euclidean distance from ``p`` to any point on the
        segment ``ab``.

    Raises
    ------
    ValueError
        If the point and segment endpoints do not share the same dimension.
    """
    if len(p) != len(a) or len(p) != len(b):
        raise ValueError(
            "Point and segment endpoints must have the same dimension: "
            f"p={len(p)}, a={len(a)}, b={len(b)}"
        )

    dim = len(p)

    # Vector from a to b
    ab = [b[i] - a[i] for i in range(dim)]
    # Vector from a to p
    ap = [p[i] - a[i] for i in range(dim)]

    ab_sq = sum(c * c for c in ab)

    # Degenerate case: segment is a single point.
    if ab_sq == 0.0:
        return math.sqrt(sum(c * c for c in ap))

    # Project p onto the line; clamp t to [0, 1] to stay on the segment.
    t = sum(ap[i] * ab[i] for i in range(dim)) / ab_sq
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0

    # Closest point on the segment.
    closest = [a[i] + t * ab[i] for i in range(dim)]

    return math.sqrt(sum((p[i] - closest[i]) ** 2 for i in range(dim)))
