from collections import deque
from typing import List

def ladder_length(begin_word: str, end_word: str, word_list: List[str]) -> int:
    """
    Find the shortest word ladder transformation length from begin_word to end_word.

    A word ladder is a sequence of words where each word differs from the
    previous one by exactly one letter. This function returns the number of
    words in the shortest such sequence (including both begin_word and end_word),
    or 0 if no valid transformation exists.

    Parameters
    ----------
    begin_word : str
        The starting word of the transformation.
    end_word : str
        The target word of the transformation.
    word_list : List[str]
        The list of allowed intermediate words.

    Returns
    -------
    int
        The length of the shortest transformation sequence, or 0 if impossible.
    """
    word_set = set(word_list)
    if end_word not in word_set:
        return 0
    if begin_word == end_word:
        return 1

    queue = deque([(begin_word, 1)])
    visited = {begin_word}

    while queue:
        current_word, level = queue.popleft()
        if current_word == end_word:
            return level

        word_chars = list(current_word)
        for i in range(len(word_chars)):
            original_char = word_chars[i]
            for c in 'abcdefghijklmnopqrstuvwxyz':
                if c == original_char:
                    continue
                word_chars[i] = c
                next_word = ''.join(word_chars)
                if next_word in word_set and next_word not in visited:
                    if next_word == end_word:
                        return level + 1
                    visited.add(next_word)
                    queue.append((next_word, level + 1))
            word_chars[i] = original_char

    return 0


def all_ladders(begin_word: str, end_word: str, word_list: List[str]) -> List[List[str]]:
    """
    Find all shortest transformation sequences from begin_word to end_word.

    Parameters
    ----------
    begin_word : str
        The starting word of the transformation.
    end_word : str
        The target word of the transformation.
    word_list : List[str]
        The list of allowed intermediate words.

    Returns
    -------
    List[List[str]]
        A list of all shortest word ladder sequences.
    """
    word_set = set(word_list)
    if end_word not in word_set:
        return []

    # Build adjacency list using intermediate generic states.
    graph = {}
    visited = {begin_word}
    queue = deque([begin_word])

    while queue:
        word = queue.popleft()
        if word not in graph:
            graph[word] = []
        word_chars = list(word)
        for i in range(len(word_chars)):
            original_char = word_chars[i]
            for c in 'abcdefghijklmnopqrstuvwxyz':
                if c == original_char:
                    continue
                word_chars[i] = c
                new_word = ''.join(word_chars)
                if new_word in word_set:
                    if new_word not in visited:
                        visited.add(new_word)
                        queue.append(new_word)
                    graph.setdefault(word, []).append(new_word)
                    graph.setdefault(new_word, [])
            word_chars[i] = original_char

    # BFS to find shortest distance to each node from begin_word.
    distance = {begin_word: 1}
    bfs_queue = deque([begin_word])
    found_end = False
    while bfs_queue:
        word = bfs_queue.popleft()
        if word == end_word:
            found_end = True
            break
        for neighbor in graph.get(word, []):
            if neighbor not in distance:
                distance[neighbor] = distance[word] + 1
                bfs_queue.append(neighbor)

    if not found_end:
        return []

    # Backtrack to collect all shortest paths.
    results: List[List[str]] = []
    path = [begin_word]

    def backtrack(current: str) -> None:
        if current == end_word:
            results.append(list(path))
            return
        for neighbor in graph.get(current, []):
            if neighbor in distance and distance[neighbor] == distance[current] + 1:
                path.append(neighbor)
                backtrack(neighbor)
                path.pop()

    backtrack(begin_word)
    return results


if __name__ == "__main__":
    # Example usage / simple sanity check.
    begin = "hit"
    end = "cog"
    word_list = ["hot", "dot", "dog", "lot", "log", "cog"]
    length = ladder_length(begin, end, word_list)
    print(f"Shortest ladder length: {length}")
    all_paths = all_ladders(begin, end, word_list)
    print(f"All shortest ladders: {all_paths}")