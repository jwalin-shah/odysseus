"""
Concentric ring m,n maxima collector.

Collects maximum values for concentric rings (defined by m, n parameters)
across various angle measurements.
"""


def missions_concentric_ring_mn_maxima_collector(rings, measurements=None):
    """
    Collect maximum values for each concentric ring at given angles.

    Parameters
    ----------
    rings : list
        List of ring definitions. Each ring may be represented as a tuple
        ``(m, n)`` or any identifier. The list length determines the
        number of rings, which are indexed ``0`` to ``len(rings) - 1``.
    measurements : dict, optional
        Nested dictionary mapping ``ring_idx`` to ``{angle: [values]}``.
        If ``None`` or empty, every ring is returned with an empty
        maximum-values list. Measurement data for ring indices not
        present in ``rings`` is ignored.

    Returns
    -------
    dict
        Mapping from each ring index to a list of maximum values
        (one maximum per angle that has non-empty data).
    """
    # Always include every defined ring in the result, even when
    # there is no measurement data for it.
    result = {i: [] for i in range(len(rings))}

    if not measurements:
        return result

    for ring_idx, angle_data in measurements.items():
        if ring_idx not in result:
            # Ignore measurements for rings that were not declared.
            continue
        if not isinstance(angle_data, dict):
            continue

        maxima = []
        for _angle, values in angle_data.items():
            if values:  # skip empty lists
                maxima.append(max(values))
        result[ring_idx] = maxima

    return result