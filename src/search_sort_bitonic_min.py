"""Find the minimum element in a bitonic array.

A bitonic array is one that is first strictly increasing and then
strictly decreasing. In such an array, the minimum element is always
located at one of the two endpoints (index 0 or index n-1).
"""


def search_sort_bitonic_min(arr):
    """Find the minimum element in a bitonic array.

    A bitonic array is one that is first strictly increasing and then
    strictly decreasing. In such an array, the minimum element is always
    located at one of the two endpoints (index 0 or index n-1).

    Args:
        arr: A list or tuple representing a bitonic array.

    Returns:
        The minimum element in the array.

    Raises:
        TypeError: If the input is not a list or tuple.
        ValueError: If the array is empty.
    """
    if not isinstance(arr, (list, tuple)):
        raise TypeError("Input must be a list or tuple")

    if len(arr) == 0:
        raise ValueError("Array cannot be empty")

    n = len(arr)
    if n == 1:
        return arr[0]

    # In a bitonic array, the minimum is always at one of the two
    # endpoints: arr[0] or arr[n-1]. We return the smaller of the two.
    return arr[0] if arr[0] <= arr[-1] else arr[-1]