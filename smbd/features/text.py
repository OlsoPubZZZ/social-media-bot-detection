"""Text features — normalization, near-duplicate detection, URL/emoji density.

Pure stdlib so the core engine installs with zero dependencies. Embedding-based
similarity can be layered in later (optional extra) without changing callers.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Dict, List, Sequence

_URL_RE = re.compile(r"https?://\S+|www\.\S+|\b\S+\.(?:com|net|org|io|ly|me|link)\b", re.I)
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_text(text: str) -> str:
    """Lowercase, strip accents/punctuation, collapse whitespace.

    Used as the canonical key for exact-duplicate grouping.
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def url_count(text: str) -> int:
    return len(_URL_RE.findall(text))


def emoji_ratio(text: str) -> float:
    """Share of characters that are emoji/symbol (rough, stdlib-only)."""
    if not text:
        return 0.0
    emoji = sum(1 for c in text if unicodedata.category(c).startswith("S") or ord(c) > 0x1F000)
    return emoji / len(text)


def shingles(text: str, k: int = 3) -> List[str]:
    """Word k-shingles of normalized text (falls back to chars for short text)."""
    tokens = normalize_text(text).split()
    if len(tokens) < k:
        return tokens or list(normalize_text(text))
    return [" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)]


def _hash64(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")


def simhash(text: str, k: int = 3) -> int:
    """64-bit SimHash over k-shingles. Similar texts -> small hamming distance."""
    bits = [0] * 64
    grams = shingles(text, k)
    if not grams:
        return 0
    for gram in grams:
        h = _hash64(gram)
        for i in range(64):
            bits[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(64):
        if bits[i] > 0:
            out |= 1 << i
    return out


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def cluster_near_duplicates(
    texts: Dict[str, str],
    max_hamming: int = 6,
    min_chars: int = 4,
) -> List[List[str]]:
    """Group ids whose texts are (near-)duplicates.

    Strategy: bucket by exact normalized text first (cheap, catches copy-paste),
    then merge buckets whose simhashes are within ``max_hamming``. Returns a list
    of clusters, each a list of ids. Singletons are omitted.

    ``texts`` maps an opaque id -> raw text.
    """
    # Exact-normalized buckets.
    buckets: Dict[str, List[str]] = {}
    sims: Dict[str, int] = {}
    for cid, raw in texts.items():
        norm = normalize_text(raw)
        if len(norm) < min_chars:
            continue
        buckets.setdefault(norm, []).append(cid)
        if norm not in sims:
            sims[norm] = simhash(raw)

    norms = list(buckets.keys())
    # Union-find over near-duplicate buckets.
    parent = {n: n for n in norms}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        parent[find(x)] = find(y)

    for i in range(len(norms)):
        for j in range(i + 1, len(norms)):
            if hamming(sims[norms[i]], sims[norms[j]]) <= max_hamming:
                union(norms[i], norms[j])

    merged: Dict[str, List[str]] = {}
    for norm in norms:
        root = find(norm)
        merged.setdefault(root, []).extend(buckets[norm])

    return [ids for ids in merged.values() if len(ids) > 1]
