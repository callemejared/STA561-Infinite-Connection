"""Theme group generator backed by a curated bank."""

from random import Random

from generators.category_bank import get_groups_for_type


def list_theme_groups() -> list[dict[str, object]]:
    """Return all available theme groups."""
    return get_groups_for_type("theme")


def sample_theme_group(rng: Random) -> dict[str, object]:
    """Sample one theme group."""
    return rng.choice(list_theme_groups())
