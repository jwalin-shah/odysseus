def dept_inventory(records):
    """
    Aggregate inventory records by (department, item) pairs.

    Parameters
    ----------
    records : iterable
        An iterable of records, where each record is a tuple/list of
        (department, item, quantity).  Duplicates of the same
        (department, item) pair are summed.

    Returns
    -------
    dict
        A dictionary whose keys are ``(department, item)`` tuples and
        whose values are the summed numeric quantity for that pair.

    Edge cases
    ----------
    * ``None`` or an empty iterable -> ``{}``.
    * Records that are not tuple/list-like, or that have fewer than three
      elements, are silently skipped.
    * Non-numeric quantities (e.g. ``"five"``) that cannot be coerced are
      skipped, but numeric strings such as ``"5"`` are accepted.
    """
    result = {}

    if records is None:
        return result

    for record in records:
        if not isinstance(record, (tuple, list)) or len(record) < 3:
            continue

        dept, item, qty = record[0], record[1], record[2]

        if not isinstance(qty, (int, float)) or isinstance(qty, bool):
            try:
                qty = float(qty)
            except (TypeError, ValueError):
                continue

        key = (dept, item)
        result[key] = result.get(key, 0) + qty

    return result