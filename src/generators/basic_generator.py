"""Basic entry point for generating a simple Infinite Connections puzzle."""

from generators.category_bank import find_group_by_label
from generators.puzzle_assembler import build_puzzle, generate_candidate_puzzle

DEMO_GROUP_SPECS = [
    ("semantic", "Kitchen tools"),
    ("semantic", "Tree types"),
    ("theme", "At the beach"),
    ("form", "Starts with SH"),
]


def generate_basic_puzzle(seed: int | None = None) -> dict[str, object]:
    """Return a deterministic sample puzzle or a seeded candidate puzzle."""
    if seed is not None:
        return generate_candidate_puzzle(puzzle_id="gen_000001", seed=seed)

    groups = [
        find_group_by_label(group_type=group_type, label=label)
        for group_type, label in DEMO_GROUP_SPECS
    ]
    return build_puzzle(groups, puzzle_id="gen_000001")
