"""
recursive_nested_list_deep_product.py
=====================================

Compute the *deep product* of a (potentially nested) list of numbers.

A "deep product" multiplies every numeric value found anywhere inside an
arbitrarily nested list/tuple structure.  Empty (sub-)lists contribute a
factor of 1 (the multiplicative identity).  Non-numeric, non-iterable
elements are silently ignored so the helper is forgiving when handed
heterogeneous data.
"""


def recursive_nested_list_deep_product(nested_list):
    """Return the product of every number inside ``nested_list``.

    The traversal recurses into any nested list or tuple, multiplying the
    results of the sub-calls together.  An empty container contributes
    ``1`` to the overall product.

    Parameters
    ----------
    nested_list : list | tuple | int | float
        A (possibly empty) container whose elements may themselves be
        numbers or further nested containers.  A bare numeric value is
        treated as a leaf and returned unchanged.

    Returns
    -------
    int | float
        The product of every numeric leaf in the structure.  Returns
        ``1`` for an empty (sub-)tree and for any non-numeric leaf.
    """
    # --- 1. Recurse into lists / tuples ----------------------------------
    if isinstance(nested_list, (list, tuple)):
        product = 1
        for item in nested_list:
            product *= recursive_nested_list_deep_product(item)
        return product

    # --- 2. Booleans: treat as neutral (bool is a subclass of int) ------
    if isinstance(nested_list, bool):
        return 1

    # --- 3. Real numeric leaves -----------------------------------------
    if isinstance(nested_list, (int, float)):
        return nested_list

    # --- 4. Anything else is ignored (strings, None, objects, ...) ------
    return 1