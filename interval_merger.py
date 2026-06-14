def merge(intervals):
    if not intervals:
        return []
    sorted_intervals = sorted(intervals)
    merged = [sorted_intervals[0]]
    for current in sorted_intervals[1:]:
        if current[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], current[1]))
        else:
            merged.append(current)
    return merged

def total_length(intervals):
    return sum(end - start for start, end in intervals)