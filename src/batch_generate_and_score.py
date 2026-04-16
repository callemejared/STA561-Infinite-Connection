"""Batch-generate and validate v2 Infinite Connections puzzles."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from random import Random
from typing import Any

from data_utils.dataset_loader import (
    DEFAULT_PROCESSED_PATH,
    DEFAULT_STATS_PATH,
    load_or_build_dataset_assets,
)
from generators.puzzle_assembler import generate_candidate_puzzle_v2
from validators.duplicate_check import canonicalize_puzzle
from validators.puzzle_validators import ValidationConfig, first_failure_stage, validate_puzzle

ACCEPTED_PUZZLES_PATH = Path("data/generated/accepted_v2.json")
GENERATION_REPORT_PATH = Path("data/generated/generation_report_v2.json")


def save_json(payload: Any, output_path: Path) -> Path:
    """Write JSON output to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    return output_path


def load_official_dataset_assets(
    force_refresh_dataset: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load the normalized official HuggingFace dataset and its statistics."""
    return load_or_build_dataset_assets(
        processed_path=DEFAULT_PROCESSED_PATH,
        stats_path=DEFAULT_STATS_PATH,
        force_download=force_refresh_dataset,
    )


def print_progress(current: int, total: int, accepted_count: int) -> None:
    """Print a simple progress update for long batch runs."""
    print(f"[progress] processed {current}/{total} candidates, accepted {accepted_count}")


def generate_and_score_candidates(
    num_candidates: int,
    seed: int,
    validation_config: ValidationConfig,
    progress_every: int = 250,
    force_refresh_dataset: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate many puzzles and keep the ones that pass all v2 checks."""
    official_puzzles, dataset_stats = load_official_dataset_assets(force_refresh_dataset=force_refresh_dataset)
    rng = Random(seed)
    accepted_puzzles: list[dict[str, Any]] = []
    accepted_keys: set[tuple[tuple[str, ...], ...]] = set()

    candidate_group_type_counts: Counter[str] = Counter()
    accepted_group_type_counts: Counter[str] = Counter()
    rejection_counts: Counter[str] = Counter()
    stage_reason_counts: dict[str, Counter[str]] = defaultdict(Counter)
    accepted_within_scores: list[float] = []
    accepted_cross_scores: list[float] = []
    accepted_solution_counts: list[int] = []

    report: dict[str, Any] = {
        "seed": seed,
        "official_puzzle_count": len(official_puzzles),
        "dataset_mechanism_counts": dataset_stats.get("mechanism_counts", {}),
        "total_candidates_generated": 0,
        "accepted_count": 0,
        "acceptance_rate": 0.0,
        "rejected_by_structure": 0,
        "rejected_by_style": 0,
        "rejected_by_ambiguity": 0,
        "rejected_by_duplicate": 0,
        "rejected_by_multi_solution": 0,
        "rejected_by_low_cohesion": 0,
        "rejected_by_high_confusion": 0,
        "rejected_by_internal_repeat": 0,
        "rejected_by_generation_error": 0,
    }

    for candidate_index in range(1, num_candidates + 1):
        puzzle_id = f"gen_v2_{candidate_index:06d}"

        try:
            candidate_puzzle = generate_candidate_puzzle_v2(puzzle_id=puzzle_id, rng=rng)
        except ValueError as exc:
            rejection_counts["generation_error"] += 1
            stage_reason_counts["generation_error"].update([str(exc)])
            report["total_candidates_generated"] += 1
            continue

        report["total_candidates_generated"] += 1
        candidate_group_type_counts.update(str(group["type"]) for group in candidate_puzzle["groups"])

        validation_result = validate_puzzle(
            candidate_puzzle,
            official_puzzles=official_puzzles,
            config=validation_config,
        )
        failed_stage = first_failure_stage(validation_result)

        if failed_stage is not None:
            rejection_counts[failed_stage] += 1
            stage_reason_counts[failed_stage].update(validation_result["reason_groups"][failed_stage])
            continue

        puzzle_key = canonicalize_puzzle(candidate_puzzle)

        if puzzle_key in accepted_keys:
            rejection_counts["internal_repeat"] += 1
            stage_reason_counts["internal_repeat"].update(["puzzle duplicates another accepted candidate"])
            continue

        accepted_keys.add(puzzle_key)
        accepted_puzzles.append(candidate_puzzle)
        accepted_group_type_counts.update(str(group["type"]) for group in candidate_puzzle["groups"])
        accepted_within_scores.append(validation_result["metrics"]["average_within_group_similarity"])
        accepted_cross_scores.append(validation_result["metrics"]["average_cross_group_similarity"])
        accepted_solution_counts.append(validation_result["metrics"]["solution_count"])

        if progress_every > 0 and candidate_index % progress_every == 0:
            print_progress(candidate_index, num_candidates, len(accepted_puzzles))

    report["accepted_count"] = len(accepted_puzzles)
    report["acceptance_rate"] = len(accepted_puzzles) / num_candidates if num_candidates else 0.0
    report["rejected_by_structure"] = rejection_counts["structure"]
    report["rejected_by_style"] = rejection_counts["style"]
    report["rejected_by_ambiguity"] = rejection_counts["ambiguity"]
    report["rejected_by_duplicate"] = rejection_counts["duplicate"]
    report["rejected_by_multi_solution"] = rejection_counts["multi_solution"]
    report["rejected_by_low_cohesion"] = rejection_counts["low_cohesion"]
    report["rejected_by_high_confusion"] = rejection_counts["high_confusion"]
    report["rejected_by_internal_repeat"] = rejection_counts["internal_repeat"]
    report["rejected_by_generation_error"] = rejection_counts["generation_error"]
    report["candidate_group_type_counts"] = dict(candidate_group_type_counts)
    report["accepted_group_type_counts"] = dict(accepted_group_type_counts)
    report["average_within_group_similarity"] = (
        sum(accepted_within_scores) / len(accepted_within_scores) if accepted_within_scores else 0.0
    )
    report["average_cross_group_similarity"] = (
        sum(accepted_cross_scores) / len(accepted_cross_scores) if accepted_cross_scores else 0.0
    )
    report["average_solution_count"] = (
        sum(accepted_solution_counts) / len(accepted_solution_counts) if accepted_solution_counts else 0.0
    )
    report["top_structure_reasons"] = dict(stage_reason_counts["structure"].most_common(5))
    report["top_style_reasons"] = dict(stage_reason_counts["style"].most_common(5))
    report["top_ambiguity_reasons"] = dict(stage_reason_counts["ambiguity"].most_common(5))
    report["top_duplicate_reasons"] = dict(stage_reason_counts["duplicate"].most_common(5))
    report["top_multi_solution_reasons"] = dict(stage_reason_counts["multi_solution"].most_common(5))
    report["top_low_cohesion_reasons"] = dict(stage_reason_counts["low_cohesion"].most_common(5))
    report["top_high_confusion_reasons"] = dict(stage_reason_counts["high_confusion"].most_common(5))
    report["top_generation_errors"] = dict(stage_reason_counts["generation_error"].most_common(5))

    return accepted_puzzles, report


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Generate and score many Infinite Connections v2 puzzles.")
    parser.add_argument("--num-candidates", type=int, default=10000, help="Number of candidate puzzles to generate.")
    parser.add_argument("--seed", type=int, default=561, help="Random seed for deterministic sampling.")
    parser.add_argument(
        "--within-threshold",
        type=float,
        default=ValidationConfig.within_group_similarity_threshold,
        help="Minimum average within-group similarity required for acceptance.",
    )
    parser.add_argument(
        "--cross-threshold",
        type=float,
        default=ValidationConfig.cross_group_similarity_threshold,
        help="Maximum average cross-group similarity allowed for acceptance.",
    )
    parser.add_argument(
        "--max-solutions",
        type=int,
        default=ValidationConfig.max_solution_count,
        help="Maximum number of valid solutions permitted.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=250,
        help="Print a progress update every N generated candidates. Use 0 to disable progress output.",
    )
    parser.add_argument(
        "--force-refresh-dataset",
        action="store_true",
        help="Re-download and rebuild the official HuggingFace dataset assets before generating.",
    )
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

    validation_config = ValidationConfig(
        within_group_similarity_threshold=args.within_threshold,
        cross_group_similarity_threshold=args.cross_threshold,
        max_solution_count=args.max_solutions,
    )
    accepted_puzzles, report = generate_and_score_candidates(
        num_candidates=args.num_candidates,
        seed=args.seed,
        validation_config=validation_config,
        progress_every=args.progress_every,
        force_refresh_dataset=args.force_refresh_dataset,
    )

    accepted_path = save_json(accepted_puzzles, args.accepted_output)
    report_path = save_json(report, args.report_output)

    print(f"Generated {report['total_candidates_generated']} candidate puzzles.")
    print(f"Accepted {report['accepted_count']} puzzles.")
    print(f"Acceptance rate: {report['acceptance_rate']:.2%}")
    print(f"Rejected by structure validation: {report['rejected_by_structure']}")
    print(f"Rejected by style validation: {report['rejected_by_style']}")
    print(f"Rejected by ambiguity validation: {report['rejected_by_ambiguity']}")
    print(f"Rejected by duplicate check: {report['rejected_by_duplicate']}")
    print(f"Rejected by multi-solution check: {report['rejected_by_multi_solution']}")
    print(f"Rejected by low cohesion: {report['rejected_by_low_cohesion']}")
    print(f"Rejected by high confusion: {report['rejected_by_high_confusion']}")
    print(f"Rejected by internal repeat: {report['rejected_by_internal_repeat']}")
    print(f"Saved accepted puzzles to {accepted_path}.")
    print(f"Saved generation report to {report_path}.")


if __name__ == "__main__":
    main()
