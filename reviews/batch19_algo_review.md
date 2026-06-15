# Batch 19 Algorithm Review

**Files reviewed:** `graph_dp.py`, `binary_lifting.py`, `two_sat.py`, `disjoint_set_advanced.py`, `treap_implicit.py`

**Reviewer scope:** Correctness, asymptotic complexity, edge cases, API ergonomics, and production readiness of each module.

---

## Executive Summary

| Module | Verdict | One-line summary |
|---|---|---|
| `graph_dp.py` | Functional, minor cleanup needed | Four classic graph-DP algorithms, correct but contains dead code and weak type hints. |
| `binary_lifting.py` | Correct, but with subtle robustness concerns | Solid LCA / k-th-ancestor / path-max; DFS is iterative but the *find* in `PathQuery` uses the *node-key* assumption which can break on non-contiguous vertex sets. |
| `two_sat.py` | Correct, ergonomics poor | Three redundant clause APIs, recursive Kosaraju that can hit the recursion limit on large instances. |
| `disjoint_set_advanced.py` | High quality | Textbook implementations of rollback / bipartite / weighted DSU; all correct. |
| `treap_implicit.py` | Correct, with a few edge-case gaps | Implicit treap with reversal lazy and sum/size aggregation; the `pop_back` and `get` paths have soft corner cases. |

Overall, every algorithm in this batch is **algorithmically correct** for its stated contract. Production hardening (typing, recursion depth, deterministic randomness, doctests, de-duplicated APIs) is the dominant theme.

---

## 1. `graph_dp.py`

### 1.1 `tsp_dp(dist)` — Held–Karp TSP

- **Algorithm.** Standard bitmask DP: `dp[mask][u]` is the minimum cost of a path starting at vertex 0, visiting exactly the vertices in `mask` and ending at `u`. Final answer adds the return edge to 0.
- **Complexity.** `O(n² · 2ⁿ)` time, `O(n · 2ⁿ)` memory. Practical for `n ≤ ~18`–20.
- **Correctness.**
  - Initialisation: `dp[1][0] = 0` (start with only vertex 0 visited, at vertex 0). Correct.
  - Transition only fires when `u` is in `mask` (line 19 guard), which is correct.
  - Final `min(... + dist[v][0])` correctly closes the tour.
  - Edge case `n == 0` and `n == 1` returns 0. The `n == 1` case is technically a degenerate "tour" of length 0 — fine for callers, but a docstring note would help.
- **Issues.**
  - `INF = float('inf')` is defined and never used.
  - Type hints are weak: `dist: list[list]` should be `list[list[float]]` and return type `int | float` is not annotated.
  - The function assumes a *complete* graph. If `dist[u][v] == inf` the answer will be `inf`, which is correct behaviour, but no input validation exists.
  - Memory is allocated eagerly for all masks; for `n = 22` that is ~180 MB. No streaming option.
- **Production readiness.** Medium. Algorithm is correct; the surrounding code is academic-quality. Add type hints, drop `INF`, and consider a sentinel-based version for very large `n`.

### 1.2 `count_hamiltonian_paths(adj, n)`

- **Algorithm.** Bitmask DP counting directed Hamiltonian *paths* (no requirement to return to start).
- **Complexity.** `O(n² · 2ⁿ)` time, `O(n · 2ⁿ)` memory.
- **Correctness.**
  - Base: `dp[1 << i][i] = 1` for all `i`. Correct.
  - Transition: from each `(mask, u)` with `u ∈ mask`, add to `(mask ∪ {v}, v)` for every `v ∈ adj[u]` with `v ∉ mask`. Correct.
  - Final sum over `dp[full]` is correct.
- **Issues.**
  - `INF` is defined and unused.
  - No check that `n == len(adj)` — the caller can lie. Should validate.
  - The function does *not* count Hamiltonian *cycles*. Worth documenting (docstring says "Hamiltonian paths" which matches, but users sometimes expect cycles).
  - If `n` exceeds ~22 the table blows up the heap.

### 1.3 `min_path_cover_dag(adj, n)`

- **Algorithm.** Dilworth's theorem: minimum path cover of a DAG = `n − |maximum matching|` in the bipartite graph `(U, V, E)` where `U = V = vertices` and `(u, v) ∈ E` iff `(u, v) ∈ adj`. Implemented as a standard augmenting-path Hopcroft-style matcher (actually a single augmenting path per vertex, equivalent to Kuhn).
- **Complexity.** `O(V · E)` worst case for Kuhn.
- **Correctness.**
  - The function relies on the bipartite structure `U` and `V` both being `[0, n)` with the same indices. This is the standard formulation for the DAG path-cover reduction, so the implementation is correct *given* the caller supplies a DAG with edges in that form.
  - Docstring does not call out that this requires a DAG. Acyclic input is the invariant the reduction relies on.
- **Issues.**
  - The function silently treats non-DAG inputs (cycles) as DAGs and produces an undercount.
  - Should be split into two vertex sets explicitly for clarity, or at least a docstring note.
  - The two match arrays `match_l` and `match_r` are kept; this is fine but slightly over-engineered for a one-sided Kuhn.

### 1.4 `tree_dp_independent_set(adj, root)`

- **Algorithm.** Tree MIS with the standard two-state DP: `include` and `exclude` returned per subtree.
- **Complexity.** `O(V + E)`.
- **Correctness.**
  - Recurrence is correct: if `u` is included, children are excluded; if `u` is excluded, children take the better of their two states.
  - `dfs` is recursive — for deep or skewed trees this will hit Python's recursion limit (default 1000). The tree is not required to be balanced, so this is a real concern (a path on 10 000 vertices will stack-overflow).
- **Issues.**
  - Recursive DFS with no `sys.setrecursionlimit` call.
  - `from collections import defaultdict` is imported inside the function and never used.
  - `adj: dict` is loosely typed; should be `dict[int, list[int]]`.
  - The function does not verify that `root` actually exists in `adj` or that the tree is connected; if not, the "tree" assumption is violated.
  - For very deep trees, an iterative post-order traversal is safer than recursion.

### 1.5 Cross-cutting issues in `graph_dp.py`

- Lint cleanups: remove `INF` constants and unused `import` inside `tree_dp_independent_set`.
- Add a module-level docstring summarising what is offered.
- Provide a few sanity tests (a 3-city TSP, a 2-vertex path cover, a small tree MIS).

---

## 2. `binary_lifting.py`

### 2.1 `BinaryLifting.build(adj, root)`

- **Algorithm.** Iterative DFS to fill depth and parent arrays, then build a `log × n` ancestor table.
- **Correctness.**
  - DFS is iterative with an explicit stack; the `vi != p and depth[vi] == -1` guard prevents revisiting the parent in undirected inputs and re-entering a visited subtree.
  - `up[0][i] = parent[i] if parent[i] != -1 else i` self-loops the root so that `kth_ancestor` and `lca` work even if `k` exceeds the depth.
  - The internal table indexing uses `node_idx` — a dictionary mapping `node` → `0..n-1`. This is required because the module supports *arbitrary hashable* node labels.
- **Issues.**
  - The DFS uses `vi != p`, but `p` is the *index* of the parent node, not the key. Then it compares `vi != p`. Since `vi` and `p` are both indices (and `p` was set to `ui` for the child), this is consistent. But the variable naming is confusing — `p` looks like a *node* and `vi`/`ui` look like indices.
  - The internal `parent[vi] = ui` then `up[0][i] = parent[i] if parent[i] != -1 else i` handles the root. But after the *iterative* DFS, the root's `parent[r]` is `-1`, so it self-loops via `i`. Subsequent levels: `up[k][r] = up[k-1][up[k-1][r]] = up[k-1][r] = ... = r`. Correct.
  - There is no detection of *disconnected* nodes: if `adj` does not include all vertices, those vertices will have `depth == -1` and the tables will have undefined behaviour on lookup.
  - The module adds attributes `_node_idx` and `_nodes` inside `build` (and not in `__init__`), so any `BinaryLifting()` instance used *before* `build` will raise `AttributeError` on `_idx`/`_depth`. This is a minor API design smell — initialise them in `__init__` for clarity.

### 2.2 `kth_ancestor(u, k)`

- **Complexity.** `O(log n)`.
- **Correctness.** Walks bits of `k` from LSB to MSB, jumping `up[b][current]`. Self-loop at the root means over-shoots clamp to the root. Correct.
- **Notes.** No upper bound on `k`; if `k > depth(u)`, the result is the root, which is the standard convention. Document this.

### 2.3 `lca(u, v)` and `_lca_idx(ui, vi)`

- **Algorithm.** Equalise depths, then lift both nodes together from the highest bit down until their ancestors diverge; return the parent of those.
- **Correctness.** Standard and correct. Loop bound `range(self._log, -1, -1)` is inclusive of bit 0.
- **Issues.**
  - The depth-equalising loop walks `range(self._log + 1)` which is inclusive of `self._log` (the highest possible bit). When the depth difference has that bit set, it lifts by `up[log]`. This works because the ancestor table has `log + 1` levels, and `up[log][x]` is the `(2^log)`-th ancestor (the root for any node). Correct.
  - Code duplication: `lca` and `_lca_idx` repeat the same logic. `_lca_idx` could be the primary and `lca` could be a thin wrapper.

### 2.4 `dist(u, v)`

- **Complexity.** `O(log n)`.
- **Correctness.** `depth[u] + depth[v] − 2 · depth[lca]`. Standard.
- **Note.** Returns an `int`, but the underlying depths are stored as Python ints — fine.

### 2.5 `PathQuery.build_weighted(adj, root, edge_weights)`

- **Correctness.**
  - For each edge `(u, v)` the weight is stored at the *child* node (the one with `depth = depth[parent] + 1`). This is the standard "lift-max" arrangement.
  - If the graph is undirected and both `(u, v)` and `(v, u)` keys exist, the `edge_weights.get((u, v), edge_weights.get((v, u), 0))` falls back. If the caller supplies only one direction with a directed key, the symmetric lookup still finds it. This is reasonable but worth a docstring.
  - The inner loop `if self._depth[ni[v]] == self._depth[ni[u]] + 1` checks that `v` is a *child* of `u`. For undirected inputs this is correct *if* the tree was rooted; for directed or self-looped graphs, the check is necessary.
- **Issues.**
  - If `edge_weights` is missing for an edge, the code silently uses 0 — this can mask a real bug. Default-to-0 may also produce a wrong *max* (no signal that 0 is a placeholder).
  - `self._max_up` is initialised in `__init__` to `[]` which is fine but only after a build will queries be valid.

### 2.6 `PathQuery.path_max(u, v)`

- **Algorithm.** Lift `u` and `v` to their LCA separately, tracking the running max via the stored edge weights.
- **Correctness.**
  - `lift_max(node_i, anc_i)` consumes the depth difference, and at each bit set, takes the max with `max_up[b][node_i]` and then jumps. Correct.
  - The edge at the LCA is *not* included, but the *path* between `u` and `v` excludes edges incident to the LCA (or rather, the edges from each child of the LCA down to the vertex). This is the standard behaviour.
- **Issues.**
  - Inner function `lift_max` uses `nonlocal result`. Clean but a class-level field would be marginally faster.
  - If `u == v`, the answer is `-1` (the initial `result`). This is technically a valid "no edges" answer, but should be documented.

### 2.7 Production readiness notes

- The two classes share a lot of logic; `PathQuery` could *contain* a `BinaryLifting` rather than inheriting, removing the artificial inheritance.
- The `node_idx` indirection adds a per-query dict lookup; for hot paths, return the index directly from the public API or accept indices.
- `math` is imported but unused.
- No tests, no doctests, no example.

---

## 3. `two_sat.py`

### 3.1 API surface

There are **three** ways to add a clause:

| Method | Variable convention | Negation convention |
|---|---|---|
| `add_clause(u, v)` | 0-indexed | signed: `u < 0` means `¬x_{-u-1}` |
| `add_clause_old(u, nu, v, nv)` | 0-indexed | boolean flag |
| `add_clause_lit(u, v)` | 1-indexed | signed: `u < 0` means `¬x_{-u}` |

This is confusing and error-prone. `add_clause_old` is dead code by naming and should be removed or renamed (`add_clause_pair`). `add_clause` and `add_clause_lit` should be unified.

### 3.2 `solve()`

- **Algorithm.** Kosaraju's SCC: forward DFS to compute post-order, then reverse DFS to label components in reverse post-order. Variable `i` is assigned `True` iff `comp[2i] > comp[2i+1]` (component order is reverse topological).
- **Complexity.** `O(V + E) = O(n + m)`.
- **Correctness.**
  - `visited` and `comp` are sized `2n`, matching the literal graph.
  - The `comp[2i] > comp[2i+1]` test relies on the fact that in Kosaraju the *first* SCC found in the reversed traversal gets a *smaller* label. The assignment rule is the standard one: pick the assignment such that the *true* literal is in the earlier SCC.
  - The `setrecursionlimit(10000)` is a hint that the author is aware of the recursion problem, but 10 000 is insufficient for, e.g., `n = 100 000`.
- **Issues.**
  - **Recursion in DFS.** This is the biggest production-readiness issue. For `n` above a few thousand the interpreter will stack-overflow. An iterative Tarjan or iterative Kosaraju would be safer.
  - The `sys` import is inside `solve` and the recursion limit is set *per-call*; if the user bumps the limit elsewhere, this resets it.
  - The class is *not* re-entrant: after `solve()` returns, the graph state is still there; you can't re-solve without rebuilding. Not a bug, but worth documenting.
  - There is no way to extract the raw component IDs or the assignment as a `{var: bool}` dict — only a `list[bool]` of length `n`.

### 3.3 `add_implication(u, v)` and `at_most_one(vars)`

- `add_implication` correctly reduces to `add_clause_lit(-u, v)`. Logical equivalence is correct: `u ⇒ v` is `¬u ∨ v`.
- `at_most_one` is the quadratic `O(k²)` encoding via pairwise `¬xᵢ ∨ ¬xⱼ`. Correct, but for `k > ~500` this generates tens of thousands of clauses; mention the linear encoding via auxiliary variables (Tseitin) for large `k`.
- `at_most_one` doesn't accept a list of 1-indexed or 0-indexed variables, but uses whatever convention the caller chose (it calls `add_clause_lit`, so it's 1-indexed). Inconsistent with `add_clause` (0-indexed) on the same class.

### 3.4 Production readiness notes

- Pick **one** clause-adding API and remove the others; document the convention.
- Replace recursive SCC with iterative Tarjan (single-pass, naturally iterative, smaller constant).
- Add `__repr__` and a `status` flag (`SAT` / `UNSAT`).
- Provide a `get_assignment(var: int) -> bool` accessor.
- Add type hints (`n: int`, `clause: tuple[int, int]`, `result: list[bool] | None`).

---

## 4. `disjoint_set_advanced.py`

### 4.1 `DSUWithRollback`

- **Algorithm.** Union by rank, **no** path compression (required for rollback to be correct).
- **Correctness.**
  - History entries are tuples `(child, old_parent, parent_root, old_rank_parent_root)`. On `rollback`, the child's parent is restored and the parent's rank is decremented if it was bumped.
  - No-op unions (already same component) push `None` and the rollback is a no-op. Correct, but a uniform history entry would simplify the loop in `rollback` (always pop, always restore `None`).
- **Complexity.** `α(n)` amortised per op (without path compression it's `O(log n)` by rank); rollback is `O(1)`.
- **Issues.**
  - No snapshot/level API for *batch* rollback across multiple unions. Most use cases (offline connectivity, Mo's algorithm) need a `snapshot()` that returns a marker and a `rollback_to(snapshot)` that pops back to it. This is a notable omission for a "rollback" DSU.
  - The class is small; an `_undo_stack` of three-tuples `(child, parent, delta_rank)` would be slightly cleaner.
  - No type hints, no `__repr__`, no `__len__` (component count), no `size(x)` helper.

### 4.2 `DSUBipartite`

- **Algorithm.** Augmented DSU with a parity bit per node; parity of `x` to its root is the "colour difference".
- **Correctness.**
  - `find` is recursive but bounded by tree height (no path compression, but union by rank keeps it `O(log n)`).
  - `parity[x] ^= parity[parent[x]]` on the unwind accumulates the parity. After path compression, `parent[x] = root` and the cumulative parity is stored in `parity[x]`. Standard implementation.
  - `union` sets `parity[rv] = pu ^ pv ^ 1`, meaning the *new* edge between `u` and `v` has parity 1 (different sides). Correct.
  - When `ru == rv` and `pu == pv`, the same-edge check fires `odd_cycle`. Correct.
- **Issues.**
  - `find` is recursive; for skewed input without path compression, depth can be `O(log n)` but with `n = 2^20` and a star graph it stays at 1. In practice safe; but a non-recursive `find` would be more robust.
  - `is_bipartite()` is a one-shot flag; for streaming you can call `union` then check. This is fine.
  - No way to *get* the colour of a node, only check bipartiteness. The `find` returns `(root, parity)` so a public `color(x)` would be a one-liner addition.

### 4.3 `WeightedDSU`

- **Algorithm.** Weighted DSU: `weight[x]` is `w(x) − w(root)`. `diff(u, v)` returns `w(v) − w(u)` if same component.
- **Correctness.**
  - `find` accumulates `weight[x] += weight[parent[x]]` and compresses. Standard.
  - `union(u, v, w)` with `w = w(v) − w(u)`. When ranks are swapped, the sign of `w` is flipped, and `wu, wv` are swapped. Correct.
  - `weight[rv] = wu − wv + w` correctly sets the new parent pointer's weight to satisfy the constraint.
- **Issues.**
  - `diff` raises `ValueError` if components differ — good, but the type hints are weak.
  - Recursive `find` (same caveat as bipartite).
  - No way to query the *value* of a single node (only differences). A `potential(x)` that returns the absolute value (assuming `w(0) = 0` for the root) is often useful.

### 4.4 Production readiness notes

- All three classes are correct and follow the standard textbook implementations.
- Add a `Snapshot` mechanism to `DSUWithRollback` — currently it's the most common feature missing.
- Type hints (`n: int`, `x: int`, `w: int`) and `__slots__` would tighten the module.
- `from __future__ import annotations` is present, good.

---

## 5. `treap_implicit.py`

### 5.1 Node structure and lazy state

- `_Node` uses `__slots__` for memory efficiency — good.
- Fields: `val`, `pri` (priority), `size`, `sum` (subtree sum), `rev` (lazy reversal flag), `left`, `right`.
- `_push` swaps children, propagates `rev` to children, clears flag. Correct.
- `_pull` recomputes `size` and `sum`. Reversal preserves both, so `_pull` is correct without first pushing.

### 5.2 `split(t, k)` and `merge(l, r)`

- **Correctness.**
  - `split(t, k)` returns `(left, right)` where `left` is the first `k` elements. `_push(t)` is called before descending, which is required for correctness when `t` has a pending reversal (a reversal inverts the order of `t.left`'s size relationship to `k`).
  - The recursion direction (`_size(t.left) >= k` vs `< k`) is standard.
- **Issues.**
  - `merge` calls `_push(l)` and `_push(r)` at the top. This is correct *only* if you don't expect children of `l` or `r` to carry reversal state at this point. After `_push`, `l` and `r` are "clean" at the root, but their children may still carry lazy flags. The recursive call `l.right = _merge(l.right, r)` *assumes* that `l.right` is clean — which is true because we just pushed `l`. ✓
  - `merge` *also* calls `_push` on `r` even when it is not the new root. Pushing `r` and then *not* using its structure (if `l.pri > r.pri`) is wasteful. Minor performance concern.

### 5.3 Public API

| Method | Behaviour | Notes |
|---|---|---|
| `push_back` | O(log n) | OK |
| `pop_back` | O(log n) | Splits at `n - 1`. If `n == 0` the `r` returned is `None` and `pop_back` returns `None`. Edge case handled. |
| `insert(pos, val)` | O(log n) | Splits at `pos`, merges a singleton. `pos` out of range is not validated. |
| `delete(pos)` | O(log n) | Standard. |
| `get(pos)` | O(log n) | Splits, extracts, *re-merges* — preserves the structure. Correct but does two splits and two merges. |
| `range_sum(l, r)` | O(log n) | Splits off `[0, l)` and `[r+1, n)`, returns the sum of the middle. |
| `range_reverse(l, r)` | O(log n) | Splits, toggles `rev` on the middle, re-merges. |

### 5.4 Edge cases and issues

- `pos` is not bounds-checked. `insert(0, x)` is valid; `insert(n, x)` appends; `insert(n + 1, x)` would put a node into the right tree (which is empty), effectively still appending — but `delete(n)` would split at `n`, then split the empty `r` at `1` (returns `None, None`), then merge `(l, None)` — works but the boundary semantics deserve a docstring.
- `pop_back` on an empty treap returns `None` rather than raising. The Python convention for `list.pop` is to raise `IndexError`. Inconsistent.
- `get(pos)` on an out-of-range `pos` returns `None` and the structure is *not* preserved correctly (the re-merge puts `None` back). A bit subtle — the structure is preserved because `_merge(l, None) = l`, so it works, but only by accident.
- `random.random()` is used for the priority. This is not deterministic across runs. For a competitive-programming setting this is usually fine, but a fixed seed (or `random.randint(0, 2**30)` with a seeded RNG) is preferable in production. Also, `random.random()` returns a `float`; using `random.getrandbits(30)` would be faster.
- The treap stores `val` as a generic Python object but the `sum` field requires `val` to support `+` with `0`. If `val` is a list or string, the sum will fail. Either document the constraint or specialise.

### 5.5 Production readiness notes

- Add `__len__` (`return _size(self._root)`) and `__iter__` (in-order traversal, possibly using a stack).
- Add bounds checks on `pos` and `r`.
- Replace `random.random()` with `random.getrandbits(30)` for speed.
- Consider supporting "min" or other monoids by parameterising the combine function.
- Consider an `apply(f, l, r)` (e.g. add-to-range) by adding an `add` lazy field. The current treap is "sum + reverse" only; a generic lazy propagation would be a natural extension.

---

## Cross-Module Observations

1. **Recursion depth.** `binary_lifting.build` is iterative, but `binary_lifting.find`-style code is *not* used; `DSUBipartite.find`, `WeightedDSU.find`, and `TwoSAT.solve` all use recursion. For production-scale inputs, an iterative version of each is safer.
2. **Type hints.** Only `from __future__ import annotations` is used; parameter and return types are mostly missing. Adding `n: int`, `u: int`, `list[bool] | None`, etc. would make the modules self-documenting and catch bugs with a type checker.
3. **Docstrings.** Most methods have at most a one-liner. Edge cases (empty input, disconnected, single element) are not enumerated. Test cases that exercise the docstring would clarify the contract.
4. **Determinism.** Only `treap_implicit.py` has randomness; making it seedable would help testing.
5. **Tests.** None of the five files have accompanying `*_test.py` modules or `if __name__ == "__main__":` smoke tests in this review scope.
6. **Code style.** Mixed: `disjoint_set_advanced.py` is the cleanest, `graph_dp.py` has dead code, `two_sat.py` has redundant APIs.

---

## Recommendations (prioritised)

1. **High** — In `two_sat.py`, replace recursive Kosaraju with iterative Tarjan and unify the three clause APIs.
2. **High** — In `disjoint_set_advanced.py`, add a `snapshot()` / `rollback_to(s)` API to `DSUWithRollback`.
3. **Medium** — In `graph_dp.py`, remove dead `INF` constants, the unused `defaultdict` import, and the recursive `dfs` in `tree_dp_independent_set`.
4. **Medium** — In `binary_lifting.py`, document that `node_idx` is set in `build` (not `__init__`), and add type hints.
5. **Medium** — In `treap_implicit.py`, bounds-check `pos`, raise `IndexError` on empty `pop_back`, switch to `random.getrandbits(30)`, add `__len__` and `__iter__`.
6. **Low** — In all five files, add type hints, doctests, and at least one example test per public function.

---

## Conclusion

All five modules are *algorithmically correct* for their stated contracts. The dominant gaps are *API ergonomics* (the three `add_clause*` variants, missing snapshot in rollback DSU), *recursion robustness* (TwoSAT, DSU finds), and *production hardening* (type hints, edge-case documentation, deterministic randomness, bounds checking). With the changes above, the batch would be ready for serious use.
