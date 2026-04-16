"""Helpers for assembling full 16-word puzzles from mechanism-specific groups."""

from random import Random

from generators.anagram_generator import sample_anagram_group
from generators.form_generator import list_form_groups
from generators.semantic_generator import list_semantic_groups
from generators.semantic_generator import sample_semantic_group
from generators.theme_generator import list_theme_groups
from generators.theme_generator import sample_theme_group
from generators.form_generator import sample_form_group

DEFAULT_MECHANISM_PLAN = ["semantic", "semantic", "theme", "form"]
MECHANISM_PLANS = [
    ["semantic", "semantic", "theme", "form"],
    ["semantic", "theme", "theme", "form"],
    ["semantic", "semantic", "theme", "theme"],
]

V2_MECHANISM_PLANS = [
    ["semantic", "theme", "form", "form"],
    ["semantic", "theme", "semantic", "form"],
    ["semantic", "theme", "theme", "form"],
    ["semantic", "theme", "form", "anagram"],
]

GROUP_LISTERS = {
    "semantic": list_semantic_groups,
    "theme": list_theme_groups,
    "form": list_form_groups,
}

V2_GROUP_BUILDERS = {
    "semantic": sample_semantic_group,
    "theme": sample_theme_group,
    "form": sample_form_group,
    "anagram": sample_anagram_group,
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


def choose_v2_group(
    mechanism: str,
    rng: Random,
    used_words: set[str],
    used_labels: set[str],
) -> dict[str, object]:
    """Choose one v2 group while enforcing distinct labels and words."""
    builder = V2_GROUP_BUILDERS[mechanism]

    if mechanism == "form":
        subtypes = [None, "prefix", "suffix", "fill_blank", "rhyme", "homophone"]
        rng.shuffle(subtypes)

        for subtype in subtypes:
            try:
                group = builder(rng, used_words=used_words, subtype=subtype)
            except ValueError:
                continue

            label_key = normalize_word(str(group["label"]))

            if label_key in used_labels:
                continue

            return group

        raise ValueError("Could not find a form group for the current puzzle.")

    group = builder(rng, used_words=used_words)
    label_key = normalize_word(str(group["label"]))

    if label_key in used_labels:
        raise ValueError("Could not find a distinct label for the current puzzle.")

    return group


def generate_candidate_puzzle_v2(
    puzzle_id: str,
    seed: int | None = None,
    rng: Random | None = None,
    mechanism_plan: list[str] | None = None,
    max_attempts: int = 100,
) -> dict[str, object]:
    """Generate one v2 candidate puzzle with mechanism variety controls."""
    local_rng = rng if rng is not None else Random(seed)

    for _ in range(max_attempts):
        plan = list(mechanism_plan) if mechanism_plan is not None else list(local_rng.choice(V2_MECHANISM_PLANS))
        groups: list[dict[str, object]] = []
        used_words: set[str] = set()
        used_labels: set[str] = set()

        for mechanism in plan:
            try:
                group = choose_v2_group(mechanism, local_rng, used_words, used_labels)
            except ValueError:
                groups = []
                break

            groups.append(group)
            used_words.update(normalize_word(str(word)) for word in group["words"])
            used_labels.add(normalize_word(str(group["label"])))

        if len(groups) != 4:
            continue

        mechanism_types = {str(group["type"]) for group in groups}

        if "semantic" not in mechanism_types or "theme" not in mechanism_types:
            continue

        local_rng.shuffle(groups)
        return build_puzzle(groups, puzzle_id=puzzle_id, source="generated_v2")

    raise ValueError("Could not assemble a v2 puzzle from the current generator banks.")


def generate_candidate_puzzles_v2(
    count: int,
    seed: int = 0,
    start_index: int = 1,
) -> list[dict[str, object]]:
    """Generate many v2 candidate puzzles with deterministic sampling."""
    rng = Random(seed)
    puzzles = []

    for offset in range(count):
        puzzle_id = f"gen_v2_{start_index + offset:06d}"
        puzzles.append(generate_candidate_puzzle_v2(puzzle_id=puzzle_id, rng=rng))

    return puzzles
