# Algorithms Index

A curated reference of algorithms implemented in this repository. Use this index to locate the right algorithm for a given problem and to understand its complexity characteristics.

## How to Use This Index

Each entry follows a consistent structure:

- **Name** — the canonical algorithm name
- **Module** — the import path in this repository
- **Time** — worst-case time complexity
- **Space** — auxiliary space complexity
- **Stable** — whether the algorithm preserves the relative order of equal elements
- **Notes** — caveats, when to prefer it, or links to deeper documentation

Complexity notation: `n` is the input size, `k` is the range of input values, and `V`/`E` are the vertex/edge counts of a graph.

---

## Sorting

| Name | Module | Time (avg) | Time (worst) | Space | Stable | Notes |
|---|---|---|---|---|---|---|
| Timsort | `algorithms.sorting.timsort` | `O(n log n)` | `O(n log n)` | `O(n)` | Yes | Default in CPython. Adaptive on partially sorted data. |
| Quicksort | `algorithms.sorting.quicksort` | `O(n log n)` | `O(n^2)` | `O(log n)` | No | Prefer Lomuto for simple partitions, Hoare for fewer swaps. |
| Mergesort | `algorithms.sorting.mergesort` | `O(n log n)` | `O(n log n)` | `O(n)` | Yes | Preferred when stability is required. |
| Heapsort | `algorithms.sorting.heapsort` | `O(n log n)` | `O(n log n)` | `O(1)` | No | In-place; useful when memory is constrained. |
| Introsort | `algorithms.sorting.introsort` | `O(n log n)` | `O(n log n)` | `O(log n)` | No | Hybrid used by `list.sort()` in some runtimes. |
| Radix Sort (LSD) | `algorithms.sorting.radix_lsd` | `O(n * k)` | `O(n * k)` | `O(n + k)` | Yes | Linear for fixed-width integer keys. |
| Counting Sort | `algorithms.sorting.counting_sort` | `O(n + k)` | `O(n + k)` | `O(k)` | Yes | Only viable for small `k`. |
| Bucket Sort | `algorithms.sorting.bucket_sort` | `O(n + k)` | `O(n^2)` | `O(n + k)` | Yes | Performance depends on input distribution. |

## Searching

| Name | Module | Time (avg) | Time (worst) | Space | Notes |
|---|---|---|---|---|---|
| Binary Search | `algorithms.searching.binary_search` | `O(log n)` | `O(log n)` | `O(1)` | Requires a sorted, indexable sequence. |
| Interpolation Search | `algorithms.searching.interpolation_search` | `O(log log n)` | `O(n)` | `O(1)` | Best on uniformly distributed numeric data. |
| Jump Search | `algorithms.searching.jump_search` | `O(sqrt(n))` | `O(sqrt(n))` | `O(1)` | Trade-off between linear and binary search. |
| Exponential Search | `algorithms.searching.exponential_search` | `O(log n)` | `O(log n)` | `O(1)` | Useful for unbounded or stream-like inputs. |
| Ternary Search | `algorithms.searching.ternary_search` | `O(log_3 n)` | `O(log_3 n)` | `O(1)` | For unimodal functions, not sorted arrays. |

## Graph Algorithms

| Name | Module | Time | Space | Notes |
|---|---|---|---|---|
| BFS | `algorithms.graph.bfs` | `O(V + E)` | `O(V)` | Shortest path in unweighted graphs. |
| DFS (iterative) | `algorithms.graph.dfs` | `O(V + E)` | `O(V)` | Iterative variant to avoid recursion limits. |
| Dijkstra | `algorithms.graph.dijkstra` | `O((V + E) log V)` | `O(V)` | Non-negative weights only. |
| Bellman–Ford | `algorithms.graph.bellman_ford` | `O(V * E)` | `O(V)` | Detects negative-weight cycles. |
| Floyd–Warshall | `algorithms.graph.floyd_warshall` | `O(V^3)` | `O(V^2)` | All-pairs shortest paths. |
| A* | `algorithms.graph.a_star` | `O(E log V)` | `O(V)` | Heuristic-guided; admissibility required for optimality. |
| Topological Sort | `algorithms.graph.topological_sort` | `O(V + E)` | `O(V)` | Kahn's algorithm and DFS variants included. |
| Kruskal's MST | `algorithms.graph.kruskal` | `O(E log E)` | `O(V)` | Uses a disjoint-set / union-find structure. |
| Prim's MST | `algorithms.graph.prim` | `O(E log V)` | `O(V)` | Better for dense graphs with a binary heap. |
| Tarjan's SCC | `algorithms.graph.tarjan_scc` | `O(V + E)` | `O(V)` | Strongly connected components in one pass. |
| Kosaraju's SCC | `algorithms.graph.kosaraju_scc` | `O(V + E)` | `O(V)` | Two-pass DFS; often simpler to implement. |

## Dynamic Programming

| Name | Module | Time | Space | Notes |
|---|---|---|---|---|
| Longest Common Subsequence | `algorithms.dp.lcs` | `O(m * n)` | `O(min(m, n))` | Space-optimized variant included. |
| Knapsack (0/1) | `algorithms.dp.knapsack_01` | `O(n * W)` | `O(W)` | One-dimensional rolling array. |
| Unbounded Knapsack | `algorithms.dp.knapsack_unbounded` | `O(n * W)` | `O(W)` | Allows reuse of items. |
| Edit Distance (Levenshtein) | `algorithms.dp.edit_distance` | `O(m * n)` | `O(min(m, n))` | Variants for Damerau also provided. |
| Coin Change | `algorithms.dp.coin_change` | `O(n * amount)` | `O(amount)` | Min coins and count-ways flavors. |
| Matrix Chain Multiplication | `algorithms.dp.matrix_chain` | `O(n^3)` | `O(n^2)` | Knuth/Yao optimizations noted. |
| Longest Increasing Subsequence | `algorithms.dp.lis` | `O(n log n)` | `O(n)` | Patience-sorting variant. |

## String Algorithms

| Name | Module | Time | Space | Notes |
|---|---|---|---|---|
| KMP | `algorithms.string.kmp` | `O(n + m)` | `O(m)` | Failure-function based. |
| Rabin–Karp | `algorithms.string.rabin_karp` | `O(n + m)` avg | `O(1)` | Rolling hash; collision risk acknowledged. |
| Z-Algorithm | `algorithms.string.z_algorithm` | `O(n + m)` | `O(n + m)` | Clean alternative to KMP. |
| Manacher | `algorithms.string.manacher` | `O(n)` | `O(n)` | Longest palindromic substring. |
| Suffix Array (SA-IS) | `algorithms.string.suffix_array` | `O(n)` | `O(n)` | Linear-time construction. |
| Aho–Corasick | `algorithms.string.aho_corasick` | `O(n + m + z)` | `O(m * sigma)` | Multi-pattern matching. |

## Trees and Heaps

| Name | Module | Time (avg) | Time (worst) | Space | Notes |
|---|---|---|---|---|---|
| Binary Search Tree | `algorithms.trees.bst` | `O(log n)` | `O(n)` | Self-balancing variants (AVL, Red–Black) included. |
| AVL Tree | `algorithms.trees.avl` | `O(log n)` | `O(log n)` | Strictly balanced; more rotations than Red–Black. |
| Red–Black Tree | `algorithms.trees.red_black` | `O(log n)` | `O(log n)` | Used in many standard-library map/set implementations. |
| Binary Heap | `algorithms.trees.binary_heap` | `O(log n)` push/pop | — | `O(1)` peek. |
| Trie | `algorithms.trees.trie` | `O(L)` | `O(L)` | `L` is key length. |
| Segment Tree | `algorithms.trees.segment_tree` | `O(log n)` query/update | — | Range queries with point updates. |
| Fenwick Tree (BIT) | `algorithms.trees.fenwick` | `O(log n)` query/update | — | Prefix-sum friendly. |

## Mathematical and Number-Theoretic

| Name | Module | Time | Space | Notes |
|---|---|---|---|---|
| Sieve of Eratosthenes | `algorithms.math.sieve` | `O(n log log n)` | `O(n)` | Segmented variant for large `n`. |
| Extended Euclidean | `algorithms.math.extended_gcd` | `O(log min(a, b))` | `O(1)` | Returns Bézout coefficients. |
| Modular Exponentiation | `algorithms.math.mod_pow` | `O(log exp)` | `O(1)` | Square-and-multiply. |
| Fast Fourier Transform | `algorithms.math.fft` | `O(n log n)` | `O(n)` | Iterative Cooley–Tukey implementation. |
| Karatsuba Multiplication | `algorithms.math.karatsuba` | `O(n^1.585)` | `O(n)` | Outperforms grade-school above ~100 digits. |

## Greedy and Selection

| Name | Module | Time | Space | Notes |
|---|---|---|---|---|
| Quickselect | `algorithms.selection.quickselect` | `O(n)` avg | `O(n)` worst | `k`-th smallest in expected linear time. |
| Median of Medians | `algorithms.selection.median_of_medians` | `O(n)` | `O(n)` | Deterministic linear selection. |
| Activity Selection | `algorithms.greedy.activity_selection` | `O(n log n)` | `O(1)` | Sort by finish time. |
| Huffman Coding | `algorithms.greedy.huffman` | `O(n log n)` | `O(n)` | Min-heap based. |

## Cryptographic Primitives

> These implementations are provided for educational and prototyping use. Do not use them as the basis of a production security system; rely on vetted libraries (e.g., `cryptography`, `hashlib` with a strong KDF).

| Name | Module | Time | Space | Notes |
|---|---|---|---|---|
| SHA-256 | `algorithms.crypto.sha256` | `O(n)` | `O(1)` | Reference implementation; not constant-time. |
| RSA (textbook) | `algorithms.crypto.rsa` | `O(log n^3)` | `O(1)` | Demonstrates the algorithm only. |
| Diffie–Hellman | `algorithms.crypto.diffie_hellman` | `O(log p)` | `O(1)` | Demonstrates key exchange only. |

## Randomized Algorithms

| Name | Module | Time (avg) | Time (worst) | Space | Notes |
|---|---|---|---|---|---|
| Reservoir Sampling | `algorithms.randomized.reservoir` | `O(n)` | `O(n)` | `O(k)` memory for a sample of size `k`. |
| Bloom Filter | `algorithms.randomized.bloom` | `O(1)` | — | Configurable false-positive rate. |
| Skip List | `algorithms.randomized.skip_list` | `O(log n)` | `O(n)` | Probabilistic balance. |

## Parallel and Approximation

| Name | Module | Time | Space | Notes |
|---|---|---|---|---|
| Merge Sort (parallel) | `algorithms.parallel.merge_sort_par` | `O(n log n / p)` | `O(n)` | `p` is the number of workers. |
| 2-Approx Vertex Cover | `algorithms.approx.vertex_cover` | `O(V + E)` | `O(V)` | Greedy maximal matching based. |
| Simulated Annealing | `algorithms.approx.simulated_annealing` | Problem-dependent | `O(1)` | Tune cooling schedule per problem. |

---

## Conventions

- **Pure functions** are preferred. Algorithms return new collections rather than mutating inputs unless explicitly noted.
- **Type hints** are required on all public APIs. New code should pass `mypy --strict`.
- **Tests** live next to the implementation as `test_<module>.py` and include randomized property tests via `hypothesis` where appropriate.
- **No external runtime dependencies** for the core `algorithms` package. Optional helpers may live in `algorithms.contrib`.

## Adding a New Algorithm

1. Place the implementation in the appropriate submodule; create the submodule if it does not exist.
2. Add an entry to this index in the correct category. Keep the table format consistent.
3. Include doctests in the module docstring that double as documentation and smoke tests.
4. Add unit tests covering edge cases: empty input, single element, duplicate values, and adversarial inputs.
5. Run `make lint test` before opening a pull request.

## See Also

- `docs/complexity_cheatsheet.md` — a printable Big-O reference.
- `docs/data_structures_index.md` — companion index for data structures.
- `CONTRIBUTING.md` — coding standards and review process.