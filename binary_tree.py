class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None


class BinarySearchTree:
    def __init__(self):
        self.root = None

    def insert(self, val):
        if self.root is None:
            self.root = Node(val)
            return True
        current = self.root
        while True:
            if val < current.val:
                if current.left is None:
                    current.left = Node(val)
                    return True
                current = current.left
            elif val > current.val:
                if current.right is None:
                    current.right = Node(val)
                    return True
                current = current.right
            else:
                return False

    def search(self, val):
        current = self.root
        while current is not None:
            if val < current.val:
                current = current.left
            elif val > current.val:
                current = current.right
            else:
                return True
        return False

    def delete(self, val):
        def _delete(node, val):
            if node is None:
                return None, False
            if val < node.val:
                node.left, deleted = _delete(node.left, val)
                return node, deleted
            elif val > node.val:
                node.right, deleted = _delete(node.right, val)
                return node, deleted
            else:
                if node.left is None and node.right is None:
                    return None, True
                if node.left is None:
                    return node.right, True
                if node.right is None:
                    return node.left, True
                successor = node.right
                while successor.left is not None:
                    successor = successor.left
                node.val = successor.val
                node.right, _ = _delete(node.right, successor.val)
                return node, True

        self.root, deleted = _delete(self.root, val)
        return deleted

    def inorder(self):
        result = []
        def _inorder(node):
            if node is None:
                return
            _inorder(node.left)
            result.append(node.val)
            _inorder(node.right)
        _inorder(self.root)
        return result

    def preorder(self):
        result = []
        def _preorder(node):
            if node is None:
                return
            result.append(node.val)
            _preorder(node.left)
            _preorder(node.right)
        _preorder(self.root)
        return result

    def postorder(self):
        result = []
        def _postorder(node):
            if node is None:
                return
            _postorder(node.left)
            _postorder(node.right)
            result.append(node.val)
        _postorder(self.root)
        return result

    def height(self):
        def _height(node):
            if node is None:
                return -1
            return 1 + max(_height(node.left), _height(node.right))
        return _height(self.root)

    def is_balanced(self):
        def _check(node):
            if node is None:
                return 0, True
            left_h, left_b = _check(node.left)
            right_h, right_b = _check(node.right)
            balanced = left_b and right_b and abs(left_h - right_h) <= 1
            return 1 + max(left_h, right_h), balanced
        _, balanced = _check(self.root)
        return balanced