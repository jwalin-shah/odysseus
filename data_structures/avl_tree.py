class AVLTree:
    class _Node:
        __slots__ = ("key", "left", "right", "height")

        def __init__(self, key: int):
            self.key = key
            self.left = None
            self.right = None
            self.height = 1

    def __init__(self):
        self._root = None

    def _height(self, node: "_Node | None") -> int:
        return 0 if node is None else node.height

    def _update_height(self, node: "_Node") -> None:
        node.height = 1 + max(self._height(node.left), self._height(node.right))

    def _balance_factor(self, node: "_Node | None") -> int:
        return 0 if node is None else self._height(node.left) - self._height(node.right)

    def _rotate_right(self, y: "_Node") -> "_Node":
        x = y.left
        t2 = x.right
        x.right = y
        y.left = t2
        self._update_height(y)
        self._update_height(x)
        return x

    def _rotate_left(self, x: "_Node") -> "_Node":
        y = x.right
        t2 = y.left
        y.left = x
        x.right = t2
        self._update_height(x)
        self._update_height(y)
        return y

    def _rebalance(self, node: "_Node") -> "_Node":
        self._update_height(node)
        bf = self._balance_factor(node)

        if bf > 1:
            if self._balance_factor(node.left) < 0:
                node.left = self._rotate_left(node.left)
            return self._rotate_right(node)

        if bf < -1:
            if self._balance_factor(node.right) > 0:
                node.right = self._rotate_right(node.right)
            return self._rotate_left(node)

        return node

    def _insert(self, node: "_Node | None", key: int) -> "_Node":
        if node is None:
            return AVLTree._Node(key)
        if key < node.key:
            node.left = self._insert(node.left, key)
        elif key > node.key:
            node.right = self._insert(node.right, key)
        else:
            return node
        return self._rebalance(node)

    def _min_node(self, node: "_Node") -> "_Node":
        cur = node
        while cur.left is not None:
            cur = cur.left
        return cur

    def _delete(self, node: "_Node | None", key: int) -> "_Node | None":
        if node is None:
            return None
        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            succ = self._min_node(node.right)
            node.key = succ.key
            node.right = self._delete(node.right, succ.key)
        return self._rebalance(node)

    def insert(self, key: int) -> None:
        self._root = self._insert(self._root, key)

    def delete(self, key: int) -> bool:
        if not self.contains(key):
            return False
        self._root = self._delete(self._root, key)
        return True

    def _contains(self, node: "_Node | None", key: int) -> bool:
        if node is None:
            return False
        if key < node.key:
            return self._contains(node.left, key)
        if key > node.key:
            return self._contains(node.right, key)
        return True

    def contains(self, key: int) -> bool:
        return self._contains(self._root, key)

    def _in_order(self, node: "_Node | None", out: list) -> None:
        if node is None:
            return
        self._in_order(node.left, out)
        out.append(node.key)
        self._in_order(node.right, out)

    def in_order(self) -> list:
        result: list = []
        self._in_order(self._root, result)
        return result