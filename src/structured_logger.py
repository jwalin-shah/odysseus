import sys

_current_stream = sys.stdout


def configure_logger(stream=None):
    """Configure the global output stream for log_event.

    Returns the previously configured stream. When called with no
    argument (or with None), the currently configured stream is
    returned without modification.
    """
    global _current_stream
    if stream is None:
        return _current_stream
    previous = _current_stream
    _current_stream = stream
    return previous


def log_event(event):
    """Write a log event to the currently configured stream."""
    if _current_stream is not None:
        _current_stream.write(str(event) + "\n")
        _current_stream.flush()
