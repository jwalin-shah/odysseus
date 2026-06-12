import pytest
import subprocess
import json
import os
import tempfile
from pathlib import Path

# ============================================================================
# V2 ARCHITECTURAL SPEC: `sys-map` (AST RepoMap CLI)
# ============================================================================
# Analysis of Open-Source AST RepoMap Implementations (Aider, OpenDevin, SwarmAI):
# 1. AST Parsing: They utilize `tree-sitter` (or similar AST parsers) to extract
#    functions, classes, and method signatures without bringing in function bodies.
# 2. Resiliency: The parser must gracefully handle malformed code and syntax errors
#    (lossy parsing) without crashing the pipeline.
# 3. Graph Ranking: Symbols are placed into a dependency graph using imports and
#    references. A PageRank-like algorithm identifies the most critical context.
# 4. Token Budgeting: Output is strictly truncated to a `--max-tokens` limit,
#    evicting the lowest-ranked AST nodes first.
# ============================================================================

def run_sys_map(*args):
    """Helper to run the sys-map CLI in tests."""
    return subprocess.run(
        ["sys-map", *args],
        capture_output=True,
        text=True
    )

class TestOdyMapArchitecture:
    """
    Adversarial Pytest Specifications for the `sys-map` AST parser CLI.
    These tests enforce statelessness, AST intelligence, and strict output boundaries.
    """

    def test_ast_signature_extraction(self, tmp_path):
        """
        MUST extract function/class signatures and omit full implementations.
        """
        code_file = tmp_path / "test_module.py"
        code_file.write_text(
            "class Engine:\n"
            "    def start(self, speed: int):\n"
            "        for i in range(speed):\n"
            "            print('vroom')\n"
        )
        
        result = run_sys_map("--format", "json", str(code_file))
        assert result.returncode == 0
        output = json.loads(result.stdout)
        
        # Must contain class and signature, but MUST NOT contain the implementation body
        assert "class Engine:" in result.stdout
        assert "def start(self, speed: int):" in result.stdout
        assert "print('vroom')" not in result.stdout

    def test_syntax_error_resiliency(self, tmp_path):
        """
        MUST use lossy parsing and not crash when fed syntactically invalid files.
        """
        bad_file = tmp_path / "broken.py"
        bad_file.write_text("def missing_colon()\n    pass\n")
        
        result = run_sys_map(str(bad_file))
        assert result.returncode == 0
        assert "missing_colon" in result.stdout

    def test_strict_token_budget_truncation(self, tmp_path):
        """
        MUST deterministically truncate the AST map if it exceeds `--max-tokens`.
        Lowest priority symbols (least referenced) must be evicted first.
        """
        large_dir = tmp_path / "large_project"
        large_dir.mkdir()
        
        # Create heavily referenced core module
        (large_dir / "core.py").write_text("class Core:\n    def execute(self):\n        pass\n")
        
        # Create unreferenced peripheral modules
        for i in range(50):
            (large_dir / f"peripheral_{i}.py").write_text(f"def helper_{i}():\n    pass\n")
            
        result = run_sys_map("--dir", str(large_dir), "--max-tokens", "100")
        assert result.returncode == 0
        
        # Core must be preserved, peripherals should be pruned
        assert "class Core:" in result.stdout
        assert len(result.stdout) <= 100 * 4  # Approximation: 4 chars per token

    def test_dependency_graph_ranking(self, tmp_path):
        """
        MUST rank imported symbols higher than isolated symbols.
        """
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "utils.py").write_text("def important_util():\n    pass\n")
        (proj / "main.py").write_text("from utils import important_util\nimportant_util()\n")
        (proj / "dead_code.py").write_text("def dead():\n    pass\n")
        
        result = run_sys_map("--dir", str(proj), "--format", "json")
        data = json.loads(result.stdout)
        
        # Assert priority/rank output
        utils_rank = data["symbols"]["utils.py:important_util"]["rank"]
        dead_rank = data["symbols"]["dead_code.py:dead"]["rank"]
        assert utils_rank > dead_rank

    def test_stateless_execution(self, tmp_path):
        """
        MUST NOT leave cache files or artifacts behind unless explicitly requested via --cache-dir.
        """
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "main.py").write_text("print('hello')\n")
        
        before_files = set(proj.iterdir())
        run_sys_map("--dir", str(proj))
        after_files = set(proj.iterdir())
        
        assert before_files == after_files
