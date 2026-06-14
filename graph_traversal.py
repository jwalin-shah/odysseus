from collections import deque

def bfs(graph: dict, start) -> list:
    """Breadth-first search traversal starting from start node."""
    if start not in graph:
        return []
    visited = {start}
    result = []
    queue = deque([start])
    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return result

def dfs(graph: dict, start) -> list:
    """Depth-first search traversal starting from start node (iterative)."""
    if start not in graph:
        return []
    visited = set()
    result = []
    stack = [start]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        result.append(node)
        for neighbor in reversed(graph.get(node, [])):
            if neighbor not in visited:
                stack.append(neighbor)
    return result

def has_cycle_undirected(graph: dict) -> bool:
    """Check if an undirected graph has a cycle using DFS with parent tracking."""
    visited = set()

    def dfs_helper(node, parent):
        visited.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs_helper(neighbor, node):
                    return True
            elif neighbor != parent:
                return True
        return False

    for node in graph:
        if node not in visited:
            if dfs_helper(node, -1):
                return True
    return False

def has_cycle_directed(graph: dict) -> bool:
    """Check if a directed graph has a cycle using DFS with color marking."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {}

    def dfs_helper(node):
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if neighbor not in color:
                color[neighbor] = WHITE
            if color[neighbor] == GRAY:
                return True
            if color[neighbor] == WHITE:
                if dfs_helper(neighbor):
                    return True
        color[node] = BLACK
        return False

    for node in graph:
        if node not in color:
            color[node] = WHITE
        if color[node] == WHITE:
            if dfs_helper(node):
                return True
    return False