"""Geometry helper: foot of the perpendicular from a point to a line."""

def perpendicular_foot(point, line_start, line_end):
    """Compute the foot of the perpendicular from a point to a (2D) line.

    Given a point ``P`` and a line through two points ``A`` and ``B``, this
    function returns the point ``F`` on the (infinite) line through ``A`` and
    ``B`` such that the segment ``PF`` is perpendicular to ``AB``.

    Using vector notation with ``d = B - A`` and ``w = P - A``::

        F = A + t * d,   where   t = (w . d) / (d . d)

    Parameters
    ----------
    point : sequence of two numbers
        The point ``P`` from which the perpendicular is dropped.
    line_start : sequence of two numbers
        The first point ``A`` defining the line.
    line_end : sequence of two numbers
        The second point ``B`` defining the line.

    Returns
    -------
    tuple of two floats
        The foot of the perpendicular ``F = (fx, fy)``.

    Notes
    -----
    If ``line_start`` and ``line_end`` coincide, the line degenerates to a
    single point.  In that case there is no well-defined line, so the
    function returns ``line_start`` unchanged as the only sensible answer.
    """
    px = float(point[0])
    py = float(point[1])
    ax = float(line_start[0])
    ay = float(line_start[1])
    bx = float(line_end[0])
    by = float(line_end[1])

    dx = bx - ax
    dy = by - ay

    denom = dx * dx + dy * dy
    if denom == 0.0:
        # Degenerate "line" - both endpoints are the same point.
        return (ax, ay)

    t = ((px - ax) * dx + (py - ay) * dy) / denom

    return (ax + t * dx, ay + t * dy)


if __name__ == "__main__":  # pragma: no cover - manual sanity check
    # Quick smoke test when run directly.
    print(perpendicular_foot((3.0, 5.0), (0.0, 0.0), (1.0, 0.0)))  # -> (3.0, 0.0)