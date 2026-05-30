"""Community detection tests — stdlib fallback and the optional networkx backend."""

import pytest

import smbd.community as community
from smbd.community import detect_communities

# Two disjoint triangles.
_TWO_TRIANGLES = [("a", "b"), ("b", "c"), ("a", "c"), ("x", "y"), ("y", "z"), ("x", "z")]
# Barbell: two triangles joined by a single bridge edge (c—x).
_BARBELL = _TWO_TRIANGLES + [("c", "x")]


def test_empty():
    assert detect_communities([]) == []


def test_single_clique_is_one_community():
    assert len(detect_communities([("a", "b"), ("b", "c"), ("a", "c")])) == 1


def test_disjoint_cliques_split_in_both_backends():
    # Disjoint components are 2 communities regardless of backend.
    comms = detect_communities(_TWO_TRIANGLES)
    assert len(comms) == 2
    assert {frozenset(c) for c in comms} == {frozenset("abc"), frozenset("xyz")}


def test_results_sorted_largest_first():
    comms = detect_communities([("a", "b"), ("b", "c"), ("x", "y")])
    assert len(comms[0]) >= len(comms[-1])


def test_stdlib_fallback_treats_connected_graph_as_one(monkeypatch):
    # Force the no-networkx path: a connected barbell is a single community.
    monkeypatch.setattr(community, "_HAS_NX", False)
    assert len(detect_communities(_BARBELL)) == 1


def test_networkx_splits_a_connected_barbell():
    pytest.importorskip("networkx")
    if not community._HAS_NX:  # pragma: no cover - safety
        pytest.skip("networkx import flag not set")
    # Modularity should separate the two cliques despite the bridge edge.
    assert len(detect_communities(_BARBELL)) == 2
