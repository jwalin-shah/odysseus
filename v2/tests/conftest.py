"""v2 test configuration.

The v2 tests invoke the sys-* / ody-* CLIs as subprocesses WITHOUT the
full path (e.g. `subprocess.run(["sys-quota", "deduct", ...])`) and
rely on the project's .venv/bin being on PATH. pytest doesn't add
that by default, so we prepend it here for the whole v2 test session.
"""
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_VENV_BIN = _PROJECT_ROOT / ".venv" / "bin"

# Prepend the v2 sys path so v2/src modules import as top-level
# (sys_quota, sys_router, sys_map, sys_vault, sys_checkpoint, sys_scraper).
_SRC_DIR = _PROJECT_ROOT / "v2" / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Prepend the venv bin so subprocess calls like ['sys-quota', 'deduct', ...]
# find the shim. We mutate os.environ so child processes inherit it.
os.environ["PATH"] = f"{_VENV_BIN}{os.pathsep}{os.environ.get('PATH', '')}"
