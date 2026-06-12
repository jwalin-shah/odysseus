#!/usr/bin/env bash
# Regenerate the sys-* CLI shims the v2 tests invoke. Run after rebuilding
# either venv. Tests resolve shims two ways: by PATH (sys-quota) and by
# repo-root .venv/bin path (sys-router), so both venvs get a full set.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

make_set() {
  local venv="$1"
  [[ -x "$venv/bin/python" ]] || { echo "skip: $venv (no python)"; return; }
  for pair in sys-quota:sys_quota ody-map:sys_map ody-router:sys_router; do
    local shim="$venv/bin/${pair%%:*}" mod="${pair##*:}"
    cat > "$shim" <<EOF
#!$venv/bin/python
import sys, os
sys.path.insert(0, os.path.join("$ROOT", "v2", "src"))
from $mod import main
raise SystemExit(main())
EOF
    chmod +x "$shim"
  done
  ln -sf ody-router "$venv/bin/sys-router"
  ln -sf ody-map "$venv/bin/sys-map"
  echo "shims: $venv/bin"
}

make_set "$ROOT/.venv"
make_set "$ROOT/v2/.venv"
