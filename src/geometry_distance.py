import math


def point_to_segment_distance(point, segment_start, segment_end):
    """Compute shortest Euclidean distance from a 2D point to a finite line segment.

    Args:
        point: 2D point as [x, y] or tuple (x, y)
        segment_start: Segment start as [x, y] or tuple (x, y)
        segment_end: Segment end as [x, y] or tuple (x, y)

    Returns:
        Float: shortest distance from point to segment
    """
    px, py = point[0], point[1]
    sx, sy = segment_start[0], segment_start[1]
    ex, ey = segment_end[0], segment_end[1]

    # Vector from segment_start to segment_end
    dx = ex - sx
    dy = ey - sy

    # Vector from segment_start to point
    px_rel = px - sx
    py_rel = py - sy

    # Squared length of segment
    segment_length_sq = dx * dx + dy * dy

    # Handle degenerate segment (zero length)
    if segment_length_sq == 0:
        return math.sqrt(px_rel * px_rel + py_rel * py_rel)

    # Parameter t for closest point on infinite line
    t = (px_rel * dx + py_rel * dy) / segment_length_sq

    # Clamp t to [0, 1] to stay within segment
    t = max(0.0, min(1.0, t))

    # Closest point on segment
    closest_x = sx + t * dx
    closest_y = sy + t * dy

    # Distance from point to closest point
    dist_x = px - closest_x
    dist_y = py - closest_y

    return math.sqrt(dist_x * dist_x + dist_y * dist_y)


def _on_segment(p, q, r):
    """Check whether point r lies on the segment pq (assumes collinear)."""
    return (min(p[0], q[0]) <= r[0] <= max(p[0], q[0]) and
            min(p[1], q[1]) <= r[1] <= max(p[1], q[1]))


def segments_intersect(p1, p2, p3, p4):
    """Return True if closed segment p1-p2 properly or partially overlaps segment p3-p4.

    Includes the collinear-overlap and endpoint-touching cases.
    """
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    d1 = cross(p3, p4, p1)
    d2 = cross(p3, p4, p2)
    d3 = cross(p1, p2, p3)
    d4 = cross(p1, p2, p4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True

    # Collinear / endpoint cases
    if d1 == 0 and _on_segment(p3, p4, p1):
        return True
    if d2 == 0 and _on_segment(p3, p4, p2):
        return True
    if d3 == 0 and _on_segment(p1, p2, p3):
        return True
    if d4 == 0 and _on_segment(p1, p2, p4):
        return True

    return False


def segment_to_segment_distance(s1_start, s1_end, s2_start, s2_end):
    """Compute shortest Euclidean distance between two 2D finite line segments.

    If the segments intersect (including touching at an endpoint or overlapping
    collinearly), the distance is 0.0. Otherwise returns the minimum of the
    distances from each endpoint of one segment to the other segment.

    Args:
        s1_start, s1_end: Endpoints of the first segment.
        s2_start, s2_end: Endpoints of the second segment.

    Returns:
        Float: shortest distance between the two segments.
    """
    p1, p2 = s1_start, s1_end
    p3, p4 = s2_start, s2_end

    if segments_intersect(p1, p2, p3, p4):
        return 0.0

    d1 = point_to_segment_distance(p1, p3, p4)
    d2 = point_to_segment_distance(p2, p3, p4)
    d3 = point_to_segment_distance(p3, p1, p2)
    d4 = point_to_segment_distance(p4, p1, p2)

    return min(d1, d2, d3, d4)