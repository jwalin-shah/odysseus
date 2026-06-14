"""Compute the shortest Euclidean distance from a point to a line segment.

The implementation works for any dimension (2D, 3D, or higher) and
correctly handles edge cases such as the point lying on the segment,
the point coinciding with an endpoint, and a degenerate (zero-length)
segment.
"""

import math


def point_to_segment_distance(point, seg_start, seg_end):
    """Return the Euclidean distance from ``point`` to the segment
    defined by ``seg_start`` and ``seg_end``.

    Parameters
    ----------
    point : sequence of numbers
        The query point. Each coordinate may be an ``int`` or ``float``.
    seg_start : sequence of numbers
        The first endpoint of the segment. Must have the same
        dimensionality as ``point`` and ``seg_end``.
    seg_end : sequence of numbers
        The second endpoint of the segment. Must have the same
        dimensionality as ``point`` and ``seg_start``.

    Returns
    -------
    float
        The shortest Euclidean distance from ``point`` to the segment.
        If the segment is degenerate (``seg_start == seg_end``) the
        distance to that single point is returned.

    Raises
    ------
    ValueError
        If the inputs do not all share the same dimensionality, or if
        the inputs are empty.
    """
    p = tuple(float(c) for c in point)
    a = tuple(float(c) for c in seg_start)
    b = tuple(float(c) for c in seg_end)

    if not p or not a or not b:
        raise ValueError("point, seg_start, and seg_end must be non-empty")

    if len(p) != len(a) or len(p) != len(b):
        raise ValueError(
            "point, seg_start, and seg_end must all have the same dimension"
        )

    # Vector from A to B
    ab = tuple(bi - ai for ai, bi in zip(a, b))
    # Vector from A to P
    ap = tuple(pi - ai for pi, ai in zip(p, a))

    ab_len_sq = sum(c * c for c in ab)

    if ab_len_sq == 0.0:
        # Degenerate segment: A == B. Distance is simply |AP|.
        return math.sqrt(sum(c * c for c in ap))

    # Parameter t of the projection of AP onto AB. The closest point on
    # the *infinite* line is A + t * (B - A). t in [0, 1] means that
    # point lies inside the segment; otherwise the closest endpoint is
    # used instead.
    t = sum(ai * bi for ai, bi in zip(ap, ab)) / ab_len_sq

    if t < 0.0:
        closest = a
    elif t > 1.0:
        closest = b
    else:
        closest = tuple(ai + t * bi for ai, bi in zip(a, ab))

    diff = tuple(pi - ci for pi, ci in zip(p, closest))
    return math.sqrt(sum(c * c for c in diff))