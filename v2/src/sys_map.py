"""sys-map: stateless AST repo map CLI (pure stdlib)."""
import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Signature extraction helpers
# ---------------------------------------------------------------------------

def _annotation_to_str(node):
    """Convert an AST annotation node to a string representation."""
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        if isinstance(node, ast.Name):
            return node.id
        return "..."


def _args_to_str(args_node):
    """Convert ast.arguments to a comma-separated string."""
    parts = []
    all_args = args_node.args
    defaults = args_node.defaults
    defaults_offset = len(all_args) - len(defaults)

    # posonlyargs (Python 3.8+)
    posonlyargs = getattr(args_node, "posonlyargs", [])
    for i, arg in enumerate(posonlyargs):
        s = arg.arg
        if arg.annotation:
            s += f": {_annotation_to_str(arg.annotation)}"
        parts.append(s)
    if posonlyargs:
        parts.append("/")

    for i, arg in enumerate(all_args):
        s = arg.arg
        if arg.annotation:
            s += f": {_annotation_to_str(arg.annotation)}"
        idx = i - defaults_offset
        if 0 <= idx < len(defaults):
            s += f"={_annotation_to_str(defaults[idx])}"
        parts.append(s)

    if args_node.vararg:
        s = f"*{args_node.vararg.arg}"
        if args_node.vararg.annotation:
            s += f": {_annotation_to_str(args_node.vararg.annotation)}"
        parts.append(s)
    elif args_node.kwonlyargs:
        parts.append("*")

    for i, arg in enumerate(args_node.kwonlyargs):
        s = arg.arg
        if arg.annotation:
            s += f": {_annotation_to_str(arg.annotation)}"
        kw_default = args_node.kw_defaults[i]
        if kw_default is not None:
            s += f"={_annotation_to_str(kw_default)}"
        parts.append(s)

    if args_node.kwarg:
        s = f"**{args_node.kwarg.arg}"
        if args_node.kwarg.annotation:
            s += f": {_annotation_to_str(args_node.kwarg.annotation)}"
        parts.append(s)

    return ", ".join(parts)


def _func_signature(node):
    """Return the def/async def signature line for a FunctionDef node."""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args = _args_to_str(node.args)
    ret = ""
    if node.returns:
        ret = f" -> {_annotation_to_str(node.returns)}"
    return f"{prefix} {node.name}({args}){ret}:"


def _class_signature(node):
    """Return the class signature line."""
    bases = []
    for b in node.bases:
        bases.append(_annotation_to_str(b))
    if bases:
        return f"class {node.name}({', '.join(bases)}):"
    return f"class {node.name}:"


# ---------------------------------------------------------------------------
# Lossy regex fallback for syntax-broken files
# ---------------------------------------------------------------------------

def _extract_names_regex(source):
    """Best-effort extraction of function/class names from broken source."""
    names = []
    for m in re.finditer(r'^\s*(?:async\s+)?def\s+(\w+)', source, re.MULTILINE):
        names.append(m.group(1))
    for m in re.finditer(r'^\s*class\s+(\w+)', source, re.MULTILINE):
        names.append(m.group(1))
    return names


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_signatures_from_file(filepath):
    """
    Parse a Python file and return {classes, functions} dicts.
    Returns None only on unrecoverable read errors.
    On SyntaxError returns a best-effort result.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        return None

    classes = {}
    functions = []

    try:
        tree = ast.parse(source, filename=str(filepath))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(item.name)
                classes[node.name] = {"methods": methods}
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
    except SyntaxError:
        # Lossy fallback: extract names with regex
        for name in _extract_names_regex(source):
            functions.append(name)

    return {"classes": classes, "functions": functions}


def _extract_symbols_from_file(filepath, base_dir=None):
    """
    Return list of (key, signature, kind) tuples.
    key = "relpath:name" or "basename:name"
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        return []

    if base_dir:
        rel = os.path.relpath(filepath, base_dir)
    else:
        rel = os.path.basename(filepath)

    results = []

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        # Lossy fallback
        for name in _extract_names_regex(source):
            results.append((f"{rel}:{name}", name, "function"))
        return results

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            sig = _class_signature(node)
            results.append((f"{rel}:{node.name}", sig, "class"))
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    msig = _func_signature(item)
                    results.append((f"{rel}:{node.name}.{item.name}", f"    {msig}", "method"))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = _func_signature(node)
            results.append((f"{rel}:{node.name}", sig, "function"))

    return results


def _extract_imports(filepath):
    """Return set of imported names from a file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=str(filepath))
    except (OSError, SyntaxError):
        return set()

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.name)
                if alias.asname:
                    imported.add(alias.asname)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
                if alias.asname:
                    imported.add(alias.asname)
    return imported


def _collect_references(filepath):
    """Return set of Name ids referenced in a file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=str(filepath))
    except (OSError, SyntaxError):
        return set()

    refs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            refs.add(node.id)
    return refs


# ---------------------------------------------------------------------------
# Directory mapping
# ---------------------------------------------------------------------------

def map_directory(directory_path):
    """Return {relpath: {classes, functions}} for all .py files."""
    result = {}
    for root, _, files in os.walk(directory_path):
        for fname in sorted(files):
            if fname.endswith(".py"):
                fpath = os.path.join(root, fname)
                sigs = extract_signatures_from_file(fpath)
                if sigs is not None:
                    rel = os.path.relpath(fpath, directory_path)
                    result[rel] = sigs
    return result


# ---------------------------------------------------------------------------
# Dependency graph ranking
# ---------------------------------------------------------------------------

def _build_symbol_ranks(directory_path):
    """
    Build a symbol rank map using import/reference counting.
    Returns dict: "relpath:name" -> rank (float, 0.0-1.0)
    """
    py_files = []
    for root, _, files in os.walk(directory_path):
        for fname in sorted(files):
            if fname.endswith(".py"):
                py_files.append(os.path.join(root, fname))

    # Map short name -> list of full keys that define it
    name_to_keys = {}
    all_symbol_keys = set()
    for fpath in py_files:
        for key, sig, kind in _extract_symbols_from_file(fpath, directory_path):
            all_symbol_keys.add(key)
            short = key.split(":")[-1].split(".")[-1]
            name_to_keys.setdefault(short, []).append(key)

    # Count cross-file references to each symbol
    ref_counts = {}
    for fpath in py_files:
        imported = _extract_imports(fpath)
        refs = _collect_references(fpath)
        all_refs = imported | refs
        for name in all_refs:
            for key in name_to_keys.get(name, []):
                ref_counts[key] = ref_counts.get(key, 0) + 1

    max_refs = max(ref_counts.values()) if ref_counts else 1
    ranks = {}
    for key in all_symbol_keys:
        count = ref_counts.get(key, 0)
        ranks[key] = count / max(max_refs, 1)

    return ranks


# ---------------------------------------------------------------------------
# Token budget truncation
# ---------------------------------------------------------------------------

def _approx_tokens(text):
    """Approximate token count: 1 token ~ 4 chars."""
    return max(1, len(text) // 4)


def _render_text_dir(directory_path, max_tokens=None):
    """Render a text map of a directory, optionally truncated to max_tokens."""
    py_files = []
    for root, _, files in os.walk(directory_path):
        for fname in sorted(files):
            if fname.endswith(".py"):
                py_files.append(os.path.join(root, fname))

    ranks = _build_symbol_ranks(directory_path) if max_tokens else {}

    # Build flat list of (priority, line) pairs in file order
    lines_with_priority = []
    for fpath in py_files:
        rel = os.path.relpath(fpath, directory_path)
        syms = _extract_symbols_from_file(fpath, directory_path)
        if not syms:
            continue
        file_rank = max((ranks.get(key, 0) for key, _, _ in syms), default=0) if max_tokens else 0
        # File header gets same priority as best symbol (not higher) so symbols win budget
        lines_with_priority.append((file_rank, f"# {rel}"))
        for key, sig, kind in syms:
            priority = ranks.get(key, 0) if max_tokens else 0
            lines_with_priority.append((priority, sig))

    if max_tokens:
        # Budget in characters: max_tokens * 4 chars, minus 1 for trailing newline from print()
        char_budget = max_tokens * 4 - 1
        # Sort by priority desc, greedily fill budget
        sorted_lines = sorted(lines_with_priority, key=lambda x: -x[0])
        kept = []
        total_chars = 0
        for priority, line in sorted_lines:
            # Cost: len(line) + 1 for the joining newline (or trailing newline)
            cost = len(line) + 1
            if total_chars + cost <= char_budget:
                kept.append((priority, line))
                total_chars += cost
        # Restore approximate file order by sorting stably (priority desc)
        kept.sort(key=lambda x: -x[0])
        lines = [line for _, line in kept]
    else:
        lines = [line for _, line in lines_with_priority]

    return "\n".join(lines)


def _render_json_dir(directory_path):
    """Render JSON map of a directory with symbol ranks."""
    ranks = _build_symbol_ranks(directory_path)

    py_files = []
    for root, _, files in os.walk(directory_path):
        for fname in sorted(files):
            if fname.endswith(".py"):
                py_files.append(os.path.join(root, fname))

    symbols = {}
    for fpath in py_files:
        for key, sig, kind in _extract_symbols_from_file(fpath, directory_path):
            symbols[key] = {
                "signature": sig.strip(),
                "kind": kind,
                "rank": ranks.get(key, 0.0),
            }

    return json.dumps({"symbols": symbols}, indent=2)


def _render_json_file(filepath):
    """Render JSON map of a single file."""
    basename = os.path.basename(filepath)
    syms = _extract_symbols_from_file(filepath, os.path.dirname(filepath))

    symbols = {}
    signatures = []
    for key, sig, kind in syms:
        short_key = f"{basename}:{key.split(':', 1)[-1]}"
        clean_sig = sig.strip()
        symbols[short_key] = {
            "signature": clean_sig,
            "kind": kind,
            "rank": 1.0,
        }
        signatures.append(clean_sig)

    return json.dumps({"symbols": symbols, "signatures": signatures}, indent=2)


def _render_text_file(filepath):
    """Render text map of a single file."""
    syms = _extract_symbols_from_file(filepath, os.path.dirname(filepath))
    if not syms:
        # Fallback: lossy regex extraction
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError:
            return ""
        return "\n".join(_extract_names_regex(source))
    return "\n".join(sig for _, sig, _ in syms)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(prog="sys-map")
    parser.add_argument("file", nargs="?", help="Single Python file to map")
    parser.add_argument("--dir", help="Directory to map")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--cache-dir", help="Cache directory (reserved for future use)")
    args = parser.parse_args(argv)

    if args.dir:
        if args.format == "json":
            output = _render_json_dir(args.dir)
        else:
            output = _render_text_dir(args.dir, max_tokens=args.max_tokens)
    elif args.file:
        if not os.path.isfile(args.file):
            print(f"sys-map: error: file not found: {args.file}", file=sys.stderr)
            return 1
        if args.format == "json":
            output = _render_json_file(args.file)
        else:
            output = _render_text_file(args.file)
    else:
        parser.print_usage(sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
