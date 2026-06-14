from typing import List, Optional


def single_element_isolator_every_three_repeats(nums: List[int]) -> Optional[int]:
    """
    Given a list where every element appears exactly three times except for one
    element which appears exactly once, find and return that single element.

    Uses bit manipulation (the classic "ones and twos" state-machine trick) to
    achieve O(n) time and O(1) extra space. For every bit position two
    variables track whether the bit has been seen once (`ones`) or twice
    (`twos`). When a bit is seen a third time it is dropped from both state
    variables; the surviving bits of `ones` form the unique element.

    Args:
        nums: A list of integers in which every value appears three times
            except for exactly one value, which appears once.

    Returns:
        The element that appears only once, or None if the input list is empty.
    """
    if not nums:
        return None

    ones, twos = 0, 0
    for num in nums:
        # Bits that have now appeared once for `num`, and are not already in `twos`.
        ones = (ones ^ num) & ~twos
        # Bits that have now appeared twice for `num`, and are not in the new `ones`.
        twos = (twos ^ num) & ~ones

    return ones