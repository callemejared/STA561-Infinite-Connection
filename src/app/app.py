"""Streamlit reviewer UI for browsing pre-generated Infinite Connections v5 puzzles.

v5 is optimized for batch generation and manual review, not for heavy live generation.
The reviewer app therefore reads a pre-generated library and exposes fast sampling,
navigation, filtering, and note-taking so TA/instructor review can stay lightweight.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATED_V5_PATH = PROJECT_ROOT / "data" / "generated" / "generated_v5.json"
REPORT_V5_PATH = PROJECT_ROOT / "data" / "generated" / "generation_report_v5.json"

ANSWER_COLORS = ["#f9dc5c", "#8cc084", "#6aa6ff", "#9b72cf"]
DEFAULT_DISPLAY_SEED = 1561
NON_THEME_FRAME = "NOT_THEME"
REVIEW_STATUSES = ("unreviewed", "keep", "revise", "reject")

st.set_page_config(page_title="Infinite Connections v5 Reviewer", page_icon=":clipboard:", layout="wide")


def shuffle_words(words: list[str], seed: int) -> list[str]:
    """Shuffle the board words for display only."""
    shuffled_words = list(words)
    random.Random(seed).shuffle(shuffled_words)
    return shuffled_words


def normalize_token(value: Any) -> str:
    """Return a compact uppercase token for lightweight search/filtering."""
    return " ".join(str(value).strip().upper().split())


def normalize_list(values: list[Any]) -> tuple[str, ...]:
    """Normalize a list of display strings for filtering and metadata display."""
    return tuple(normalize_token(value) for value in values if normalize_token(value))


def prepare_library(puzzles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach cheap reviewer metadata so filtering stays fast on a large v5 pool."""
    prepared_entries: list[dict[str, Any]] = []

    for puzzle in puzzles:
        groups = list(puzzle.get("groups", []))
        difficulty = dict(puzzle.get("difficulty", {}))
        generation = dict(puzzle.get("generation", {}))
        group_labels = [str(group.get("label", "")) for group in groups]
        group_types = [str(group.get("type", "")) for group in groups]
        all_words = [str(word) for word in puzzle.get("all_words", [])]
        search_blob = " ".join(
            [
                str(puzzle.get("puzzle_id", "")),
                str(puzzle.get("source", "")),
                " ".join(group_labels),
                " ".join(group_types),
                " ".join(all_words),
                " ".join(generation.get("mechanism_families", [])),
                " ".join(generation.get("theme_frame_families", [])),
            ]
        ).upper()

        prepared_entries.append(
            {
                "puzzle": puzzle,
                "puzzle_id": str(puzzle.get("puzzle_id", "")),
                "source": str(puzzle.get("source", "")),
                "group_tiers": normalize_list(list(difficulty.get("group_tiers", []))),
                "mechanism_families": normalize_list(list(generation.get("mechanism_families", []))),
                "theme_frame_families": normalize_list(list(generation.get("theme_frame_families", []))),
                "search_blob": search_blob,
            }
        )

    return prepared_entries


@st.cache_data(show_spinner=False)
def load_local_library() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load the default generated_v5 library and optional report from disk."""
    if not GENERATED_V5_PATH.exists():
        raise FileNotFoundError(str(GENERATED_V5_PATH))

    with GENERATED_V5_PATH.open("r", encoding="utf-8") as file:
        puzzles = json.load(file)

    report: dict[str, Any] = {}

    if REPORT_V5_PATH.exists():
        with REPORT_V5_PATH.open("r", encoding="utf-8") as file:
            report = json.load(file)

    return prepare_library(list(puzzles)), report


@st.cache_data(show_spinner=False)
def load_uploaded_library(file_bytes: bytes) -> list[dict[str, Any]]:
    """Parse an uploaded JSON library once so reviewers can inspect alternate exports."""
    payload = json.loads(file_bytes.decode("utf-8"))
    return prepare_library(list(payload))


def ensure_session_defaults() -> None:
    """Populate the Streamlit session with reviewer defaults."""
    defaults: dict[str, Any] = {
        "display_seed": DEFAULT_DISPLAY_SEED,
        "filtered_position": 0,
        "filter_signature": None,
        "show_answer": False,
        "review_records": {},
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_filters(
    library: list[dict[str, Any]],
    required_tiers: list[str],
    mechanism_filters: list[str],
    theme_filters: list[str],
    search_query: str,
) -> list[int]:
    """Return the library indices that survive the lightweight reviewer filters."""
    normalized_query = normalize_token(search_query)
    filtered_indices: list[int] = []

    for index, entry in enumerate(library):
        entry_tiers = set(entry["group_tiers"])
        entry_mechanisms = set(entry["mechanism_families"])
        entry_frames = set(entry["theme_frame_families"])

        if required_tiers and not set(required_tiers).issubset(entry_tiers):
            continue
        if mechanism_filters and not set(mechanism_filters).intersection(entry_mechanisms):
            continue
        if theme_filters and not set(theme_filters).intersection(entry_frames):
            continue
        if normalized_query and normalized_query not in entry["search_blob"]:
            continue

        filtered_indices.append(index)

    return filtered_indices


def sync_filter_state(filtered_indices: list[int], filter_signature: tuple[Any, ...]) -> None:
    """Reset navigation when the filter set changes so the reviewer never lands out of range."""
    if st.session_state.get("filter_signature") != filter_signature:
        st.session_state["filter_signature"] = filter_signature
        st.session_state["filtered_position"] = 0
        st.session_state["show_answer"] = False

    if not filtered_indices:
        st.session_state["filtered_position"] = 0
        return

    st.session_state["filtered_position"] = min(
        int(st.session_state.get("filtered_position", 0)),
        len(filtered_indices) - 1,
    )


def reset_current_puzzle_view(current_puzzle: dict[str, Any]) -> None:
    """Hide the answer and reshuffle the current board."""
    display_seed = int(st.session_state.get("display_seed", DEFAULT_DISPLAY_SEED))
    st.session_state["display_words"] = shuffle_words(list(current_puzzle["all_words"]), display_seed)
    st.session_state["display_seed"] = display_seed + 1
    st.session_state["show_answer"] = False


def render_board(words: list[str]) -> None:
    """Render the words as a 4x4 board."""
    for row_start in range(0, 16, 4):
        row_words = words[row_start : row_start + 4]
        columns = st.columns(4, gap="small")

        for column, word in zip(columns, row_words):
            column.markdown(
                f"<div class='word-tile'>{word}</div>",
                unsafe_allow_html=True,
            )


def render_answer(groups: list[dict[str, Any]]) -> None:
    """Render the solved groups with extra metadata useful for manual review."""
    for color, group in zip(ANSWER_COLORS, groups):
        words = " - ".join(str(word) for word in group["words"])
        metadata = dict(group.get("metadata", {}))
        info_bits = [str(group.get("type", ""))]

        if metadata.get("mechanism_family"):
            info_bits.append(str(metadata["mechanism_family"]))
        if metadata.get("theme_frame_family") and metadata.get("theme_frame_family") != NON_THEME_FRAME:
            info_bits.append(str(metadata["theme_frame_family"]))

        info_line = " | ".join(info_bits)
        st.markdown(
            (
                f"<div class='answer-card' style='background:{color};'>"
                f"<strong>{group.get('label', '')}</strong><br>"
                f"<span class='answer-type'>{info_line}</span><br>{words}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def review_summary(review_records: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Summarize reviewer statuses for the sidebar and metrics."""
    counts = {status: 0 for status in REVIEW_STATUSES}

    for record in review_records.values():
        status = str(record.get("status", "unreviewed"))

        if status not in counts:
            counts["unreviewed"] += 1
        else:
            counts[status] += 1

    return counts


def build_review_export(
    library: list[dict[str, Any]],
    review_records: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a compact export that instructors can save alongside manual judgments."""
    puzzle_lookup = {entry["puzzle_id"]: entry for entry in library}
    exported_rows: list[dict[str, Any]] = []

    for puzzle_id, record in sorted(review_records.items()):
        entry = puzzle_lookup.get(puzzle_id)

        if entry is None:
            continue

        exported_rows.append(
            {
                "puzzle_id": puzzle_id,
                "status": record.get("status", "unreviewed"),
                "notes": record.get("notes", ""),
                "group_tiers": list(entry["group_tiers"]),
                "mechanism_families": list(entry["mechanism_families"]),
                "theme_frame_families": list(entry["theme_frame_families"]),
            }
        )

    return exported_rows


st.markdown(
    """
    <style>
    .word-tile {
        align-items: center;
        background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
        border: 1px solid #cbd5e1;
        border-radius: 14px;
        display: flex;
        font-size: 1rem;
        font-weight: 700;
        justify-content: center;
        min-height: 78px;
        padding: 0.6rem;
        text-align: center;
    }
    .answer-card {
        border-radius: 14px;
        color: #1f2937;
        margin-bottom: 0.7rem;
        padding: 0.9rem 1rem;
    }
    .answer-type {
        opacity: 0.8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

ensure_session_defaults()

uploaded_library = st.sidebar.file_uploader(
    "Optional library override",
    type="json",
    help="Upload a generated_v5-style JSON file if you want to review a custom export instead of the default local library.",
)

try:
    if uploaded_library is not None:
        library = load_uploaded_library(uploaded_library.getvalue())
        report = {}
        library_label = uploaded_library.name
    else:
        library, report = load_local_library()
        library_label = str(GENERATED_V5_PATH.name)
except FileNotFoundError:
    st.title("Infinite Connections v5 Reviewer")
    st.error(
        "No local `generated_v5.json` library was found. Run "
        "`python src/batch_generate_v5.py --count 10000 --seed 561` first, or upload a JSON library from the sidebar."
    )
    st.stop()
except json.JSONDecodeError as exc:
    st.title("Infinite Connections v5 Reviewer")
    st.error(f"Could not parse the supplied v5 JSON library: {exc}")
    st.stop()

if not library:
    st.title("Infinite Connections v5 Reviewer")
    st.warning("The loaded v5 library is empty, so there is nothing to review yet.")
    st.stop()

all_tiers = sorted({tier for entry in library for tier in entry["group_tiers"]})
all_mechanisms = sorted({family for entry in library for family in entry["mechanism_families"]})
all_theme_frames = sorted(
    {
        frame
        for entry in library
        for frame in entry["theme_frame_families"]
        if frame and frame != NON_THEME_FRAME
    }
)

st.sidebar.subheader("Review Filters")
required_tiers = st.sidebar.multiselect(
    "Require tiers",
    options=all_tiers,
    help="Keep only puzzles whose tier mix includes all selected tiers.",
)
mechanism_filters = st.sidebar.multiselect(
    "Mechanism families",
    options=all_mechanisms,
    help="Keep puzzles that contain at least one of the selected mechanism families.",
)
theme_filters = st.sidebar.multiselect(
    "Theme frame families",
    options=all_theme_frames,
    help="Keep puzzles that contain at least one of the selected theme frame families.",
)
search_query = st.sidebar.text_input(
    "Search",
    help="Search by puzzle id, labels, words, types, or generation metadata.",
)

filter_signature = (
    tuple(required_tiers),
    tuple(mechanism_filters),
    tuple(theme_filters),
    normalize_token(search_query),
    library_label,
)
filtered_indices = apply_filters(library, required_tiers, mechanism_filters, theme_filters, search_query)
sync_filter_state(filtered_indices, filter_signature)

review_records = st.session_state.get("review_records", {})
review_counts = review_summary(review_records)
review_export = build_review_export(library, review_records)

st.sidebar.subheader("Review Progress")
st.sidebar.metric("Reviewed", review_counts["keep"] + review_counts["revise"] + review_counts["reject"])
st.sidebar.metric("Marked revise", review_counts["revise"])
st.sidebar.metric("Marked reject", review_counts["reject"])
st.sidebar.download_button(
    "Download review notes",
    data=json.dumps(review_export, indent=2, ensure_ascii=False),
    file_name="v5_review_notes.json",
    mime="application/json",
    disabled=not review_export,
)

st.title("Infinite Connections v5 Reviewer")
st.caption(
    "This interface is optimized for TA / instructor review of a pre-generated v5 puzzle pool. "
    "It does not perform live generation, so browsing and random sampling stay fast even for large batches."
)
st.caption(f"Current library: `{library_label}`")

summary_columns = st.columns(4)
summary_columns[0].metric("Loaded puzzles", len(library))
summary_columns[1].metric("Filtered puzzles", len(filtered_indices))
summary_columns[2].metric("Reviewed", review_counts["keep"] + review_counts["revise"] + review_counts["reject"])
summary_columns[3].metric("Needs revision", review_counts["revise"])

if report:
    report_columns = st.columns(4)
    report_columns[0].metric("Batch size", int(report.get("generated_count", len(library))))
    report_columns[1].metric("Throughput", f"{float(report.get('puzzles_per_second', 0.0)):.1f}/s")
    report_columns[2].metric("Runtime build", f"{float(report.get('runtime_build_seconds', 0.0)):.2f}s")
    report_columns[3].metric("Generation time", f"{float(report.get('generation_seconds', 0.0)):.2f}s")

if not filtered_indices:
    st.warning("No puzzles match the current filters. Clear or relax the sidebar filters to continue reviewing.")
    st.stop()

navigation_columns = st.columns([1, 1.2, 1, 1.1, 1, 1.1])
current_position = int(st.session_state.get("filtered_position", 0))

if navigation_columns[0].button("Previous", use_container_width=True, disabled=current_position <= 0):
    st.session_state["filtered_position"] = max(current_position - 1, 0)
    st.session_state["show_answer"] = False

if navigation_columns[1].button("Random Unreviewed", use_container_width=True):
    candidate_positions = [
        position
        for position, library_index in enumerate(filtered_indices)
        if review_records.get(library[library_index]["puzzle_id"], {}).get("status", "unreviewed") == "unreviewed"
    ]

    if candidate_positions:
        st.session_state["filtered_position"] = random.choice(candidate_positions)
        st.session_state["show_answer"] = False

if navigation_columns[2].button("Random", use_container_width=True):
    st.session_state["filtered_position"] = random.randrange(len(filtered_indices))
    st.session_state["show_answer"] = False

current_position = int(st.session_state.get("filtered_position", 0))

if navigation_columns[3].button("Next", use_container_width=True, disabled=current_position >= len(filtered_indices) - 1):
    st.session_state["filtered_position"] = min(current_position + 1, len(filtered_indices) - 1)
    st.session_state["show_answer"] = False

toggle_label = "Hide Answers" if st.session_state.get("show_answer", False) else "Reveal Answers"

if navigation_columns[4].button(toggle_label, use_container_width=True):
    st.session_state["show_answer"] = not st.session_state.get("show_answer", False)

active_library_index = filtered_indices[int(st.session_state.get("filtered_position", 0))]
active_entry = library[active_library_index]
active_puzzle = active_entry["puzzle"]

if "display_words" not in st.session_state or st.session_state.get("display_puzzle_id") != active_entry["puzzle_id"]:
    reset_current_puzzle_view(active_puzzle)
    st.session_state["display_puzzle_id"] = active_entry["puzzle_id"]

if navigation_columns[5].button("Shuffle Board", use_container_width=True):
    reset_current_puzzle_view(active_puzzle)
    st.session_state["display_puzzle_id"] = active_entry["puzzle_id"]

position_columns = st.columns([1.2, 1.8, 1.8])
position_columns[0].metric("Filtered position", f"{int(st.session_state['filtered_position']) + 1} / {len(filtered_indices)}")
position_columns[1].metric("Puzzle ID", active_entry["puzzle_id"])
position_columns[2].metric(
    "Current status",
    review_records.get(active_entry["puzzle_id"], {}).get("status", "unreviewed"),
)

main_columns = st.columns([1.8, 1.2], gap="large")

with main_columns[0]:
    render_board(list(st.session_state["display_words"]))

    if st.session_state.get("show_answer"):
        st.subheader("Answer")
        render_answer(list(active_puzzle.get("groups", [])))
    else:
        st.caption("Use Reveal Answers to show the four hidden categories.")

with main_columns[1]:
    difficulty = dict(active_puzzle.get("difficulty", {}))

    st.subheader("Puzzle Metadata")
    st.write(f"**Source:** {active_entry['source']}")
    st.write(f"**Tier mix:** {', '.join(active_entry['group_tiers'])}")
    st.write(f"**Puzzle score:** {float(difficulty.get('puzzle_score', 0.0)):.3f}")
    st.write(f"**Mechanisms:** {', '.join(active_entry['mechanism_families'])}")

    theme_frames = [frame for frame in active_entry["theme_frame_families"] if frame != NON_THEME_FRAME]

    if theme_frames:
        st.write(f"**Theme frames:** {', '.join(theme_frames)}")

    group_rows: list[dict[str, Any]] = []

    for group in active_puzzle.get("groups", []):
        metadata = dict(group.get("metadata", {}))
        group_rows.append(
            {
                "label": group.get("label", ""),
                "type": group.get("type", ""),
                "words": ", ".join(str(word) for word in group.get("words", [])),
                "mechanism": metadata.get("mechanism_family", ""),
                "theme_frame": metadata.get("theme_frame_family", ""),
            }
        )

    st.dataframe(group_rows, use_container_width=True, hide_index=True)

    st.subheader("Reviewer Notes")
    puzzle_id = active_entry["puzzle_id"]
    stored_review = review_records.get(puzzle_id, {"status": "unreviewed", "notes": ""})
    status_key = f"review_status_{puzzle_id}"
    notes_key = f"review_notes_{puzzle_id}"

    if status_key not in st.session_state:
        st.session_state[status_key] = stored_review["status"]
    if notes_key not in st.session_state:
        st.session_state[notes_key] = stored_review["notes"]

    st.selectbox("Status", REVIEW_STATUSES, key=status_key)
    st.text_area(
        "Notes",
        key=notes_key,
        height=180,
        placeholder="Write what should be revised, kept, or rejected for this puzzle.",
    )

    review_action_columns = st.columns(2)

    if review_action_columns[0].button("Save Review", use_container_width=True):
        review_records[puzzle_id] = {
            "status": st.session_state[status_key],
            "notes": st.session_state[notes_key].strip(),
        }
        st.session_state["review_records"] = review_records
        st.success("Saved reviewer note for this puzzle.")

    if review_action_columns[1].button("Clear Review", use_container_width=True):
        review_records.pop(puzzle_id, None)
        st.session_state["review_records"] = review_records
        st.session_state[status_key] = "unreviewed"
        st.session_state[notes_key] = ""
        st.success("Cleared reviewer note for this puzzle.")
