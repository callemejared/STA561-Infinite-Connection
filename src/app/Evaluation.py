"""Streamlit dashboard for generating and reviewing final v6 puzzle batches.

The Evaluation page is optimized for instructor review:
- large batches can still be generated on demand
- the generated library is saved to disk
- the UI keeps only small review state in session, not the full 10K payload
- review navigation stays lightweight by sampling IDs or jumping directly to one
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
GENERATED_V6_FINAL_PATH = PROJECT_ROOT / "data" / "generated" / "generated_v6_final.json"
REPORT_V6_FINAL_PATH = PROJECT_ROOT / "data" / "generated" / "generation_report_v6_final.json"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from generators import puzzle_generator_v6 as puzzle_generator_v6

generate_puzzles_v6_with_progress = puzzle_generator_v6.generate_puzzles_v6_with_progress
initialize_v6_runtime = puzzle_generator_v6.initialize_v6_runtime
clear_v6_runtime_caches = getattr(
    puzzle_generator_v6,
    "clear_v6_runtime_caches",
    initialize_v6_runtime.cache_clear,
)

ANSWER_COLORS = ["#f9dc5c", "#8cc084", "#6aa6ff", "#9b72cf"]
NON_THEME_FRAME = "NOT_THEME"
DEFAULT_BATCH_SIZE = 2000
DEFAULT_SEED = 561
DEFAULT_SAMPLE_SIZE = 5

st.set_page_config(page_title="Evaluation", page_icon=":clipboard:", layout="wide")


def normalize_token(value: Any) -> str:
    """Return a compact uppercase token for search and filtering."""
    return " ".join(str(value).strip().upper().split())


def normalize_list(values: list[Any]) -> tuple[str, ...]:
    """Normalize a list of display tokens for cheap filtering."""
    return tuple(normalize_token(value) for value in values if normalize_token(value))


def save_json(payload: Any, output_path: Path) -> Path:
    """Persist a generated final artifact to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    return output_path


@st.cache_data(show_spinner=False)
def load_review_bundle(
    puzzles_path: str,
    report_path: str,
    puzzles_mtime_ns: int,
    report_mtime_ns: int,
) -> dict[str, Any]:
    """Load the saved review artifacts and build lightweight lookup tables."""
    del puzzles_mtime_ns
    del report_mtime_ns

    with Path(puzzles_path).open("r", encoding="utf-8") as file:
        puzzles = json.load(file)

    with Path(report_path).open("r", encoding="utf-8") as file:
        report = json.load(file)

    entries: list[dict[str, Any]] = []
    entry_by_id: dict[str, dict[str, Any]] = {}
    puzzle_by_id: dict[str, dict[str, Any]] = {}
    id_by_number: dict[int, str] = {}

    for number, puzzle in enumerate(puzzles, start=1):
        groups = list(puzzle.get("groups", []))
        difficulty = dict(puzzle.get("difficulty", {}))
        generation = dict(puzzle.get("generation", {}))
        puzzle_id = str(puzzle.get("puzzle_id", f"gen_v6_{number:06d}"))
        entry = {
            "puzzle_id": puzzle_id,
            "sequence_number": number,
            "group_tiers": normalize_list(list(difficulty.get("group_tiers", []))),
            "mechanism_families": normalize_list(list(generation.get("mechanism_families", []))),
            "theme_frame_families": normalize_list(list(generation.get("theme_frame_families", []))),
            "group_labels": tuple(str(group.get("label", "")) for group in groups),
        }
        entries.append(entry)
        entry_by_id[puzzle_id] = entry
        puzzle_by_id[puzzle_id] = puzzle
        id_by_number[number] = puzzle_id

    return {
        "entries": entries,
        "entry_by_id": entry_by_id,
        "puzzle_by_id": puzzle_by_id,
        "id_by_number": id_by_number,
        "report": report,
    }


def load_review_bundle_from_disk() -> dict[str, Any] | None:
    """Load the saved review bundle when generated artifacts are present."""
    if not GENERATED_V6_FINAL_PATH.exists() or not REPORT_V6_FINAL_PATH.exists():
        return None

    return load_review_bundle(
        str(GENERATED_V6_FINAL_PATH),
        str(REPORT_V6_FINAL_PATH),
        GENERATED_V6_FINAL_PATH.stat().st_mtime_ns,
        REPORT_V6_FINAL_PATH.stat().st_mtime_ns,
    )


def build_generation_report(
    puzzles: list[dict[str, Any]],
    runtime: dict[str, Any],
    seed: int,
    requested_count: int,
    runtime_seconds: float,
    generation_seconds: float,
) -> dict[str, Any]:
    """Build a lightweight summary for the generated final batch."""
    mechanism_counts: Counter[str] = Counter()
    theme_frame_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()

    for puzzle in puzzles:
        generation = dict(puzzle.get("generation", {}))
        difficulty = dict(puzzle.get("difficulty", {}))
        mechanism_counts.update(generation.get("mechanism_families", []))
        theme_frame_counts.update(generation.get("theme_frame_families", []))
        tier_counts.update(difficulty.get("group_tiers", []))

    return {
        "seed": seed,
        "requested_count": requested_count,
        "generated_count": len(puzzles),
        "runtime_build_seconds": round(runtime_seconds, 3),
        "generation_seconds": round(generation_seconds, 3),
        "puzzles_per_second": round(len(puzzles) / max(generation_seconds, 1e-9), 3),
        "record_count": runtime["record_count"],
        "semantic_group_count": runtime.get("semantic_group_count"),
        "semantic_bank_mode": runtime.get("semantic_bank_mode"),
        "semantic_overlap_check": runtime.get("semantic_overlap_check"),
        "official_overlap_check": runtime.get("official_overlap_check"),
        "theme_bank_mode": runtime.get("theme_bank_mode"),
        "form_bank_mode": runtime.get("form_bank_mode"),
        "anagram_bank_mode": runtime.get("anagram_bank_mode"),
        "mechanism_family_counts": dict(mechanism_counts),
        "theme_frame_family_counts": dict(theme_frame_counts),
        "tier_counts": dict(tier_counts),
    }


def ensure_session_defaults() -> None:
    """Populate Streamlit session state for the review flow."""
    defaults: dict[str, Any] = {
        "selected_ids": [],
        "current_puzzle_id": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_answer(groups: list[dict[str, Any]]) -> None:
    """Render one puzzle's four solved groups directly for manual review."""
    for color, group in zip(ANSWER_COLORS, groups):
        words = " - ".join(str(word) for word in group.get("words", []))
        metadata = dict(group.get("metadata", {}))
        metadata_bits = [str(group.get("type", ""))]

        if metadata.get("mechanism_family"):
            metadata_bits.append(str(metadata["mechanism_family"]))
        if metadata.get("theme_frame_family") and metadata.get("theme_frame_family") != NON_THEME_FRAME:
            metadata_bits.append(str(metadata["theme_frame_family"]))

        metadata_line = " | ".join(metadata_bits)
        st.markdown(
            (
                f"<div class='answer-card' style='background:{color};'>"
                f"<strong>{group.get('label', '')}</strong><br>"
                f"<span class='answer-type'>{metadata_line}</span><br>{words}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def sample_puzzle_ids(entries: list[dict[str, Any]], sample_size: int, seed: int) -> list[str]:
    """Draw a reproducible random sample of puzzle IDs from the generated library."""
    puzzle_ids = [entry["puzzle_id"] for entry in entries]

    if not puzzle_ids:
        return []

    sample_count = min(sample_size, len(puzzle_ids))
    return random.Random(seed).sample(puzzle_ids, sample_count)


def exported_sample_payload(puzzle_by_id: dict[str, dict[str, Any]], selected_ids: list[str]) -> list[dict[str, Any]]:
    """Return the currently selected sample for download or sharing."""
    return [puzzle_by_id[puzzle_id] for puzzle_id in selected_ids if puzzle_id in puzzle_by_id]


def reset_sample(entries: list[dict[str, Any]], sample_size: int, seed: int) -> None:
    """Refresh the sampled review IDs and open the first sampled puzzle."""
    selected_ids = sample_puzzle_ids(entries, sample_size=sample_size, seed=seed)
    st.session_state["selected_ids"] = selected_ids
    st.session_state["current_puzzle_id"] = selected_ids[0] if selected_ids else None


def current_review_options(selected_ids: list[str], current_puzzle_id: str | None) -> list[str]:
    """Return the small set of IDs shown in the active puzzle selector."""
    options = list(selected_ids)

    if current_puzzle_id and current_puzzle_id not in options:
        options.insert(0, current_puzzle_id)

    return options


st.markdown(
    """
    <style>
    .answer-card {
        border-radius: 14px;
        color: #1f2937;
        margin-bottom: 0.8rem;
        padding: 1rem 1.1rem;
    }
    .answer-type {
        opacity: 0.82;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

ensure_session_defaults()

st.title("Evaluation")
st.caption(
    "Generate a large final library, save it locally, then review a small sampled subset or jump to any puzzle by number. "
    "The page keeps only lightweight review state in session so large batches stay responsive."
)

control_columns = st.columns([1, 1, 1.1, 1.2], vertical_alignment="bottom")
requested_count = control_columns[0].number_input(
    "Batch size",
    min_value=100,
    max_value=50000,
    value=DEFAULT_BATCH_SIZE,
    step=100,
    help="The app defaults to a smaller interactive batch for smoother review. You can still raise this to 10,000+.",
)
seed = control_columns[1].number_input(
    "Seed",
    min_value=0,
    max_value=10**9,
    value=DEFAULT_SEED,
    step=1,
)
force_rebuild = control_columns[2].checkbox(
    "Cold rebuild runtime",
    value=False,
    help="Usually leave this off. Reusing the cached runtime makes repeat evaluation runs much faster.",
)
generate_clicked = control_columns[3].button("Generate Batch", use_container_width=True)

if generate_clicked:
    progress_bar = st.progress(0.0, text="Starting final batch generation...")
    status_box = st.empty()

    try:
        runtime_start = perf_counter()
        status_box.info("Phase 1/2: preparing the final runtime and compatibility graph...")

        if force_rebuild:
            clear_v6_runtime_caches()

        runtime = initialize_v6_runtime()
        runtime_seconds = perf_counter() - runtime_start
        progress_bar.progress(0.12, text="Runtime ready. Starting batch generation...")

        generation_start = perf_counter()
        status_box.info(f"Phase 2/2: generating {int(requested_count):,} puzzles...")

        def on_progress(done_count: int, total_count: int) -> None:
            generation_fraction = done_count / max(total_count, 1)
            overall_fraction = 0.12 + (0.88 * generation_fraction)
            progress_bar.progress(
                min(overall_fraction, 1.0),
                text=f"Generating puzzles... {done_count:,} / {total_count:,}",
            )

        puzzles = generate_puzzles_v6_with_progress(
            count=int(requested_count),
            seed=int(seed),
            runtime=runtime,
            progress_callback=on_progress,
        )
        generation_seconds = perf_counter() - generation_start
        report = build_generation_report(
            puzzles=puzzles,
            runtime=runtime,
            seed=int(seed),
            requested_count=int(requested_count),
            runtime_seconds=runtime_seconds,
            generation_seconds=generation_seconds,
        )

        save_json(puzzles, GENERATED_V6_FINAL_PATH)
        save_json(report, REPORT_V6_FINAL_PATH)

        load_review_bundle.clear()
        review_bundle = load_review_bundle_from_disk()

        if review_bundle is None:
            raise RuntimeError("Saved review artifacts could not be reloaded after generation.")

        reset_sample(review_bundle["entries"], sample_size=DEFAULT_SAMPLE_SIZE, seed=int(seed))

        progress_bar.progress(1.0, text=f"Finished generating {len(puzzles):,} puzzles.")
        status_box.success(
            f"Generated {len(puzzles):,} puzzles in {generation_seconds:.2f}s after a {runtime_seconds:.2f}s runtime build. "
            f"Files were saved to `{GENERATED_V6_FINAL_PATH.name}` and `{REPORT_V6_FINAL_PATH.name}`."
        )
    except Exception as error:
        progress_bar.empty()
        status_box.error(f"Final batch generation failed: {error}")
        st.stop()

review_bundle = load_review_bundle_from_disk()

if review_bundle is None:
    st.info(
        "Click `Generate Batch` to build the final v6 library. The page will save the outputs locally and then open the review tools below."
    )
    st.stop()

entries = review_bundle["entries"]
entry_by_id = review_bundle["entry_by_id"]
puzzle_by_id = review_bundle["puzzle_by_id"]
id_by_number = review_bundle["id_by_number"]
report = review_bundle["report"]

valid_selected_ids = [puzzle_id for puzzle_id in st.session_state.get("selected_ids", []) if puzzle_id in entry_by_id]

if not valid_selected_ids:
    reset_sample(entries, sample_size=min(DEFAULT_SAMPLE_SIZE, len(entries)), seed=int(report.get("seed", DEFAULT_SEED)))
    valid_selected_ids = list(st.session_state["selected_ids"])
else:
    st.session_state["selected_ids"] = valid_selected_ids

if st.session_state.get("current_puzzle_id") not in entry_by_id:
    st.session_state["current_puzzle_id"] = valid_selected_ids[0] if valid_selected_ids else entries[0]["puzzle_id"]

summary_columns = st.columns(4)
summary_columns[0].metric("Generated puzzles", int(report.get("generated_count", len(entries))))
summary_columns[1].metric("Throughput", f"{float(report.get('puzzles_per_second', 0.0)):.1f}/s")
summary_columns[2].metric("Runtime build", f"{float(report.get('runtime_build_seconds', 0.0)):.2f}s")
summary_columns[3].metric("Generation time", f"{float(report.get('generation_seconds', 0.0)):.2f}s")
st.caption(
    f"Semantic bank: `{report.get('semantic_bank_mode', 'unknown')}` | "
    f"Theme bank: `{report.get('theme_bank_mode', 'unknown')}` | "
    f"Form bank: `{report.get('form_bank_mode', 'unknown')}` | "
    f"Anagram bank: `{report.get('anagram_bank_mode', 'unknown')}` | "
    f"Official overlap check: `{report.get('official_overlap_check', report.get('semantic_overlap_check', 'unknown'))}`"
)

sampling_columns = st.columns([1.2, 1.1, 1.1], vertical_alignment="bottom")
sample_size = sampling_columns[0].number_input(
    "Random sample size",
    min_value=1,
    max_value=min(100, len(entries)),
    value=min(DEFAULT_SAMPLE_SIZE, len(entries)),
    step=1,
)
sample_seed = sampling_columns[1].number_input(
    "Sample seed",
    min_value=0,
    max_value=10**9,
    value=int(report.get("seed", DEFAULT_SEED)),
    step=1,
)

if sampling_columns[2].button("Draw Sample", use_container_width=True):
    reset_sample(entries, sample_size=int(sample_size), seed=int(sample_seed))

selected_ids = list(st.session_state["selected_ids"])
st.caption(
    "Sampled puzzle IDs: " + ", ".join(selected_ids)
    if selected_ids
    else "No sampled puzzle IDs are currently selected."
)

jump_columns = st.columns([1.2, 1, 1.4], vertical_alignment="bottom")
current_entry = entry_by_id[st.session_state["current_puzzle_id"]]
jump_number = jump_columns[0].number_input(
    "Jump to puzzle number",
    min_value=1,
    max_value=len(entries),
    value=int(current_entry["sequence_number"]),
    step=1,
)

if jump_columns[1].button("Open Puzzle", use_container_width=True):
    st.session_state["current_puzzle_id"] = id_by_number[int(jump_number)]

review_options = current_review_options(selected_ids, st.session_state.get("current_puzzle_id"))
active_id = jump_columns[2].selectbox(
    "Current puzzle ID",
    options=review_options,
    index=max(0, review_options.index(st.session_state["current_puzzle_id"])) if st.session_state.get("current_puzzle_id") in review_options else 0,
)
st.session_state["current_puzzle_id"] = active_id

selected_payload = exported_sample_payload(puzzle_by_id, selected_ids)
download_columns = st.columns([1, 1.2, 3])
download_columns[0].download_button(
    "Download full report",
    data=json.dumps(report, indent=2, ensure_ascii=False),
    file_name="generation_report_v6_final.json",
    mime="application/json",
)
download_columns[1].download_button(
    "Download sample",
    data=json.dumps(selected_payload, indent=2, ensure_ascii=False),
    file_name="final_review_sample.json",
    mime="application/json",
)
download_columns[2].caption(
    f"Current review sample contains {len(selected_ids)} puzzle IDs. Use random sampling or jump directly to any generated puzzle number."
)

active_entry = entry_by_id[active_id]
active_puzzle = puzzle_by_id[active_id]
review_columns = st.columns([1.6, 1.1], gap="large")

with review_columns[0]:
    st.subheader(f"Puzzle {active_entry['puzzle_id']}")
    render_answer(list(active_puzzle.get("groups", [])))

with review_columns[1]:
    difficulty = dict(active_puzzle.get("difficulty", {}))
    st.subheader("Metadata")
    st.write(f"**Source:** {active_puzzle.get('source', '')}")
    st.write(f"**Puzzle number:** {active_entry['sequence_number']}")
    st.write(f"**Tier mix:** {', '.join(active_entry['group_tiers'])}")
    st.write(f"**Puzzle score:** {float(difficulty.get('puzzle_score', 0.0)):.3f}")
    st.write(f"**Mechanism families:** {', '.join(active_entry['mechanism_families'])}")

    theme_frames = [frame for frame in active_entry["theme_frame_families"] if frame != NON_THEME_FRAME]

    if theme_frames:
        st.write(f"**Theme frame families:** {', '.join(theme_frames)}")

    group_rows: list[dict[str, Any]] = []

    for group in active_puzzle.get("groups", []):
        metadata = dict(group.get("metadata", {}))
        group_rows.append(
            {
                "label": group.get("label", ""),
                "type": group.get("type", ""),
                "mechanism": metadata.get("mechanism_family", ""),
                "theme_frame": metadata.get("theme_frame_family", ""),
                "words": ", ".join(str(word) for word in group.get("words", [])),
            }
        )

    st.dataframe(group_rows, use_container_width=True, hide_index=True)
