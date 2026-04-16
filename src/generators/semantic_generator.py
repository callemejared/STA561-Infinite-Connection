"""Semantic group generator backed by a curated bank."""

from random import Random

from generators.category_bank import get_groups_for_type


def list_semantic_groups() -> list[dict[str, object]]:
    """Return all available semantic groups."""
    return get_groups_for_type("semantic")


def sample_semantic_group(rng: Random) -> dict[str, object]:
    """Sample one semantic group."""
    return rng.choice(list_semantic_groups())
