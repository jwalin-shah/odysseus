import json
import os
import tempfile


def save_sync_state(path: str, seen_hashes: set) -> None:
    """Atomically write a JSON-encoded set of seen message fingerprints to disk.

    Creates parent directories as needed.
    """
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # Use mkstemp to get a secure temp file in the same directory
    # so that os.replace is an atomic operation on the same filesystem.
    fd, tmp_path = tempfile.mkstemp(dir=parent_dir or ".")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(list(seen_hashes), f)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
