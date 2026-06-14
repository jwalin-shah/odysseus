# === avl_tree.py ===
"""AVL tree: self-balancing BST with O(log n) insert, delete, search."""
from __future__ import annotations
from typing import Any


class _Node:
    __slots__ = ("key", "value", "left", "right", "height")

    def __init__(self, key: Any, value: Any = None) -> None:
        self.key = key
        self.value = value
        self.left: _Node | None = None
        self.right: _Node | None = None
        self.height: int = 1


class AVLTree:
    """Self-balancing AVL tree ensuring O(log n) height via rotations."""

    def __init__(self) -> None:
        self.root: _Node | None = None
        self._size: int = 0

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: Any) -> bool:
        return self.search(key) is not None

    # ----- height / balance helpers -----
    @staticmethod
    def _h(node: _Node | None) -> int:
        return node.height if node else 0

    @staticmethod
    def _bf(node: _Node | None) -> int:
        return AVLTree._h(node.left) - AVLTree._h(node.right) if node else 0

    # ----- rotations -----
    @staticmethod
    def _rotate_right(y: _Node) -> _Node:
        x, t2 = y.left, y.left.right  # type: ignore[assignment]
        x.right = y
        y.left = t2
        y.height = 1 + max(AVLTree._h(y.left), AVLTree._h(y.right))
        x.height = 1 + max(AVLTree._h(x.left), AVLTree._h(x.right))
        return x

    @staticmethod
    def _rotate_left(x: _Node) -> _Node:
        y, t2 = x.right, x.right.left  # type: ignore[assignment]
        y.left = x
        x.right = t2
        x.height = 1 + max(AVLTree._h(x.left), AVLTree._h(x.right))
        y.height = 1 + max(AVLTree._h(y.left), AVLTree._h(y.right))
        return y

    # ----- rebalance -----
    @staticmethod
    def _rebalance(node: _Node) -> _Node:
        bf = AVLTree._bf(node)
        if bf > 1:
            if AVLTree._bf(node.left) < 0:
                node.left = AVLTree._rotate_left(node.left)  # type: ignore[arg-type]
            return AVLTree._rotate_right(node)
        if bf < -1:
            if AVLTree._bf(node.right) > 0:
                node.right = AVLTree._rotate_right(node.right)  # type: ignore[arg-type]
            return AVLTree._rotate_left(node)
        return node

    # ----- public ops -----
    def insert(self, key: Any, value: Any = None) -> None:
        def _ins(n: _Node | None) -> _Node:
            if n is None:
                self._size += 1
                return _Node(key, value)
            if key < n.key:
                n.left = _ins(n.left)
            elif key > n.key:
                n.right = _ins(n.right)
            else:
                n.value = value
                return n
            n.height = 1 + max(self._h(n.left), self._h(n.right))
            return self._rebalance(n)
        self.root = _ins(self.root)

    def delete(self, key: Any) -> None:
        def _min_node(n: _Node) -> _Node:
            while n.left:
                n = n.left  # type: ignore[assignment]
            return n

        def _del(n: _Node | None) -> _Node | None:
            if n is None:
                return None
            deleted = False
            if key < n.key:
                n.left = _del(n.left)
                deleted = n.left is not None or key in self  # not used downstream
            elif key > n.key:
                n.right = _del(n.right)
            else:
                if n.left is None or n.right is None:
                    self._size -= 1
                    return n.left or n.right
                succ = _min_node(n.right)  # type: ignore[arg-type]
                n.key, n.value = succ.key, succ.value
                n.right = _del(n.right)
            n.height = 1 + max(self._h(n.left), self._h(n.right))
            return self._rebalance(n)
        self.root = _del(self.root)

    def search(self, key: Any) -> Any | None:
        n = self.root
        while n:
            if key < n.key:
                n = n.left
            elif key > n.key:
                n = n.right
            else:
                return n.value
        return None

    def inorder(self) -> list[tuple[Any, Any]]:
        out: list[tuple[Any, Any]] = []
        stack: list[_Node] = []
        n = self.root
        while stack or n:
            while n:
                stack.append(n)
                n = n.left
            n = stack.pop()
            out.append((n.key, n.value))
            n = n.right
        return out


# === b_tree.py ===
"""B-tree of order `t`: balanced search tree for disk-friendly access."""
from __future__ import annotations
from typing import Any, Iterable


class _BNode:
    __slots__ = ("keys", "values", "children", "leaf")

    def __init__(self, leaf: bool) -> None:
        self.keys: list[Any] = []
        self.values: list[Any] = []
        self.children: list[_BNode] = []
        self.leaf: bool = leaf


class BTree:
    """B-tree with configurable minimum degree `t` (t >= 2)."""

    def __init__(self, t: int = 2) -> None:
        if t < 2:
            raise ValueError("minimum degree t must be >= 2")
        self.t: int = t
        self.root: _BNode = _BNode(leaf=True)

    # ----- split child -----
    def _split_child(self, parent: _BNode, i: int) -> None:
        t = self.t
        child = parent.children[i]
        new = _BNode(leaf=child.leaf)
        mid = t - 1
        new.keys = child.keys[t:]
        new.values = child.values[t:]
        if not child.leaf:
            new.children = child.children[t:]
        sep_key = child.keys[mid]
        sep_val = child.values[mid]
        child.keys = child.keys[:mid]
        child.values = child.values[:mid]
        if not child.leaf:
            child.children = child.children[:t]
        parent.keys.insert(i, sep_key)
        parent.values.insert(i, sep_val)
        parent.children.insert(i + 1, new)

    # ----- insert non-full -----
    def _insert_nonfull(self, node: _BNode, key: Any, value: Any) -> None:
        i = len(node.keys) - 1
        if node.leaf:
            while i >= 0 and key < node.keys[i]:
                i -= 1
            i += 1
            node.keys.insert(i, key)
            node.values.insert(i, value)
            return
        while i >= 0 and key < node.keys[i]:
            i -= 1
        i += 1
        if len(node.children[i].keys) == 2 * self.t - 1:
            self._split_child(node, i)
            if key > node.keys[i]:
                i += 1
        self._insert_nonfull(node.children[i], key, value)

    def insert(self, key: Any, value: Any = None) -> None:
        r = self.root
        if len(r.keys) == 2 * self.t - 1:
            s = _BNode(leaf=False)
            s.children.append(r)
            self._split_child(s, 0)
            self._insert_nonfull(s, key, value)
            self.root = s
        else:
            self._insert_nonfull(r, key, value)

    # ----- search -----
    def search(self, key: Any) -> Any | None:
        def _b(n: _BNode | None) -> Any | None:
            if n is None:
                return None
            i = 0
            while i < len(n.keys) and key > n.keys[i]:
                i += 1
            if i < len(n.keys) and key == n.keys[i]:
                return n.values[i]
            if n.leaf:
                return None
            return _b(n.children[i])
        return _b(self.root)

    def __contains__(self, key: Any) -> bool:
        return self.search(key) is not None

    def items(self) -> list[tuple[Any, Any]]:
        out: list[tuple[Any, Any]] = []

        def _walk(n: _BNode) -> None:
            for i, k in enumerate(n.keys):
                if not n.leaf:
                    _walk(n.children[i])
                out.append((k, n.values[i]))
            if not n.leaf:
                _walk(n.children[-1])
        _walk(self.root)
        return out

    def bulk_load(self, items: Iterable[tuple[Any, Any]]) -> None:
        for k, v in items:
            self.insert(k, v)


# === red_black_tree.py ===
"""Red-Black tree: self-balancing BST with strict O(log n) operations."""
from __future__ import annotations
from typing import Any

RED, BLACK = True, False


class _RBNode:
    __slots__ = ("key", "value", "left", "right", "parent", "color")

    def __init__(self, key: Any, value: Any = None,
                 color: bool = RED,
                 parent: "_RBNode | None" = None) -> None:
        self.key = key
        self.value = value
        self.left: _RBNode | None = None
        self.right: _RBNode | None = None
        self.parent = parent
        self.color = color


class RedBlackTree:
    NIL: _RBNode  # set in __init__

    def __init__(self) -> None:
        RedBlackTree.NIL = _RBNode(key=None, color=BLACK)
        RedBlackTree.NIL.left = RedBlackTree.NIL
        RedBlackTree.NIL.right = RedBlackTree.NIL
        self.NIL = RedBlackTree.NIL
        self.root: _RBNode = self.NIL
        self._size: int = 0

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: Any) -> bool:
        return self.search(key) is not None

    # ----- rotations -----
    def _left_rotate(self, x: _RBNode) -> None:
        y = x.right
        x.right = y.left
        if y.left is not self.NIL:
            y.left.parent = x
        y.parent = x.parent
        if x.parent is self.NIL:
            self.root = y
        elif x is x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y

    def _right_rotate(self, y: _RBNode) -> None:
        x = y.left
        y.left = x.right
        if x.right is not self.NIL:
            x.right.parent = y
        x.parent = y.parent
        if y.parent is self.NIL:
            self.root = x
        elif y is y.parent.left:
            y.parent.left = x
        else:
            y.parent.right = x
        x.right = y
        y.parent = x

    def _transplant(self, u: _RBNode, v: _RBNode) -> None:
        if u.parent is self.NIL:
            self.root = v
        elif u is u.parent.left:
            u.parent.left = v
        else:
            u.parent.right = v
        v.parent = u.parent

    def _minimum(self, x: _RBNode) -> _RBNode:
        while x.left is not self.NIL:
            x = x.left  # type: ignore[assignment]
        return x

    # ----- insert fixup -----
    def _insert_fix(self, z: _RBNode) -> None:
        while z.parent.color is RED:
            if z.parent is z.parent.parent.left:
                y = z.parent.parent.right
                if y.color is RED:
                    z.parent.color = BLACK
                    y.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z is z.parent.right:
                        z = z.parent
                        self._left_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._right_rotate(z.parent.parent)
            else:
                y = z.parent.parent.left
                if y.color is RED:
                    z.parent.color = BLACK
                    y.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z is z.parent.left:
                        z = z.parent
                        self._right_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._left_rotate(z.parent.parent)
        self.root.color = BLACK

    def insert(self, key: Any, value: Any = None) -> None:
        z = _RBNode(key, value, color=RED, parent=self.NIL)
        z.left = self.NIL
        z.right = self.NIL
        y, x = self.NIL, self.root
        while x is not self.NIL:
            y = x
            x = x.left if key < x.key else x.right
        z.parent = y
        if y is self.NIL:
            self.root = z
        elif key < y.key:
            y.left = z
        else:
            y.right = z
        self._size += 1
        self._insert_fix(z)

    def search(self, key: Any) -> Any | None:
        n = self.root
        while n is not self.NIL:
            if key < n.key:
                n = n.left
            elif key > n.key:
                n = n.right
            else:
                return n.value
        return None

    def inorder(self) -> list[tuple[Any, Any]]:
        out: list[tuple[Any, Any]] = []

        def _walk(n: _RBNode) -> None:
            if n is self.NIL:
                return
            _walk(n.left)
            out.append((n.key, n.value))
            _walk(n.right)
        _walk(self.root)
        return out


# === skiplist.py ===
"""Skip list: probabilistic balanced structure with expected O(log n) ops."""
from __future__ import annotations
import random
from typing import Any, Iterator


class _SNode:
    __slots__ = ("key", "value", "next", "span", "level")

    def __init__(self, key: Any = None, value: Any = None,
                 level: int = 0) -> None:
        self.key = key
        self.value = value
        self.next: list[_SNode | None] = [None] * (level + 1)
        self.span: list[int] = [0] * (level + 1)
        self.level: int = level


class SkipList:
    MAX_LEVEL = 32
    P = 0.5

    def __init__(self, seed: int | None = None) -> None:
        self._rand = random.Random(seed)
        self._level = 0
        self._size = 0
        self.head: _SNode = _SNode(level=self.MAX_LEVEL)

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: Any) -> bool:
        return self.search(key) is not None

    def _random_level(self) -> int:
        lvl = 0
        while lvl < self.MAX_LEVEL and self._rand.random() < self.P:
            lvl += 1
        return lvl

    def insert(self, key: Any, value: Any = None) -> None:
        update: list[_SNode] = [self.head] * (self.MAX_LEVEL + 1)
        rank: list[int] = [0] * (self.MAX_LEVEL + 1)
        n = self.head
        for i in range(self._level, -1, -1):
            rank[i] = rank[i + 1] if i + 1 <= self._level else 0
            while n.next[i] is not None and n.next[i].key < key:  # type: ignore[union-attr]
                rank[i] += n.span[i]
                n = n.next[i]  # type: ignore[assignment]
            update[i] = n
        n = n.next[0]  # type: ignore[assignment]
        if n is not None and n.key == key:
            n.value = value
            return
        lvl = self._random_level()
        if lvl > self._level:
            for i in range(self._level + 1, lvl + 1):
                update[i] = self.head
                rank[i] = 0
                self.head.span[i] = self._size
            self._level = lvl
        new = _SNode(key, value, level=lvl)
        for i in range(lvl + 1):
            new.next[i] = update[i].next[i]
            update[i].next[i] = new
            new.span[i] = update[i].span[i] - (rank[0] - rank[i])
            update[i].span[i] = (rank[0] - rank[i]) + 1
        for i in range(lvl + 1, self._level + 1):
            update[i].span[i] += 1
        self._size += 1

    def delete(self, key: Any) -> bool:
        update: list[_SNode] = [self.head] * (self.MAX_LEVEL + 1)
        n = self.head
        for i in range(self._level, -1, -1):
            while n.next[i] is not None and n.next[i].key < key:  # type: ignore[union-attr]
                n = n.next[i]  # type: ignore[assignment]
            update[i] = n
        n = n.next[0]  # type: ignore[assignment]
        if n is None or n.key != key:
            return False
        for i in range(self._level + 1):
            if update[i].next[i] is n:
                update[i].span[i] += n.span[i] - 1
                update[i].next[i] = n.next[i]
            else:
                update[i].span[i] -= 1
        while self._level > 0 and self.head.next[self._level] is None:
            self._level -= 1
        self._size -= 1
        return True

    def search(self, key: Any) -> Any | None:
        n = self.head
        for i in range(self._level, -1, -1):
            while n.next[i] is not None and n.next[i].key < key:  # type: ignore[union-attr]
                n = n.next[i]  # type: ignore[assignment]
        n = n.next[0]  # type: ignore[assignment]
        return n.value if n is not None and n.key == key else None

    def __iter__(self) -> Iterator[tuple[Any, Any]]:
        n = self.head.next[0]
        while n is not None:
            yield (n.key, n.value)
            n = n.next[0]  # type: ignore[assignment]


# === treap.py ===
"""Treap: randomized BST using heap-priority for expected O(log n) balance."""
from __future__ import annotations
import random
from typing import Any


class _TNode:
    __slots__ = ("key", "value", "prio", "left", "right")

    def __init__(self, key: Any, value: Any = None, prio: int = 0) -> None:
        self.key = key
        self.value = value
        self.prio = prio
        self.left: _TNode | None = None
        self.right: _TNode | None = None


class Treap:
    def __init__(self, seed: int | None = None) -> None:
        self._rand = random.Random(seed)
        self.root: _TNode | None = None
        self._size: int = 0

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: Any) -> bool:
        return self.search(key) is not None

    @staticmethod
    def _rotate_right(y: _TNode) -> _TNode:
        x = y.left  # type: ignore[assignment]
        t2 = x.right
        x.right = y
        y.left = t2
        return x

    @staticmethod
    def _rotate_left(x: _TNode) -> _TNode:
        y = x.right  # type: ignore[assignment]
        t2 = y.left
        y.left = x
        x.right = t2
        return y

    def insert(self, key: Any, value: Any = None) -> None:
        def _ins(n: _TNode | None) -> _TNode:
            if n is None:
                self._size += 1
                return _TNode(key, value, self._rand.randrange(1 << 30))
            if key < n.key:
                n.left = _ins(n.left)
                if n.left.prio < n.prio:
                    n = self._rotate_right(n)
            elif key > n.key:
                n.right = _ins(n.right)
                if n.right.prio < n.prio:
                    n = self._rotate_left(n)
            else:
                n.value = value
            return n
        self.root = _ins(self.root)

    def delete(self, key: Any) -> None:
        def _del(n: _TNode | None) -> _TNode | None:
            if n is None:
                return None
            if key < n.key:
                n.left = _del(n.left)
            elif key > n.key:
                n.right = _del(n.right)
            else:
                if n.left is None:
                    self._size -= 1
                    return n.right
                if n.right is None:
                    self._size -= 1
                    return n.left
                if n.left.prio < n.right.prio:
                    n = self._rotate_right(n)
                    n.right = _del(n.right)
                else:
                    n = self._rotate_left(n)
                    n.left = _del(n.left)
            return n
        self.root = _del(self.root)

    def search(self, key: Any) -> Any | None:
        n = self.root
        while n:
            if key < n.key:
                n = n.left
            elif key > n.key:
                n = n.right
            else:
                return n.value
        return None

    def inorder(self) -> list[tuple[Any, Any]]:
        out: list[tuple[Any, Any]] = []

        def _walk(n: _TNode | None) -> None:
            if n is None:
                return
            _walk(n.left)
            out.append((n.key, n.value))
            _walk(n.right)
        _walk(self.root)
        return out


# === segment_tree.py ===
"""Segment tree: range queries and point updates in O(log n)."""
from __future__ import annotations
from typing import Any, Callable, Sequence


class SegmentTree:
    def __init__(self, data: Sequence[Any], op: Callable[[Any, Any], Any],
                 identity: Any) -> None:
        self.n: int = len(data)
        self.op: Callable[[Any, Any], Any] = op
        self.identity: Any = identity
        self.size: int = 1
        while self.size < self.n:
            self.size <<= 1
        self.tree: list[Any] = [identity] * (2 * self.size)
        for i, v in enumerate(data):
            self.tree[self.size + i] = v
        for i in range(self.size - 1, 0, -1):
            self.tree[i] = op(self.tree[2 * i], self.tree[2 * i + 1])

    def update(self, idx: int, value: Any) -> None:
        if not 0 <= idx < self.n:
            raise IndexError("index out of range")
        i = idx + self.size
        self.tree[i] = value
        i >>= 1
        while i:
            self.tree[i] = self.op(self.tree[2 * i], self.tree[2 * i + 1])
            i >>= 1

    def query(self, left: int, right: int) -> Any:
        """Half-open [left, right)."""
        if left < 0 or right > self.n or left >= right:
            raise IndexError("invalid range")
        res_l = self.identity
        res_r = self.identity
        l = left + self.size
        r = right + self.size
        while l < r:
            if l & 1:
                res_l = self.op(res_l, self.tree[l])
                l += 1
            if r & 1:
                r -= 1
                res_r = self.op(self.tree[r], res_r)
            l >>= 1
            r >>= 1
        return self.op(res_l, res_r)


# === fenwick_tree.py ===
"""Fenwick / Binary Indexed Tree: prefix sums with O(log n) updates."""
from __future__ import annotations
from typing import Sequence


class FenwickTree:
    def __init__(self, size: int) -> None:
        if size < 0:
            raise ValueError("size must be non-negative")
        self.n: int = size
        self.bit: list[int] = [0] * (self.n + 1)

    def build(self, data: Sequence[int]) -> None:
        if len(data) != self.n:
            raise ValueError("data length must equal size")
        for i, v in enumerate(data, 1):
            self.bit[i] = v
        for i in range(1, self.n + 1):
            j = i + (i & -i)
            if j <= self.n:
                self.bit[j] += self.bit[i]

    def update(self, idx: int, delta: int) -> None:
        i = idx + 1
        while i <= self.n:
            self.bit[i] += delta
            i += i & -i

    def set(self, idx: int, value: int) -> None:
        cur = self.prefix_sum(idx + 1) - self.prefix_sum(idx)
        self.update(idx, value - cur)

    def prefix_sum(self, k: int) -> int:
        if k < 0:
            return 0
        if k > self.n:
            k = self.n
        s = 0
        i = k
        while i > 0:
            s += self.bit[i]
            i -= i & -i
        return s

    def range_sum(self, left: int, right: int) -> int:
        if left >= right:
            return 0
        return self.prefix_sum(right) - self.prefix_sum(left)


# === sparse_table.py ===
"""Sparse table: idempotent range queries in O(1) after O(n log n) build."""
from __future__ import annotations
from math import log2
from typing import Any, Callable, Sequence


class SparseTable:
    def __init__(self, data: Sequence[Any],
                 op: Callable[[Any, Any], Any]) -> None:
        self.n: int = len(data)
        self.log: list[int] = [0] * (self.n + 1)
        for i in range(2, self.n + 1):
            self.log[i] = self.log[i >> 1] + 1
        k = self.log[self.n] + 1
        self.st: list[list[Any]] = [list(data)] + [
            [op(self.st[i - 1][j], self.st[i - 1][j + (1 << (i - 1))])
             for j in range(self.n - (1 << i) + 1)]
            for i in range(1, k)
        ]
        self.op: Callable[[Any, Any], Any] = op

    def query(self, left: int, right: int) -> Any:
        """Closed [left, right]."""
        if left < 0 or right >= self.n or left > right:
            raise IndexError("invalid range")
        j = self.log[right - left + 1]
        return self.op(self.st[j][left], self.st[j][right - (1 << j) + 1])


# === union_find.py ===
"""Union-Find / Disjoint Set Union with path compression and union by rank."""
from __future__ import annotations
from typing import Any


class UnionFind:
    def __init__(self, size: int) -> None:
        if size < 0:
            raise ValueError("size must be non-negative")
        self.parent: list[int] = list(range(size))
        self.rank: list[int] = [0] * size
        self.components: int = size

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, x: int, y: int) -> bool:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
        self.components -= 1
        return True

    def connected(self, x: int, y: int) -> bool:
        return self.find(x) == self.find(y)

    def __len__(self) -> int:
        return self.components