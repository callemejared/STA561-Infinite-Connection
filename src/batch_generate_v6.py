"""Batch-generate large final v6 puzzle sets with the low-cost compatibility sampler."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any

from generators.puzzle_generator_v6 import generate_puzzles_v6, initialize_v6_runtime

GENERATED_V6_FINAL_PATH = Path("data/generated/generated_v6_final.json")
GENERATION_REPORT_V6_FINAL_PATH = Path("data/generated/generation_report_v6_final.json")


def save_json(payload: Any, output_path: Path) -> Path:
    """Write JSON output to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    return output_path


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the final v6 batch generator."""
    parser = argparse.ArgumentParser(description="Generate many Infinite Connections v6 final puzzles cheaply.")
    parser.add_argument("--count", type=int, default=10000, help="Number of final v6 puzzles to generate.")
    parser.add_argument("--seed", type=int, default=561, help="Random seed for deterministic v6 final sampling.")
    parser.add_argument(
        "--output",
        type=Path,
        default=GENERATED_V6_FINAL_PATH,
        help="Where to save the generated final v6 puzzle list.",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=GENERATION_REPORT_V6_FINAL_PATH,
        help="Where to save the lightweight final v6 generation report.",
    )
    return parser


def main() -> None:
    """Run the final v6 batch generator from the command line."""
    parser = build_argument_parser()
    args = parser.parse_args()

    runtime_start = perf_counter()
    runtime = initialize_v6_runtime()
    runtime_seconds = perf_counter() - runtime_start

    generation_start = perf_counter()
    puzzles = generate_puzzles_v6(count=args.count, seed=args.seed)
    generation_seconds = perf_counter() - generation_start

    mechanism_counts: Counter[str] = Counter()
    theme_frame_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()

    for puzzle in puzzles:
        mechanism_counts.update(puzzle.get("generation", {}).get("mechanism_families", []))
        theme_frame_counts.update(puzzle.get("generation", {}).get("theme_frame_families", []))
        tier_counts.update(puzzle.get("difficulty", {}).get("group_tiers", []))

    report = {
        "seed": args.seed,
        "requested_count": args.count,
        "generated_count": len(puzzles),
        "runtime_build_seconds": round(runtime_seconds, 3),
        "generation_seconds": round(generation_seconds, 3),
        "puzzles_per_second": round(len(puzzles) / max(generation_seconds, 1e-9), 3),
        "record_count": runtime["record_count"],
        "semantic_group_count": runtime["semantic_group_count"],
        "semantic_bank_mode": runtime["semantic_bank_mode"],
        "semantic_overlap_check": runtime["semantic_overlap_check"],
        "official_overlap_check": runtime["official_overlap_check"],
        "theme_bank_mode": runtime["theme_bank_mode"],
        "form_bank_mode": runtime["form_bank_mode"],
        "anagram_bank_mode": runtime["anagram_bank_mode"],
        "mechanism_family_counts": dict(mechanism_counts),
        "theme_frame_family_counts": dict(theme_frame_counts),
        "tier_counts": dict(tier_counts),
    }

    output_path = save_json(puzzles, args.output)
    report_path = save_json(report, args.report_output)

    print(f"Generated {len(puzzles)} final v6 puzzles.")
    print(f"Runtime build: {runtime_seconds:.3f}s")
    print(f"Generation time: {generation_seconds:.3f}s")
    print(f"Throughput: {report['puzzles_per_second']:.3f} puzzles/second")
    print(f"Semantic bank mode: {report['semantic_bank_mode']}")
    print(f"Saved puzzles to {output_path}")
    print(f"Saved report to {report_path}")


if __name__ == "__main__":
    main()
