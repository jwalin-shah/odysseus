import heapq


def dijkstra(graph: dict[str, dict[str, float]], start: str, end: str) -> tuple[float, list[str]]:
    if start not in graph or end not in graph:
        return (float('inf'), [])

    distances: dict[str, float] = {start: 0.0}
    previous: dict[str, str | None] = {start: None}
    heap: list[tuple[float, str]] = [(0.0, start)]
    visited: set[str] = set()

    while heap:
        current_distance, current_node = heapq.heappop(heap)

        if current_node in visited:
            continue
        visited.add(current_node)

        if current_node == end:
            path: list[str] = []
            node: str | None = end
            while node is not None:
                path.append(node)
                node = previous[node]
            path.reverse()
            return (current_distance, path)

        if current_distance > distances.get(current_node, float('inf')):
            continue

        for neighbor, weight in graph.get(current_node, {}).items():
            new_distance = current_distance + weight
            if new_distance < distances.get(neighbor, float('inf')):
                distances[neighbor] = new_distance
                previous[neighbor] = current_node
                heapq.heappush(heap, (new_distance, neighbor))

    return (float('inf'), [])