"""Load, normalize, and summarize the official NYT Connections dataset."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

HF_DATASET_ID = "tm21cy/NYT-Connections"
HF_DATASET_URL = "https://huggingface.co/datasets/tm21cy/NYT-Connections/raw/main/ConnectionsFinalDataset.json"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_PATH = PROJECT_ROOT / "data" / "raw" / "nyt_connections_hf.json"
DEFAULT_PROCESSED_PATH = PROJECT_ROOT / "data" / "processed" / "nyt_official.json"
DEFAULT_STATS_PATH = PROJECT_ROOT / "data" / "processed" / "nyt_dataset_stats.json"

FORM_LABEL_HINTS = (
    "ANAGRAM",
    "HOMOPHONE",
    "HOMOPHONES",
    "PALINDROME",
    "PALINDROMES",
    "RHYME",
    "RHYMES",
    "STARTS WITH",
    "ENDS WITH",
    "CONTAINS",
    "LETTER",
    "INITIALS",
    "PREFIX",
    "SUFFIX",
)

THEME_PREFIX_HINTS = (
    "AT ",
    "IN ",
    "ON ",
    "AROUND ",
    "ASSOCIATED WITH ",
    "FEATURED IN ",
    "FOUND IN ",
    "SEEN IN ",
    "THINGS FOUND ",
    "THINGS YOU ",
    "COMPONENTS OF ",
    "PARTS OF ",
    "BODY PARTS IN ",
    "WORDS BEFORE ",
    "WORDS AFTER ",
)

THEME_CONTAINS_HINTS = (
    " IN “",
    ' IN "',
    " OF A ",
    " OF AN ",
    " USED FOR ",
    " ASSOCIATED WITH ",
    " FEATURED IN ",
    " FOUND IN ",
    " SEEN IN ",
    " CLASSIC ",
    " U.S. ",
)

THEME_TERMS = {
    "AIRLINES",
    "AIRPORTS",
    "ANIMALS IN CHINESE ZODIAC",
    "BASEBALL",
    "BIRDS IN THE TITLE",
    "BOARD GAMES",
    "BOOKS",
    "BRANDS",
    "CAPITALS",
    "CITIES",
    "COLLEGES",
    "COUNTRIES",
    "DISNEY",
    "FOODS",
    "MOVIES",
    "MUSICALS",
    "NBA TEAMS",
    "NFL TEAMS",
    "PLACES",
    "PRESIDENTS",
    "SONGS",
    "SPORTS TEAMS",
    "STATES",
    "SUPERHEROES",
    "TEAMS",
    "TV SHOWS",
}


def normalize_text(value: Any) -> str:
    """Normalize whitespace and uppercase text for comparison."""
    return " ".join(str(value).strip().upper().split())


def normalize_word(word: Any) -> str:
    """Normalize one display word while preserving punctuation if present."""
    return normalize_text(word)


def compact_key(value: Any) -> str:
    """Return a comparison-friendly key for a label or word."""
    normalized = normalize_text(value)
    compact = re.sub(r"[^A-Z0-9]+", "", normalized)
    return compact or normalized


def shared_prefix(words: list[str], prefix_length: int) -> bool:
    """Return True when all words share the same prefix."""
    keys = [compact_key(word) for word in words]

    if any(len(key) < prefix_length + 1 for key in keys):
        return False

    return len({key[:prefix_length] for key in keys}) == 1


def shared_suffix(words: list[str], suffix_length: int) -> bool:
    """Return True when all words share the same suffix."""
    keys = [compact_key(word) for word in words]

    if any(len(key) < suffix_length + 1 for key in keys):
        return False

    return len({key[-suffix_length:] for key in keys}) == 1


def is_anagram_set(words: list[str]) -> bool:
    """Return True when every word is an anagram of the others."""
    keys = [compact_key(word) for word in words]

    if any(len(key) < 3 for key in keys):
        return False

    return len({"".join(sorted(key)) for key in keys}) == 1


def count_alpha_patterns(words: list[str], width: int, kind: str) -> dict[str, int]:
    """Count shared alphabetic prefixes or suffixes across the reusable word pool."""
    counter: Counter[str] = Counter()

    for word in words:
        key = compact_key(word)

        if not key.isalpha() or len(key) < width:
            continue

        pattern_value = key[:width] if kind == "prefix" else key[-width:]
        counter.update([pattern_value])

    return dict(counter)


def infer_group_type(label: str, words: list[str]) -> str:
    """Infer a broad mechanism label for one official group."""
    label_text = normalize_text(label)

    if "___" in label_text:
        return "form"

    if any(hint in label_text for hint in FORM_LABEL_HINTS):
        return "form"

    if is_anagram_set(words) or shared_prefix(words, 2) or shared_suffix(words, 3):
        return "form"

    if label_text in THEME_TERMS:
        return "theme"

    if any(label_text.startswith(prefix) for prefix in THEME_PREFIX_HINTS):
        return "theme"

    if any(hint in label_text for hint in THEME_CONTAINS_HINTS):
        return "theme"

    return "semantic"


def parse_hf_answer_group(raw_group: dict[str, Any]) -> dict[str, Any]:
    """Convert one answer entry into the shared group schema."""
    words = [normalize_word(word) for word in raw_group.get("words", [])]
    label = normalize_text(raw_group.get("answerDescription", ""))

    return {
        "label": label,
        "type": infer_group_type(label, words),
        "words": words,
    }


def extract_puzzle_number(raw_record: dict[str, Any], fallback_index: int) -> int:
    """Try to pull the contest number from the HuggingFace record."""
    contest = str(raw_record.get("contest", ""))
    match = re.search(r"CONNECTIONS\s+(\d+)", contest.upper())

    if match:
        return int(match.group(1))

    return fallback_index


def normalize_hf_record(raw_record: dict[str, Any], fallback_index: int) -> dict[str, Any]:
    """Convert one HuggingFace dataset row into the internal puzzle schema."""
    groups = [parse_hf_answer_group(group) for group in raw_record.get("answers", [])]
    puzzle_number = extract_puzzle_number(raw_record, fallback_index)
    all_words = [word for group in groups for word in group["words"]]

    return {
        "puzzle_id": f"nyt_{puzzle_number:04d}",
        "source": "nyt_official",
        "groups": groups,
        "all_words": all_words,
    }


def save_json(payload: Any, output_path: str | Path) -> Path:
    """Write JSON payloads to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    return path


def download_hf_dataset(
    output_path: str | Path = DEFAULT_RAW_PATH,
    dataset_url: str = HF_DATASET_URL,
    force: bool = False,
) -> Path:
    """Download the raw HuggingFace dataset JSON to disk."""
    path = Path(output_path)

    if path.exists() and not force:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with urlopen(dataset_url, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not download {HF_DATASET_ID} from {dataset_url}.") from exc

    save_json(payload, path)
    return path


def load_raw_hf_dataset(
    raw_path: str | Path = DEFAULT_RAW_PATH,
    download_if_missing: bool = True,
    force_download: bool = False,
) -> list[dict[str, Any]]:
    """Load the raw HuggingFace dataset, downloading it if requested."""
    path = Path(raw_path)

    if not path.exists():
        if not download_if_missing:
            raise FileNotFoundError(f"Raw dataset not found at {path}.")
        path = download_hf_dataset(output_path=path, force=force_download)
    elif force_download:
        path = download_hf_dataset(output_path=path, force=True)

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, list):
        raise ValueError("Expected the raw HuggingFace dataset to be a JSON list.")

    return payload


def normalize_hf_dataset(raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize every raw dataset row into the shared puzzle schema."""
    normalized_puzzles = []

    for index, raw_record in enumerate(raw_records, start=1):
        normalized_puzzles.append(normalize_hf_record(raw_record, fallback_index=index))

    return normalized_puzzles


def build_category_banks(normalized_puzzles: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group normalized official answers into broad mechanism banks."""
    banks: dict[str, list[dict[str, Any]]] = {"semantic": [], "theme": [], "form": []}
    seen_keys: set[tuple[str, str, tuple[str, ...]]] = set()

    for puzzle in normalized_puzzles:
        for group in puzzle["groups"]:
            group_type = str(group["type"])
            bank_entry = {
                "label": str(group["label"]),
                "type": group_type,
                "words": list(group["words"]),
                "source_puzzle_id": str(puzzle["puzzle_id"]),
            }
            key = (
                group_type,
                compact_key(group["label"]),
                tuple(sorted(compact_key(word) for word in group["words"])),
            )

            if key in seen_keys:
                continue

            seen_keys.add(key)
            banks.setdefault(group_type, []).append(bank_entry)

    return banks


def collect_dataset_statistics(normalized_puzzles: list[dict[str, Any]]) -> dict[str, Any]:
    """Collect word, label, and mechanism statistics for later generation."""
    word_counter: Counter[str] = Counter()
    label_counter: Counter[str] = Counter()
    mechanism_counter: Counter[str] = Counter()

    for puzzle in normalized_puzzles:
        word_counter.update(str(word) for word in puzzle["all_words"])

        for group in puzzle["groups"]:
            label_counter.update([str(group["label"])])
            mechanism_counter.update([str(group["type"])])

    category_banks = build_category_banks(normalized_puzzles)
    word_pool = sorted(word_counter)
    prefix3_frequency = count_alpha_patterns(word_pool, width=3, kind="prefix")
    suffix3_frequency = count_alpha_patterns(word_pool, width=3, kind="suffix")

    return {
        "dataset_id": HF_DATASET_ID,
        "dataset_url": HF_DATASET_URL,
        "puzzle_count": len(normalized_puzzles),
        "group_count": len(normalized_puzzles) * 4,
        "unique_word_count": len(word_counter),
        "mechanism_counts": dict(mechanism_counter),
        "word_frequency": dict(word_counter),
        "label_frequency": dict(label_counter),
        "top_words": [{"word": word, "count": count} for word, count in word_counter.most_common(30)],
        "top_labels": [{"label": label, "count": count} for label, count in label_counter.most_common(30)],
        "word_pool": word_pool,
        "category_banks": category_banks,
        "pattern_statistics": {
            "alphabetic_word_pool_size": sum(1 for word in word_pool if compact_key(word).isalpha()),
            "prefix3_frequency": prefix3_frequency,
            "suffix3_frequency": suffix3_frequency,
            "top_prefix3": [{"pattern": pattern, "count": count} for pattern, count in Counter(prefix3_frequency).most_common(25)],
            "top_suffix3": [{"pattern": pattern, "count": count} for pattern, count in Counter(suffix3_frequency).most_common(25)],
        },
    }


def build_dataset_assets(
    raw_path: str | Path = DEFAULT_RAW_PATH,
    processed_output_path: str | Path = DEFAULT_PROCESSED_PATH,
    stats_output_path: str | Path = DEFAULT_STATS_PATH,
    force_download: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Download if needed, normalize the dataset, and save statistics."""
    raw_records = load_raw_hf_dataset(raw_path=raw_path, force_download=force_download)
    normalized_puzzles = normalize_hf_dataset(raw_records)
    statistics = collect_dataset_statistics(normalized_puzzles)

    save_json(normalized_puzzles, processed_output_path)
    save_json(statistics, stats_output_path)
    return normalized_puzzles, statistics


def load_processed_puzzles(processed_path: str | Path = DEFAULT_PROCESSED_PATH) -> list[dict[str, Any]]:
    """Load normalized official puzzles from disk."""
    path = Path(processed_path)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_dataset_statistics(stats_path: str | Path = DEFAULT_STATS_PATH) -> dict[str, Any]:
    """Load the saved dataset statistics from disk."""
    path = Path(stats_path)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_or_build_dataset_assets(
    processed_path: str | Path = DEFAULT_PROCESSED_PATH,
    stats_path: str | Path = DEFAULT_STATS_PATH,
    raw_path: str | Path = DEFAULT_RAW_PATH,
    force_download: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load the normalized dataset and statistics, rebuilding them if needed."""
    processed_file = Path(processed_path)
    stats_file = Path(stats_path)

    if processed_file.exists() and stats_file.exists() and not force_download:
        return load_processed_puzzles(processed_file), load_dataset_statistics(stats_file)

    return build_dataset_assets(
        raw_path=raw_path,
        processed_output_path=processed_file,
        stats_output_path=stats_file,
        force_download=force_download,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for dataset ingestion."""
    parser = argparse.ArgumentParser(description="Load and normalize the NYT Connections HuggingFace dataset.")
    parser.add_argument("--raw-path", type=Path, default=DEFAULT_RAW_PATH, help="Local path for the raw dataset JSON.")
    parser.add_argument(
        "--processed-output",
        type=Path,
        default=DEFAULT_PROCESSED_PATH,
        help="Where to write normalized puzzles.",
    )
    parser.add_argument(
        "--stats-output",
        type=Path,
        default=DEFAULT_STATS_PATH,
        help="Where to write dataset statistics and category banks.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download the raw dataset even if a cached copy exists.",
    )
    return parser


def main() -> None:
    """Download, normalize, and summarize the official dataset."""
    parser = build_argument_parser()
    args = parser.parse_args()

    normalized_puzzles, statistics = build_dataset_assets(
        raw_path=args.raw_path,
        processed_output_path=args.processed_output,
        stats_output_path=args.stats_output,
        force_download=args.force_download,
    )

    print(f"Loaded {len(normalized_puzzles)} official puzzles from {HF_DATASET_ID}.")
    print(f"Saved normalized puzzles to {args.processed_output}.")
    print(f"Saved dataset statistics to {args.stats_output}.")
    print(f"Mechanism counts: {statistics['mechanism_counts']}")
    print(f"Unique words: {statistics['unique_word_count']}")


if __name__ == "__main__":
    main()
