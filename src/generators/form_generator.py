"""Lightweight form-based group generator backed by a curated bank."""

from random import Random

from generators.category_bank import get_groups_for_type


def list_form_groups() -> list[dict[str, object]]:
    """Return all available form groups."""
    return get_groups_for_type("form")


def sample_form_group(rng: Random) -> dict[str, object]:
    """Sample one form-based group."""
    return rng.choice(list_form_groups())
