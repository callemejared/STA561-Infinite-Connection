"""Streamlit dashboard for generating and reviewing final v6 puzzle batches.

The final app is designed for the competition review workflow:
- one click generates a 10K puzzle library
- progress stays visible during runtime build and batch generation
- every puzzle has a stable ID
- instructors can randomly sample or jump to any ID and inspect answers directly
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

from generators.puzzle_generator_v6 import generate_puzzles_v6_with_progress, initialize_v6_runtime

ANSWER_COLORS = ["#f9dc5c", "#8cc084", "#6aa6ff", "#9b72cf"]
NON_THEME_FRAME = "NOT_THEME"
DEFAULT_BATCH_SIZE = 10000
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


def prepare_library(puzzles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach cheap review metadata to the generated puzzle library."""
    prepared_entries: list[dict[str, Any]] = []

    for puzzle in puzzles:
        groups = list(puzzle.get("groups", []))
        difficulty = dict(puzzle.get("difficulty", {}))
        generation = dict(puzzle.get("generation", {}))
        group_labels = [str(group.get("label", "")) for group in groups]
        group_types = [str(group.get("type", "")) for group in groups]
        all_words = [str(word) for word in puzzle.get("all_words", [])]
        mechanism_families = normalize_list(list(generation.get("mechanism_families", [])))
        theme_frame_families = normalize_list(list(generation.get("theme_frame_families", [])))
        group_tiers = normalize_list(list(difficulty.get("group_tiers", [])))
        search_blob = " ".join(
            [
                str(puzzle.get("puzzle_id", "")),
                " ".join(group_labels),
                " ".join(group_types),
                " ".join(all_words),
                " ".join(mechanism_families),
                " ".join(theme_frame_families),
            ]
        ).upper()

        prepared_entries.append(
            {
                "puzzle": puzzle,
                "puzzle_id": str(puzzle.get("puzzle_id", "")),
                "group_tiers": group_tiers,
                "mechanism_families": mechanism_families,
                "theme_frame_families": theme_frame_families,
                "search_blob": search_blob,
            }
        )

    return prepared_entries


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
    """Populate Streamlit session state for the batch reviewer flow."""
    defaults: dict[str, Any] = {
        "prepared_library": None,
        "generation_report": None,
        "selected_ids": [],
        "current_puzzle_id": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_answer(groups: list[dict[str, Any]]) -> None:
    """Render one puzzle's four solved groups directly for manual quality review."""
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


def sample_puzzle_ids(library: list[dict[str, Any]], sample_size: int, seed: int) -> list[str]:
    """Draw a reproducible random sample of puzzle IDs from the generated library."""
    puzzle_ids = [entry["puzzle_id"] for entry in library]

    if not puzzle_ids:
        return []

    sample_count = min(sample_size, len(puzzle_ids))
    return random.Random(seed).sample(puzzle_ids, sample_count)


def lookup_entry_by_id(library: list[dict[str, Any]], puzzle_id: str) -> dict[str, Any] | None:
    """Return one prepared library entry by puzzle id."""
    for entry in library:
        if entry["puzzle_id"] == puzzle_id:
            return entry

    return None


def exported_sample_payload(library: list[dict[str, Any]], selected_ids: list[str]) -> list[dict[str, Any]]:
    """Return the currently selected sample for download or sharing."""
    selected_set = set(selected_ids)
    return [entry["puzzle"] for entry in library if entry["puzzle_id"] in selected_set]


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
    "Generate the final 10K-scale batch once, then randomly sample or jump to puzzle IDs for direct answer review. "
    "This reviewer flow is built for TA / instructor auditing rather than gameplay."
)

control_columns = st.columns([1, 1, 1.2], vertical_alignment="bottom")
requested_count = control_columns[0].number_input(
    "Batch size",
    min_value=100,
    max_value=50000,
    value=DEFAULT_BATCH_SIZE,
    step=100,
)
seed = control_columns[1].number_input(
    "Seed",
    min_value=0,
    max_value=10**9,
    value=DEFAULT_SEED,
    step=1,
)
generate_clicked = control_columns[2].button("Generate Batch", use_container_width=True)

if generate_clicked:
    progress_bar = st.progress(0.0, text="Starting final batch generation...")
    status_box = st.empty()

    try:
        runtime_start = perf_counter()
        status_box.info("Phase 1/2: building the final runtime and compatibility graph...")
        # Evaluation is meant to reflect a fresh end-to-end batch run on every
        # click, so we clear the memoized runtime before rebuilding it here.
        initialize_v6_runtime.cache_clear()
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

        prepared_library = prepare_library(puzzles)
        st.session_state["prepared_library"] = prepared_library
        st.session_state["generation_report"] = report
        st.session_state["selected_ids"] = sample_puzzle_ids(prepared_library, DEFAULT_SAMPLE_SIZE, int(seed))
        st.session_state["current_puzzle_id"] = prepared_library[0]["puzzle_id"] if prepared_library else None

        progress_bar.progress(1.0, text=f"Finished generating {len(puzzles):,} puzzles.")
        status_box.success(
            f"Generated {len(puzzles):,} puzzles in {generation_seconds:.2f}s after a {runtime_seconds:.2f}s runtime build. "
            f"Files were saved to `{GENERATED_V6_FINAL_PATH.name}` and `{REPORT_V6_FINAL_PATH.name}`."
        )
    except Exception as error:
        progress_bar.empty()
        status_box.error(f"Final batch generation failed: {error}")
        st.stop()

prepared_library = st.session_state.get("prepared_library")
report = st.session_state.get("generation_report")

if prepared_library is None or report is None:
    st.info(
        "Click `Generate Batch` to build the final v6 library. The app will generate the full batch, "
        "show progress, save the JSON files locally, and then open the review tools below."
    )
    st.stop()

summary_columns = st.columns(4)
summary_columns[0].metric("Generated puzzles", int(report.get("generated_count", len(prepared_library))))
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

sampling_columns = st.columns([1.2, 1.1, 1.1, 2], vertical_alignment="bottom")
sample_size = sampling_columns[0].number_input(
    "Random sample size",
    min_value=1,
    max_value=min(100, len(prepared_library)),
    value=min(DEFAULT_SAMPLE_SIZE, len(prepared_library)),
    step=1,
)
sample_seed = sampling_columns[1].number_input(
    "Sample seed",
    min_value=0,
    max_value=10**9,
    value=int(seed),
    step=1,
)

if sampling_columns[2].button("Draw Sample", use_container_width=True):
    st.session_state["selected_ids"] = sample_puzzle_ids(prepared_library, int(sample_size), int(sample_seed))
    if st.session_state["selected_ids"]:
        st.session_state["current_puzzle_id"] = st.session_state["selected_ids"][0]

all_ids = [entry["puzzle_id"] for entry in prepared_library]
default_selection = [
    puzzle_id for puzzle_id in st.session_state.get("selected_ids", []) if puzzle_id in set(all_ids)
]
selected_ids = sampling_columns[3].multiselect(
    "Selected puzzle IDs",
    options=all_ids,
    default=default_selection,
    help="Use random sampling above or manually select exact IDs for the review subset.",
)
st.session_state["selected_ids"] = selected_ids

if not selected_ids:
    st.warning("Pick at least one puzzle ID to review.")
    st.stop()

active_id = st.selectbox(
    "Current puzzle ID",
    options=selected_ids,
    index=max(0, selected_ids.index(st.session_state["current_puzzle_id"])) if st.session_state.get("current_puzzle_id") in selected_ids else 0,
)
st.session_state["current_puzzle_id"] = active_id
active_entry = lookup_entry_by_id(prepared_library, active_id)

if active_entry is None:
    st.error("The selected puzzle ID is missing from the generated library.")
    st.stop()

selected_payload = exported_sample_payload(prepared_library, selected_ids)
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
    f"Current sample contains {len(selected_ids)} puzzle IDs. Use the random sampler above to draw a fresh audit subset."
)

active_puzzle = active_entry["puzzle"]
review_columns = st.columns([1.6, 1.1], gap="large")

with review_columns[0]:
    st.subheader(f"Puzzle {active_entry['puzzle_id']}")
    render_answer(list(active_puzzle.get("groups", [])))

with review_columns[1]:
    difficulty = dict(active_puzzle.get("difficulty", {}))
    st.subheader("Metadata")
    st.write(f"**Source:** {active_puzzle.get('source', '')}")
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
