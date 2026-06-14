# === trie_autocomplete.py ===
"""Trie-based autocomplete with frequency ranking."""
from __future__ import annotations
import heapq


class _Node:
    __slots__ = ('children', 'freq', 'word')

    def __init__(self):
        self.children: dict[str, '_Node'] = {}
        self.freq: int = 0
        self.word: str | None = None


class TrieAutocomplete:
    def __init__(self):
        self._root = _Node()

    def insert(self, word: str, freq: int = 1) -> None:
        node = self._root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = _Node()
            node = node.children[ch]
        node.freq = freq
        node.word = word

    def _collect(self, node: _Node, results: list) -> None:
        if node.word is not None:
            results.append((node.word, node.freq))
        for child in node.children.values():
            self._collect(child, results)

    def search(self, prefix: str, top_k: int = 10) -> list[tuple[str, int]]:
        node = self._root
        for ch in prefix:
            if ch not in node.children:
                return []
            node = node.children[ch]
        results: list[tuple[str, int]] = []
        self._collect(node, results)
        return heapq.nlargest(top_k, results, key=lambda x: x[1])

    def delete(self, word: str) -> bool:
        def _del(node: _Node, i: int) -> bool:
            if i == len(word):
                if node.word is None:
                    return False
                node.word = None
                node.freq = 0
                return True
            ch = word[i]
            if ch not in node.children:
                return False
            removed = _del(node.children[ch], i + 1)
            if removed and not node.children[ch].children and node.children[ch].word is None:
                del node.children[ch]
            return removed
        return _del(self._root, 0)

    def starts_with(self, prefix: str) -> bool:
        node = self._root
        for ch in prefix:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return True
