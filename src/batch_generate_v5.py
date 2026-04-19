"""Batch-generate large v5 puzzle sets with a low-cost compatibility sampler."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any

from generators.puzzle_generator_v5 import generate_puzzles_v5, initialize_v5_runtime

GENERATED_V5_PATH = Path("data/generated/generated_v5.json")
GENERATION_REPORT_V5_PATH = Path("data/generated/generation_report_v5.json")


def save_json(payload: Any, output_path: Path) -> Path:
    """Write JSON output to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    return output_path


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the v5 batch generator."""
    parser = argparse.ArgumentParser(description="Generate many Infinite Connections v5 puzzles cheaply.")
    parser.add_argument("--count", type=int, default=10000, help="Number of v5 puzzles to generate.")
    parser.add_argument("--seed", type=int, default=561, help="Random seed for deterministic v5 sampling.")
    parser.add_argument(
        "--output",
        type=Path,
        default=GENERATED_V5_PATH,
        help="Where to save the generated v5 puzzle list.",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=GENERATION_REPORT_V5_PATH,
        help="Where to save the lightweight v5 generation report.",
    )
    return parser


def main() -> None:
    """Run the v5 batch generator from the command line."""
    parser = build_argument_parser()
    args = parser.parse_args()

    runtime_start = perf_counter()
    runtime = initialize_v5_runtime()
    runtime_seconds = perf_counter() - runtime_start

    generation_start = perf_counter()
    puzzles = generate_puzzles_v5(count=args.count, seed=args.seed)
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
        "mechanism_family_counts": dict(mechanism_counts),
        "theme_frame_family_counts": dict(theme_frame_counts),
        "tier_counts": dict(tier_counts),
    }

    output_path = save_json(puzzles, args.output)
    report_path = save_json(report, args.report_output)

    print(f"Generated {len(puzzles)} v5 puzzles.")
    print(f"Runtime build: {runtime_seconds:.3f}s")
    print(f"Generation time: {generation_seconds:.3f}s")
    print(f"Throughput: {report['puzzles_per_second']:.3f} puzzles/second")
    print(f"Saved puzzles to {output_path}")
    print(f"Saved report to {report_path}")


if __name__ == "__main__":
    main()
