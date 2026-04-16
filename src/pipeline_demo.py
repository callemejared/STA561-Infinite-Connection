"""Minimal end-to-end demo for the starter puzzle generation pipeline."""

import json
from pathlib import Path

from generators.basic_generator import generate_basic_puzzle
from load_data import (
    NORMALIZED_OFFICIAL_PATH,
    load_official_puzzles,
    normalize_all_official_puzzles,
    save_normalized_official_puzzles,
)
from validators.duplicate_check import is_duplicate_of_official
from validators.puzzle_validators import collect_validation_report

GENERATED_SAMPLE_PATH = Path("data/generated/sample_puzzle.json")


def load_or_build_normalized_official_puzzles() -> list[dict[str, object]]:
    """Load normalized official puzzles, building the file first if needed."""
    if NORMALIZED_OFFICIAL_PATH.exists():
        with NORMALIZED_OFFICIAL_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)

    raw_puzzles = load_official_puzzles()
    normalized_puzzles = normalize_all_official_puzzles(raw_puzzles)
    save_normalized_official_puzzles(normalized_puzzles, NORMALIZED_OFFICIAL_PATH)
    return normalized_puzzles


def save_sample_puzzle(puzzle: dict[str, object], output_path: Path = GENERATED_SAMPLE_PATH) -> Path:
    """Write one generated sample puzzle to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(puzzle, file, indent=2)

    return output_path


def main() -> None:
    """Run the v1.0 pipeline demo on one deterministic sample puzzle."""
    official_puzzles = load_or_build_normalized_official_puzzles()
    print(f"Loaded {len(official_puzzles)} official puzzles.")

    candidate_puzzle = generate_basic_puzzle()
    print(f"Generated puzzle: {candidate_puzzle['puzzle_id']}")

    validation_report = collect_validation_report(candidate_puzzle)

    for validator_name, reasons in validation_report.items():
        print(f"{validator_name} validation passed: {not reasons}")
        for reason in reasons:
            print(f"  - {reason}")

    is_duplicate = is_duplicate_of_official(candidate_puzzle, official_puzzles)
    print(f"Exact duplicate of official puzzle: {is_duplicate}")

    if any(validation_report.values()):
        print("No sample file was written because the generated puzzle did not pass validation.")
        return

    if is_duplicate:
        print("No sample file was written because the generated puzzle matched an official puzzle.")
        return

    output_path = save_sample_puzzle(candidate_puzzle)
    print(f"Saved sample puzzle to {output_path}.")
    print(f"all_words: {candidate_puzzle['all_words']}")

    for index, group in enumerate(candidate_puzzle["groups"], start=1):
        print(f"group {index}: {group['label']} ({group['type']}) -> {group['words']}")


if __name__ == "__main__":
    main()
