# Microagent Router: builds keyword->file index from .agent-rules/ and skills/
# Reads keyword YAML front-matter and provides get_context(task_description)

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class MicroagentRouter:
    """Routes tasks to relevant microagents based on keyword matching."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.agent_rules_dir = self.base_path / ".agent-rules"
        self.skills_dir = self.base_path / "skills"
        self.keyword_index: Dict[str, str] = {}
        self._build_index()

    @staticmethod
    def _parse_front_matter(content: str) -> Optional[dict]:
        """Parse YAML front-matter from markdown content."""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return None
        front_matter_text = match.group(1)
        if HAS_YAML:
            try:
                data = yaml.safe_load(front_matter_text)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        # Fallback: simple key: value parsing
        result = {}
        for line in front_matter_text.splitlines():
            if ':' in line:
                key, _, value = line.partition(':')
                result[key.strip()] = value.strip()
        return result if result else None

    def _extract_keywords(self, front_matter: dict) -> List[str]:
        """Extract keywords from front-matter dict."""
        keywords: List[str] = []
        if not front_matter:
            return keywords

        kws = front_matter.get('keywords', front_matter.get('tags', []))
        if isinstance(kws, list):
            keywords.extend([str(k).lower().strip() for k in kws if k])
        elif isinstance(kws, str):
            keywords.append(kws.lower().strip())

        for field in ('description', 'name', 'title', 'summary'):
            val = front_matter.get(field)
            if val:
                words = re.findall(r'\w+', str(val).lower())
                keywords.extend(words)
        return keywords

    def _index_directory(self, directory: Path) -> None:
        """Index all markdown files in a directory."""
        if not directory.exists() or not directory.is_dir():
            return
        for md_file in directory.rglob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                front_matter = self._parse_front_matter(content)
                if front_matter:
                    keywords = self._extract_keywords(front_matter)
                    for kw in keywords:
                        if kw:
                            self.keyword_index[kw] = str(md_file)
            except (OSError, UnicodeDecodeError):
                continue

    def _build_index(self) -> None:
        """Build the keyword to file index."""
        self.keyword_index = {}
        self._index_directory(self.agent_rules_dir)
        self._index_directory(self.skills_dir)

    def reload(self) -> None:
        """Rebuild the index from disk."""
        self._build_index()

    def get_context(self, task_description: str) -> str:
        """Return the most relevant microagent content for the task description."""
        if not task_description or not self.keyword_index:
            return ""

        task_lower = task_description.lower()
        task_words = set(re.findall(r'\w+', task_lower))

        # Score each indexed file by keyword overlap
        file_scores: Dict[str, int] = {}
        for keyword, filepath in self.keyword_index.items():
            score = 0
            if keyword and keyword in task_lower:
                score += 10
            kw_words = set(re.findall(r'\w+', keyword))
            overlap = task_words & kw_words
            score += len(overlap)
            if score > 0:
                file_scores[filepath] = file_scores.get(filepath, 0) + score

        if not file_scores:
            return ""

        best_file = max(file_scores, key=file_scores.get)
        try:
            with open(best_file, 'r', encoding='utf-8') as f:
                return f.read()
        except OSError:
            return ""


_default_router: Optional[MicroagentRouter] = None


def get_router(base_path: str = ".") -> MicroagentRouter:
    """Get or create the default router singleton."""
    global _default_router
    if _default_router is None:
        _default_router = MicroagentRouter(base_path=base_path)
    return _default_router


def get_context(task_description: str, base_path: str = ".") -> str:
    """Convenience function to get context using the default router."""
    return get_router(base_path=base_path).get_context(task_description)