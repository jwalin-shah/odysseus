# === flatten_nested.py ===

def flatten(nested):
    """Recursively flatten an arbitrarily nested list into a single flat list."""
    result = []
    for item in nested:
        if isinstance(item, (list, tuple)):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result


if __name__ == "__main__":
    nested = [1, [2, 3, [4, 5]], 6, [[7]], 8]
    print(flatten(nested))