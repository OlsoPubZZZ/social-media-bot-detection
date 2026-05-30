"""Community detection over the coordination graph.

A connected group of accounts can still contain several *distinct* rings that
happen to be bridged (e.g. they all dropped the same hashtag once). Splitting a
component into communities tells "one 40-account ring" apart from "four 10-account
rings", which changes how you read an amplification report.

Backends:
* **networkx** (the optional ``[graph]`` extra) — modularity-based
  ``greedy_modularity_communities``, which can split a *connected* graph.
* **stdlib fallback** — connected components (union-find). Each connected group
  is one community; the extra only ever *increases* resolution, never changes
  the core's behavior or its zero-dependency guarantee.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple

try:  # optional [graph] extra
    import networkx as _nx

    _HAS_NX = True
except ImportError:  # pragma: no cover - depends on whether the extra is installed
    _nx = None
    _HAS_NX = False


def _connected_components(edges: List[Tuple[str, str]]) -> List[Set[str]]:
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)

    groups: Dict[str, Set[str]] = {}
    for node in parent:
        groups.setdefault(find(node), set()).add(node)
    return list(groups.values())


def detect_communities(edges: Iterable[Tuple[str, str]]) -> List[Set[str]]:
    """Partition the nodes touched by ``edges`` into communities.

    Returns a list of node sets, sorted largest-first then lexicographically for
    determinism. Uses networkx modularity when available, else connected
    components.
    """
    clean = [(a, b) for a, b in edges if a != b]
    if not clean:
        return []

    if _HAS_NX:
        graph = _nx.Graph()
        graph.add_edges_from(clean)
        communities = _nx.community.greedy_modularity_communities(graph)
        result = [set(c) for c in communities]
    else:
        result = _connected_components(clean)

    return sorted(result, key=lambda c: (-len(c), sorted(c)))
