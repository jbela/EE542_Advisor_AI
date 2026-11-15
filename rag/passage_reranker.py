"""Lightweight lexical reranking for retrieved evidence."""

import re
from collections import Counter

STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "can", "do",
    "does", "for", "from", "how", "i", "in", "is",
    "it", "my", "of", "on", "or", "the", "their",
    "to", "us", "usc", "what", "when", "where",
    "which", "with", "would"
}


def tokenize(text):
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOPWORDS and len(token) > 1
    ]


def lexical_score(question, passage):
    query_tokens = tokenize(question)
    passage_tokens = tokenize(passage)

    if not query_tokens or not passage_tokens:
        return 0.0

    query_counts = Counter(query_tokens)
    passage_counts = Counter(passage_tokens)

    overlap = sum(
        min(count, passage_counts[token])
        for token, count in query_counts.items()
    )

    coverage = overlap / sum(query_counts.values())

    return coverage


def rerank_passages(question, results, weight=0.35):
    """
    Rerank retrieved passages using lexical overlap.

    Preserve original retrieval scores and metadata.
    """

    if not results:
        return []

    reranked = []

    for rank, result in enumerate(results):
        text = result.get("text", "")

        lexical = lexical_score(question, text)

        # Rank-based baseline avoids assuming FAISS/RRF
        # scores are on the same scale as lexical coverage.
        baseline = 1 / (rank + 1)

        combined = (
            (1 - weight) * baseline
            + weight * lexical
        )

        reranked.append({
            **result,
            "rerank_score": combined,
            "lexical_score": lexical,
            "original_rank": rank + 1
        })

    reranked.sort(
        key=lambda item: item["rerank_score"],
        reverse=True
    )

    return reranked
