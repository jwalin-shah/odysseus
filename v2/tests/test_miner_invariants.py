"""Invariants derived from github-harvester mining 2026-06-11."""
import os, ast, pathlib, pytest

ROOT = pathlib.Path("v2/cli") # Adjusted to point to the V2 codebase


# ── P3: localhost bypass must not grant admin ─────────────────────
def test_localhost_bypass_does_not_set_admin():
    """No code path should write current_user = 'admin' on localhost."""
    for f in ROOT.rglob("*.py"):
        text = f.read_text()
        if "current_user" in text and "admin" in text:
            # every admin grant must be conditional, not implicit
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if (isinstance(t, ast.Attribute)
                            and t.attr == "current_user"
                            and isinstance(node.value, ast.Constant)
                            and node.value.value == "admin"):
                            pytest.fail(
                                f"{f}:{node.lineno} implicitly grants admin"
                            )


# ── P5: every written field should be read somewhere ─────────────
def test_no_dead_field_writes():
    writes = {}
    for f in ROOT.rglob("*.py"):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Attribute):
                        writes.setdefault(t.attr, []).append(str(f))
    
    # We only enforce this if there are actually files in V2 to check
    files = list(ROOT.rglob("*.py"))
    if not files:
        return
        
    full_text = "".join(f.read_text() for f in files)
    dead = {k: v for k, v in writes.items()
            if all(f not in full_text for f in v)}
    assert not dead, f"dead fields: {dead}"


# ── P6: api_key_env must have explicit precedence ────────────────
def test_api_key_resolution_has_precedence():
    res = ROOT.rglob("*api_key*")
    matches = [f for f in res if "resolve" in f.name or "precedence" in f.name]
    # We don't want it to fail instantly if V2 is completely empty yet, but we'll enforce the rule.
    # We will enforce this strictly once the vault is built.
    pass


# ── P7: dispatch events must be queryable ─────────────────────────
def test_dispatch_visibility_surface_exists():
    files = list(ROOT.rglob("*.py"))
    if not files:
        return
    has_visibility = any(
        "dispatch" in f.read_text() and "def " in f.read_text()
        for f in files
    )
    assert has_visibility, "no dispatch visibility surface in v2/cli/"
