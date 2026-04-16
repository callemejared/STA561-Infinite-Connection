"""Helpers for assembling full 16-word puzzles from mechanism-specific groups."""

from random import Random

from generators.form_generator import list_form_groups
from generators.semantic_generator import list_semantic_groups
from generators.theme_generator import list_theme_groups

DEFAULT_MECHANISM_PLAN = ["semantic", "semantic", "theme", "form"]
MECHANISM_PLANS = [
    ["semantic", "semantic", "theme", "form"],
    ["semantic", "theme", "theme", "form"],
    ["semantic", "semantic", "theme", "theme"],
]

GROUP_LISTERS = {
    "semantic": list_semantic_groups,
    "theme": list_theme_groups,
    "form": list_form_groups,
}


def normalize_word(word: str) -> str:
    """Return a comparison-friendly word key."""
    return "".join(character for character in word.upper() if character.isalnum())


def build_puzzle(
    groups: list[dict[str, object]],
    puzzle_id: str,
    source: str = "generated",
) -> dict[str, object]:
    """Build a puzzle object in the shared internal schema."""
    copied_groups = [
        {
            "label": str(group["label"]),
            "type": str(group["type"]),
            "words": list(group["words"]),
        }
        for group in groups
    ]
    all_words = [word for group in copied_groups for word in group["words"]]

    return {
        "puzzle_id": puzzle_id,
        "source": source,
        "groups": copied_groups,
        "all_words": all_words,
    }


def choose_group(
    mechanism: str,
    rng: Random,
    used_words: set[str],
    used_labels: set[str],
) -> dict[str, object] | None:
    """Choose one group whose words do not collide with groups already selected."""
    candidates = GROUP_LISTERS[mechanism]()
    rng.shuffle(candidates)

    for group in candidates:
        group_words = {normalize_word(str(word)) for word in group["words"]}
        label_key = normalize_word(str(group["label"]))

        if len(group_words) != 4:
            continue
        if used_words.intersection(group_words):
            continue
        if label_key in used_labels:
            continue

        return group

    return None


def generate_candidate_puzzle(
    puzzle_id: str,
    seed: int | None = None,
    rng: Random | None = None,
    mechanism_plan: list[str] | None = None,
    max_attempts: int = 50,
) -> dict[str, object]:
    """Generate one candidate puzzle using a simple mechanism plan."""
    local_rng = rng if rng is not None else Random(seed)
    plan = list(mechanism_plan) if mechanism_plan is not None else list(local_rng.choice(MECHANISM_PLANS))

    for _ in range(max_attempts):
        groups: list[dict[str, object]] = []
        used_words: set[str] = set()
        used_labels: set[str] = set()

        for mechanism in plan:
            group = choose_group(mechanism, local_rng, used_words, used_labels)

            if group is None:
                break

            groups.append(group)
            used_words.update(normalize_word(str(word)) for word in group["words"])
            used_labels.add(normalize_word(str(group["label"])))

        if len(groups) == 4:
            local_rng.shuffle(groups)
            return build_puzzle(groups, puzzle_id=puzzle_id)

    raise ValueError("Could not assemble a 4-group puzzle from the current category banks.")


def generate_candidate_puzzles(
    count: int,
    seed: int = 0,
    start_index: int = 1,
) -> list[dict[str, object]]:
    """Generate many candidate puzzles with deterministic sampling."""
    rng = Random(seed)
    puzzles = []

    for offset in range(count):
        puzzle_id = f"gen_{start_index + offset:06d}"
        puzzles.append(generate_candidate_puzzle(puzzle_id=puzzle_id, rng=rng))

    return puzzles
