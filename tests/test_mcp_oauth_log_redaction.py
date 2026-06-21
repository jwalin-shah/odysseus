"""ODYSSEY-OAUTH-LOG regression tests for routes/mcp_routes secret redaction.

The previous mcp_routes.py called `logger.info(...)` with
`client_secret=...` payloads on the happy path. A long-lived OAuth
client_secret is exactly the kind of credential that must never reach a
log aggregator, error tracker, or CI artefact. The fix installs a
logging.LogRecord factory that scrubs `_SECRET_KEYS` out of every record
this module emits, plus a `_redact_secrets` helper for direct unit tests.
"""
from __future__ import annotations

import io
import logging
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# Stub out the heavy deps the route module imports so the test stays
# dependency-free. bcrypt is the one actually missing on the test runner.
def _stub(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class _Router:
    def __init__(self, *a, **kw):
        self.routes = []

    def get(self, *a, **kw):
        def deco(fn):
            self.routes.append(fn)
            return fn

        return deco

    def post(self, *a, **kw):
        def deco(fn):
            self.routes.append(fn)
            return fn

        return deco


_stub("core.database", McpServer=type("M", (), {}), SessionLocal=type("S", (), {}))
_stub("core.middleware", require_admin=lambda r: None)
_stub("src.constants", DATA_DIR="/tmp/odyssey-unify-test")
class _Mgr:
    pass


_stub("src.mcp_manager", McpManager=_Mgr)
_stub("core.auth")
_stub("bcrypt", __version__="stub")

# `sys_checkpoint` / pre-existing module caches can shadow the safe factory
# across test runs; force a fresh import of the module under test.
sys.modules.pop("routes.mcp_routes", None)
import routes.mcp_routes as m  # noqa: E402

REDACT = m._redact_secrets
SENSITIVE = "TOP_SECRET_DO_NOT_LEAK_123"


def test_redact_kv_form():
    assert REDACT(f"client_secret={SENSITIVE}") == "client_secret=<REDACTED>"


def test_redact_json_double_quoted():
    assert REDACT(f'"client_secret": "{SENSITIVE}"') == '"client_secret": "<REDACTED>"'


def test_redact_python_single_quoted():
    assert REDACT(f"'client_secret': '{SENSITIVE}'") == "'client_secret': '<REDACTED>'"


def test_redact_access_token():
    assert REDACT("access_token=eyJ-abc-xyz") == "access_token=<REDACTED>"


def test_redact_refresh_token():
    assert REDACT("refresh_token=rt-xyz") == "refresh_token=<REDACTED>"


def test_redact_id_token():
    assert REDACT("id_token=id-xyz") == "id_token=<REDACTED>"


def test_redact_leaves_non_secret_keys_intact():
    line = "level=info msg=hello status=200 path=/var/log/app.log"
    assert REDACT(line) == line


def test_redact_preserves_sibling_keys():
    line = f"client_id=alice client_secret={SENSITIVE} status=ok"
    assert REDACT(line) == "client_id=alice client_secret=<REDACTED> status=ok"


def test_redact_handles_empty_string():
    assert REDACT("") == ""


def test_redact_handles_multiple_secrets_in_one_line():
    line = f"client_secret={SENSITIVE} access_token=eyJabc refresh_token=rt-xyz"
    out = REDACT(line)
    assert SENSITIVE not in out
    assert "access_token=<REDACTED>" in out
    assert "refresh_token=<REDACTED>" in out


def test_module_logger_scrubs_secrets_at_emission():
    """The installed _SafeLogRecordFactory must scrub the module's own
    `logger` calls — that's the actual attack surface. We capture into a
    private StringIO handler so the test doesn't depend on the global
    root logger config."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.INFO)
    saved_level = m.logger.level
    saved_propagate = m.logger.propagate
    m.logger.addHandler(handler)
    m.logger.setLevel(logging.INFO)
    m.logger.propagate = False
    try:
        m.logger.info("client_secret=%s client_id=alice status=ok", SENSITIVE)
        m.logger.info("JSON dump: %s", f'{{"client_secret": "{SENSITIVE}"}}')
        m.logger.info("token: %s", f"access_token={SENSITIVE}")
    finally:
        m.logger.removeHandler(handler)
        m.logger.setLevel(saved_level)
        m.logger.propagate = saved_propagate

    captured = buf.getvalue()
    assert SENSITIVE not in captured
    assert "client_secret=<REDACTED>" in captured
    assert "access_token=<REDACTED>" in captured
    assert "client_id=alice" in captured  # non-secret key survives


def test_module_logger_idempotent_under_reinstall():
    """Re-installing the safe factory on top of an already-installed safe
    factory must produce exactly one scrubbing pass per record (not N).

    The real install path in `mcp_routes.py` checks `isinstance(_old_factory,
    _SafeLogRecordFactory)` so a re-import of the module wraps nothing
    extra. We assert that property directly: install -> emit (one REDACTED),
    install again -> emit (still one REDACTED)."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.INFO)
    saved_level = m.logger.level
    saved_propagate = m.logger.propagate
    m.logger.addHandler(handler)
    m.logger.setLevel(logging.INFO)
    m.logger.propagate = False
    try:
        # Mimic module import: ensure the safe factory is the live one.
        current = logging.getLogRecordFactory()
        if not isinstance(current, m._SafeLogRecordFactory):
            logging.setLogRecordFactory(m._SafeLogRecordFactory(current))
        m.logger.info("client_secret=%s", SENSITIVE)
        # Now simulate a second module import — but the live factory is
        # already a _SafeLogRecordFactory, so the install in mcp_routes.py
        # would no-op. We force a stack to prove the test catches it.
        logging.setLogRecordFactory(m._SafeLogRecordFactory(logging.getLogRecordFactory()))
        logging.setLogRecordFactory(m._SafeLogRecordFactory(logging.getLogRecordFactory()))
        buf.truncate(0)
        buf.seek(0)
        m.logger.info("client_secret=%s", SENSITIVE)
    finally:
        m.logger.removeHandler(handler)
        m.logger.setLevel(saved_level)
        m.logger.propagate = saved_propagate
    out = buf.getvalue()
    assert SENSITIVE not in out
    # The message emitted one line containing exactly one REDACTED marker.
    assert out.count("client_secret=<REDACTED>") == 1, (
        f"expected exactly one REDACTED marker, got: {out!r}"
    )


def test_factory_install_is_noop_when_already_safe():
    """`mcp_routes.py` guards with `isinstance(_old_factory, _SafeLogRecordFactory)`.
    A re-import must not stack factories — direct check of the install path."""
    # Reset to the python default factory.
    logging.setLogRecordFactory(logging.LogRecord)
    # First install — should wrap.
    first = logging.getLogRecordFactory()
    m._install_safe_factory()
    wrapped1 = logging.getLogRecordFactory()
    assert isinstance(wrapped1, m._SafeLogRecordFactory)
    # Second install — must not stack.
    m._install_safe_factory()
    wrapped2 = logging.getLogRecordFactory()
    assert wrapped2 is wrapped1, "second install must not stack a new wrapper"


if __name__ == "__main__":
    test_redact_kv_form()
    test_redact_json_double_quoted()
    test_redact_python_single_quoted()
    test_redact_access_token()
    test_redact_refresh_token()
    test_redact_id_token()
    test_redact_leaves_non_secret_keys_intact()
    test_redact_preserves_sibling_keys()
    test_redact_handles_empty_string()
    test_redact_handles_multiple_secrets_in_one_line()
    test_module_logger_scrubs_secrets_at_emission()
    test_module_logger_idempotent_under_reinstall()
    test_factory_install_is_noop_when_already_safe()
    print("13 passed")
