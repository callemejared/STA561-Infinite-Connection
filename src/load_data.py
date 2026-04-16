"""Helpers for loading and normalizing official Infinite Connections data."""

import json
from pathlib import Path
from typing import Any

RAW_OFFICIAL_PATH = Path("data/raw/official_connections.json")
NORMALIZED_OFFICIAL_PATH = Path("data/processed/official_connections_normalized.json")


def load_official_puzzles(
    raw_path: str | Path = RAW_OFFICIAL_PATH,
) -> list[dict[str, Any]]:
    """Load the raw official puzzle export from disk."""
    path = Path(raw_path)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_official_puzzle(raw_puzzle: dict[str, Any]) -> dict[str, Any]:
    """Convert one raw puzzle record into the unified internal puzzle schema."""
    raw_groups = sorted(raw_puzzle.get("answers", []), key=lambda group: group.get("level", 0))

    groups = []
    for raw_group in raw_groups:
        groups.append(
            {
                "label": str(raw_group.get("group", "")),
                # Official groups do not come with a mechanism label yet.
                "type": "unknown",
                "words": [str(word) for word in raw_group.get("members", [])],
            }
        )

    all_words = [word for group in groups for word in group["words"]]
    raw_id = raw_puzzle.get("id", "unknown")

    if isinstance(raw_id, int):
        puzzle_id = f"official_{raw_id:06d}"
    else:
        puzzle_id = f"official_{raw_id}"

    return {
        "puzzle_id": puzzle_id,
        "source": "official",
        "groups": groups,
        "all_words": all_words,
    }


def normalize_all_official_puzzles(raw_puzzles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize every raw official puzzle into the internal schema."""
    return [normalize_official_puzzle(raw_puzzle) for raw_puzzle in raw_puzzles]


def save_normalized_official_puzzles(
    normalized_puzzles: list[dict[str, Any]],
    output_path: str | Path = NORMALIZED_OFFICIAL_PATH,
) -> Path:
    """Write normalized official puzzles to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(normalized_puzzles, file, indent=2)

    return path


def main() -> None:
    """Normalize the official puzzle export and save it to data/processed."""
    raw_puzzles = load_official_puzzles()
    normalized_puzzles = normalize_all_official_puzzles(raw_puzzles)
    output_path = save_normalized_official_puzzles(normalized_puzzles)

    print(f"Loaded {len(raw_puzzles)} raw official puzzles.")
    print(f"Saved {len(normalized_puzzles)} normalized official puzzles to {output_path}.")


if __name__ == "__main__":
    main()
