"""Similarity helpers backed by pretrained vectors with a lexical fallback."""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Any

import numpy as np

DEFAULT_EMBEDDING_MODEL = "glove-wiki-gigaword-50"
TOKEN_PATTERN = re.compile(r"[A-Z0-9]+")


def normalize_phrase(value: Any) -> str:
    """Return uppercase text with compact whitespace."""
    return " ".join(str(value).strip().upper().split())


def normalize_compact(value: Any) -> str:
    """Return uppercase text with punctuation removed."""
    normalized = normalize_phrase(value)
    compact = re.sub(r"[^A-Z0-9]+", "", normalized)
    return compact or normalized.replace(" ", "")


def tokenize_text(value: Any) -> tuple[str, ...]:
    """Return normalized alphanumeric tokens for one text value."""
    normalized = normalize_phrase(value)
    return tuple(TOKEN_PATTERN.findall(normalized))


def cosine_counter_similarity(left: Counter[str], right: Counter[str]) -> float:
    """Compute cosine similarity for sparse Counters."""
    if not left or not right:
        return 0.0

    dot_product = sum(left[key] * right.get(key, 0) for key in left)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def cosine_dense_similarity(left: np.ndarray, right: np.ndarray) -> float:
    """Compute cosine similarity for dense vectors."""
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))

    if math.isclose(left_norm, 0.0) or math.isclose(right_norm, 0.0):
        return 0.0

    return float(np.dot(left, right) / (left_norm * right_norm))


def lexical_vector(text: str) -> Counter[str]:
    """Build a lightweight lexical vector when embeddings are unavailable."""
    features: Counter[str] = Counter()
    normalized = normalize_phrase(text)
    compact = normalize_compact(text)

    for token in tokenize_text(text):
        features[f"token:{token}"] += 1

    if compact:
        for prefix_length in (2, 3):
            if len(compact) >= prefix_length:
                features[f"prefix:{compact[:prefix_length]}"] += 1
                features[f"suffix:{compact[-prefix_length:]}"] += 1

    if len(compact) < 3:
        if compact:
            features[f"gram:{compact}"] += 1
        return features

    for index in range(len(compact) - 2):
        features[f"gram:{compact[index:index + 3]}"] += 1

    if normalized:
        features[f"text:{normalized}"] += 1

    return features


@lru_cache(maxsize=1)
def load_embedding_backend() -> tuple[str, Any | None]:
    """Load a compact pretrained embedding model when available."""
    try:
        import gensim.downloader as api
    except Exception:
        return "lexical-fallback", None

    try:
        model = api.load(DEFAULT_EMBEDDING_MODEL)
    except Exception:
        return "lexical-fallback", None

    return f"gensim:{DEFAULT_EMBEDDING_MODEL}", model


@lru_cache(maxsize=16384)
def vectorize_text(text: str) -> tuple[str, Counter[str] | np.ndarray]:
    """Vectorize text with pretrained embeddings or a lexical fallback."""
    backend_name, model = load_embedding_backend()

    if model is None:
        return backend_name, lexical_vector(text)

    token_vectors: list[np.ndarray] = []

    for token in tokenize_text(text):
        lowered = token.lower()

        if lowered in model:
            token_vectors.append(np.asarray(model[lowered], dtype=float))

    if not token_vectors:
        return "lexical-fallback", lexical_vector(text)

    return backend_name, np.mean(np.stack(token_vectors), axis=0)


@lru_cache(maxsize=65536)
def text_similarity(left: str, right: str) -> tuple[str, float]:
    """Return the backend and similarity score for two texts."""
    left_backend, left_vector = vectorize_text(left)
    right_backend, right_vector = vectorize_text(right)

    if isinstance(left_vector, Counter) or isinstance(right_vector, Counter):
        left_counter = left_vector if isinstance(left_vector, Counter) else lexical_vector(left)
        right_counter = right_vector if isinstance(right_vector, Counter) else lexical_vector(right)
        return "lexical-fallback", cosine_counter_similarity(left_counter, right_counter)

    backend_name = left_backend if left_backend == right_backend else "mixed"
    return backend_name, cosine_dense_similarity(left_vector, right_vector)


def max_similarity_to_labels(word: str, labels: list[str]) -> tuple[str, float]:
    """Return the best similarity score from one word to many labels."""
    best_backend = "unknown"
    best_score = 0.0

    for label in labels:
        backend_name, similarity = text_similarity(word, label)

        if similarity > best_score:
            best_backend = backend_name
            best_score = similarity

    return best_backend, best_score
