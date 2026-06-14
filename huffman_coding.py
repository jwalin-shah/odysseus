import heapq
from collections import Counter


class _Node:
    __slots__ = ("char", "freq", "left", "right")

    def __init__(self, char=None, freq=0, left=None, right=None):
        self.char = char
        self.freq = freq
        self.left = left
        self.right = right

    def __lt__(self, other):
        return self.freq < other.freq


def _build_tree(text):
    if not text:
        return None
    freq = Counter(text)
    heap = [_Node(char=c, freq=f) for c, f in freq.items()]
    heapq.heapify(heap)
    if len(heap) == 1:
        node = heap[0]
        return _Node(freq=node.freq, left=node, right=_Node(freq=0))
    while len(heap) > 1:
        left = heapq.heappop(heap)
        right = heapq.heappop(heap)
        parent = _Node(freq=left.freq + right.freq, left=left, right=right)
        heapq.heappush(heap, parent)
    return heap[0]


def _build_code_map(root):
    code_map = {}

    def dfs(node, prefix):
        if node is None:
            return
        if node.char is not None:
            code_map[node.char] = prefix or "0"
            return
        dfs(node.left, prefix + "0")
        dfs(node.right, prefix + "1")

    dfs(root, "")
    return code_map


def encode(text):
    """Encode text using Huffman coding. Returns (encoded_string, code_map)."""
    if not text:
        return "", {}
    root = _build_tree(text)
    code_map = _build_code_map(root)
    encoded = "".join(code_map[ch] for ch in text)
    return encoded, code_map


def decode(encoded, code_map):
    """Decode an encoded string using the provided code_map."""
    if not encoded or not code_map:
        return ""
    reverse_map = {code: ch for ch, code in code_map.items()}
    result = []
    current = []
    for bit in encoded:
        current.append(bit)
        key = "".join(current)
        if key in reverse_map:
            result.append(reverse_map[key])
            current = []
    if current:
        return "".join(result) + reverse_map.get("".join(current), "")
    return "".join(result)