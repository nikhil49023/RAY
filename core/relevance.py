"""
relevance.py — Lightweight ReLU-style relevance reranking
---------------------------------------------------------
This reranker keeps only positive evidence contributions and boosts search
results that share more query terms, phrases, and domain hints.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Callable, Iterable, List


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "i", "in", "into", "is", "it", "of", "on", "or", "that", "the", "this",
    "to", "what", "when", "where", "which", "who", "why", "with", "you",
}


def _tokens(text: str) -> List[str]:
    return [tok for tok in re.findall(r"[a-z0-9]+", (text or "").lower()) if tok not in STOPWORDS]


def relu_precision_score(query: str, *texts: str) -> float:
    q_tokens = _tokens(query)
    if not q_tokens:
        return 0.0

    doc_tokens = _tokens(" ".join(texts))
    if not doc_tokens:
        return 0.0

    counts = Counter(doc_tokens)
    unique_hits = sum(1 for tok in set(q_tokens) if counts[tok] > 0)
    total_hits = sum(counts[tok] for tok in set(q_tokens))
    coverage = unique_hits / max(len(set(q_tokens)), 1)
    density = total_hits / max(len(doc_tokens), 1)

    first_phrase = " ".join(q_tokens[:2])
    phrase_bonus = 0.5 if first_phrase and first_phrase in " ".join(doc_tokens) else 0.0
    score = (coverage * 4.0) + (density * 10.0) + phrase_bonus
    return round(max(0.0, score), 4)


def rerank_with_relu(
    query: str,
    items: Iterable[dict],
    text_getter: Callable[[dict], str],
) -> List[dict]:
    ranked: List[dict] = []
    for item in items:
        score = relu_precision_score(query, text_getter(item))
        enriched = dict(item)
        enriched["relu_score"] = score
        ranked.append(enriched)
    return sorted(ranked, key=lambda row: row.get("relu_score", 0.0), reverse=True)
