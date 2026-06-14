def trimorphic_predicate(n):
    """Return True if n is a trimorphic number.

    A trimorphic number is an integer whose cube ends in the digits of the
    number itself. For example, 24 is trimorphic because 24**3 = 13824,
    which ends in the digits "24".

    Parameters
    ----------
    n : int
        The number to test. Non-integer values are coerced via ``int()``.

    Returns
    -------
    bool
        True if ``n`` is trimorphic, False otherwise.
    """
    n = int(n)
    cube = n ** 3
    # str(cube).endswith(str(n)) correctly handles multi-digit suffixes
    # because string suffix matching works on the decimal representation.
    return str(cube).endswith(str(n))