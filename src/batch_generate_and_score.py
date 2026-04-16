"""Generate many candidate puzzles, filter them, and save a simple report."""

import argparse
import json
from collections import Counter
from pathlib import Path
from random import Random
from typing import Any

from generators.puzzle_assembler import generate_candidate_puzzle
from load_data import (
    NORMALIZED_OFFICIAL_PATH,
    load_official_puzzles,
    normalize_all_official_puzzles,
    save_normalized_official_puzzles,
)
from validators.duplicate_check import canonicalize_puzzle, is_duplicate_of_official
from validators.puzzle_validators import (
    validate_ambiguity_and_overlap,
    validate_structure,
    validate_style,
)

ACCEPTED_PUZZLES_PATH = Path("data/generated/accepted_puzzles.json")
GENERATION_REPORT_PATH = Path("data/generated/generation_report.json")


def load_or_build_normalized_official_puzzles() -> list[dict[str, Any]]:
    """Load normalized official puzzles, building the file first if needed."""
    if NORMALIZED_OFFICIAL_PATH.exists():
        with NORMALIZED_OFFICIAL_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)

    raw_puzzles = load_official_puzzles()
    normalized_puzzles = normalize_all_official_puzzles(raw_puzzles)
    save_normalized_official_puzzles(normalized_puzzles, NORMALIZED_OFFICIAL_PATH)
    return normalized_puzzles


def save_json(payload: Any, output_path: Path) -> Path:
    """Write JSON output to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    return output_path


def generate_and_score_candidates(
    num_candidates: int,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate many puzzles and keep the ones that pass all checks."""
    official_puzzles = load_or_build_normalized_official_puzzles()
    rng = Random(seed)
    accepted_puzzles: list[dict[str, Any]] = []
    accepted_keys: set[tuple[tuple[str, ...], ...]] = set()

    candidate_group_type_counts: Counter[str] = Counter()
    accepted_group_type_counts: Counter[str] = Counter()
    structure_reason_counts: Counter[str] = Counter()
    style_reason_counts: Counter[str] = Counter()
    ambiguity_reason_counts: Counter[str] = Counter()

    report: dict[str, Any] = {
        "seed": seed,
        "official_puzzle_count": len(official_puzzles),
        "total_candidates_generated": 0,
        "rejected_by_duplicate_check": 0,
        "rejected_by_structure_validation": 0,
        "rejected_by_style_validation": 0,
        "rejected_by_ambiguity_validation": 0,
        "rejected_by_internal_repeat": 0,
        "accepted_count": 0,
        "counting_note": "Rejection counts are stage-based: each candidate is counted at the first stage where it fails.",
    }

    for candidate_index in range(1, num_candidates + 1):
        puzzle_id = f"gen_{candidate_index:06d}"
        candidate_puzzle = generate_candidate_puzzle(puzzle_id=puzzle_id, rng=rng)
        report["total_candidates_generated"] += 1
        candidate_group_type_counts.update(str(group["type"]) for group in candidate_puzzle["groups"])

        structure_reasons = validate_structure(candidate_puzzle)
        if structure_reasons:
            report["rejected_by_structure_validation"] += 1
            structure_reason_counts.update(structure_reasons)
            continue

        style_reasons = validate_style(candidate_puzzle)
        if style_reasons:
            report["rejected_by_style_validation"] += 1
            style_reason_counts.update(style_reasons)
            continue

        ambiguity_reasons = validate_ambiguity_and_overlap(candidate_puzzle)
        if ambiguity_reasons:
            report["rejected_by_ambiguity_validation"] += 1
            ambiguity_reason_counts.update(ambiguity_reasons)
            continue

        if is_duplicate_of_official(candidate_puzzle, official_puzzles):
            report["rejected_by_duplicate_check"] += 1
            continue

        puzzle_key = canonicalize_puzzle(candidate_puzzle)
        if puzzle_key in accepted_keys:
            report["rejected_by_internal_repeat"] += 1
            continue

        accepted_keys.add(puzzle_key)
        accepted_puzzles.append(candidate_puzzle)
        accepted_group_type_counts.update(str(group["type"]) for group in candidate_puzzle["groups"])

    report["accepted_count"] = len(accepted_puzzles)
    report["candidate_group_type_counts"] = dict(candidate_group_type_counts)
    report["accepted_group_type_counts"] = dict(accepted_group_type_counts)
    report["top_structure_rejection_reasons"] = dict(structure_reason_counts.most_common(5))
    report["top_style_rejection_reasons"] = dict(style_reason_counts.most_common(5))
    report["top_ambiguity_rejection_reasons"] = dict(ambiguity_reason_counts.most_common(5))

    return accepted_puzzles, report


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Generate and score many Infinite Connections puzzles.")
    parser.add_argument("--num-candidates", type=int, default=200, help="Number of candidate puzzles to generate.")
    parser.add_argument("--seed", type=int, default=561, help="Random seed for deterministic sampling.")
    parser.add_argument(
        "--accepted-output",
        type=Path,
        default=ACCEPTED_PUZZLES_PATH,
        help="Where to save accepted puzzles.",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=GENERATION_REPORT_PATH,
        help="Where to save the generation report.",
    )
    return parser


def main() -> None:
    """Run batch generation from the command line."""
    parser = build_argument_parser()
    args = parser.parse_args()

    accepted_puzzles, report = generate_and_score_candidates(
        num_candidates=args.num_candidates,
        seed=args.seed,
    )

    accepted_path = save_json(accepted_puzzles, args.accepted_output)
    report_path = save_json(report, args.report_output)

    print(f"Generated {report['total_candidates_generated']} candidate puzzles.")
    print(f"Accepted {report['accepted_count']} puzzles.")
    print(f"Rejected by structure validation: {report['rejected_by_structure_validation']}")
    print(f"Rejected by style validation: {report['rejected_by_style_validation']}")
    print(f"Rejected by ambiguity validation: {report['rejected_by_ambiguity_validation']}")
    print(f"Rejected by duplicate check: {report['rejected_by_duplicate_check']}")
    print(f"Rejected by internal repeat: {report['rejected_by_internal_repeat']}")
    print(f"Saved accepted puzzles to {accepted_path}.")
    print(f"Saved generation report to {report_path}.")


if __name__ == "__main__":
    main()
