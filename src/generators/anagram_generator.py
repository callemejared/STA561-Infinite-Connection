"""Optional anagram-focused generator retained for v4 compatibility."""

from __future__ import annotations

from random import Random

from generators.generator_resources import clone_group, load_anagram_bank, load_independent_anagram_bank, normalize_word_key


def list_anagram_groups() -> list[dict[str, object]]:
    """Return the available anagram groups."""
    return [clone_group(group, group_type="anagram") for group in load_anagram_bank()]


def list_independent_anagram_groups_v6() -> list[dict[str, object]]:
    """Return independently authored anagram groups for the v6 final workflow."""
    independent_groups: list[dict[str, object]] = []

    for group in load_independent_anagram_bank():
        cloned_group = clone_group(group, group_type="anagram")
        metadata = dict(cloned_group.get("metadata", {}))
        metadata["anagram_source"] = "independent_v6"
        cloned_group["metadata"] = metadata
        independent_groups.append(cloned_group)

    return independent_groups


def sample_anagram_group(
    rng: Random,
    used_words: set[str] | None = None,
) -> dict[str, object]:
    """Sample one anagram group while respecting the puzzle's used words."""
    candidates = []

    for group in list_anagram_groups():
        group_words = {normalize_word_key(word) for word in group["words"]}

        if used_words and used_words.intersection(group_words):
            continue

        candidates.append(group)

    if not candidates:
        raise ValueError("Could not find an available anagram group.")

    return clone_group(rng.choice(candidates), group_type="anagram")
