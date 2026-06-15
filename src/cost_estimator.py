def entry_model_name(entry: dict) -> str:
    """Extracts and normalizes the model identifier from a trajectory log entry.

    Looks for the model identifier under the 'model' key first, then falls back
    to 'model_name'. Returns 'unknown' if neither key is present or if the value
    is empty.
    """
    if not isinstance(entry, dict):
        return 'unknown'
    model = entry.get('model')
    if not model:
        model = entry.get('model_name')
    if not model:
        return 'unknown'
    return str(model).strip() or 'unknown'
