def concentric_ring_mn_maxima_collector(matrix):
    """
    Collect the maxima of concentric rings in an m-by-n matrix.

    The matrix is decomposed into concentric "rings" where ring 0 is the
    outermost border, ring 1 is the next border inward, and so on, up to
    the innermost ring (the center cell, or the innermost square for
    even-sized matrices).

    Returns a list whose i-th element is the maximum value found in ring i
    (ordered from outermost to innermost). Returns an empty list for an
    empty or zero-width matrix.
    """
    if not matrix or not matrix[0]:
        return []

    m = len(matrix)
    n = len(matrix[0])

    # Number of concentric rings.
    # For a 1x1: 1 ring. 2x2: 1 ring. 3x3: 2 rings. 4x4: 2 rings. 5x5: 3 rings.
    num_rings = (min(m, n) + 1) // 2

    ring_maxes = [float("-inf")] * num_rings
    for i in range(m):
        for j in range(n):
            dist_top = i
            dist_bottom = m - 1 - i
            dist_left = j
            dist_right = n - 1 - j
            ring_idx = min(dist_top, dist_bottom, dist_left, dist_right)
            if matrix[i][j] > ring_maxes[ring_idx]:
                ring_maxes[ring_idx] = matrix[i][j]

    return ring_maxes