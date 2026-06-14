def van_eck(n):
    """Generate the first n terms of Van Eck's sequence.

    Van Eck's sequence is defined as:
    - a(0) = 0
    - For n >= 1: a(n) = 0 if a(n-1) has not appeared in a(0)..a(n-2)
    - Otherwise, a(n) = the distance from the most recent previous occurrence
      of a(n-1) (at some index j < n-1) to position n-1.

    Args:
        n: Number of terms to generate. Non-positive values yield an empty list.

    Returns:
        A list of n integers representing the first n terms of the sequence.
    """
    if n <= 0:
        return []
    if n == 1:
        return [0]

    seq = [0]
    # occurrences[value] = [last_index, second_to_last_index] where the value
    # appeared in the sequence so far. We need both because when computing
    # seq[i] we look at the most recent occurrence of seq[i-1] strictly
    # before index i-1; if the most recent is at i-1 itself, we fall back
    # to the second-to-last.
    occurrences = {0: [0, None]}

    for i in range(1, n):
        prev_val = seq[i - 1]
        info = occurrences.get(prev_val)

        if info is None:
            seq.append(0)
        else:
            last_idx, second_last_idx = info
            if last_idx < i - 1:
                # Most recent occurrence is strictly before i-1.
                seq.append((i - 1) - last_idx)
            elif second_last_idx is not None:
                # Most recent occurrence is at i-1; use the second-to-last.
                seq.append((i - 1) - second_last_idx)
            else:
                # No occurrence strictly before i-1.
                seq.append(0)

        # Record where the new value appeared.
        new_val = seq[i]
        if new_val in occurrences:
            old_last = occurrences[new_val][0]
            occurrences[new_val] = [i, old_last]
        else:
            occurrences[new_val] = [i, None]

    return seq