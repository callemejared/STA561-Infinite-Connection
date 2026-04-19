"""Streamlit UI for browsing a pre-generated Infinite Connections v4 library."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
ACCEPTED_PUZZLES_PATH = PROJECT_ROOT / "data" / "generated" / "accepted_v4.json"
ANSWER_COLORS = ["#f9dc5c", "#8cc084", "#6aa6ff", "#9b72cf"]
LIBRARY_BENCHMARK_ACCEPTED = 10
LIBRARY_BENCHMARK_SECONDS = 427.4
SECONDS_PER_ACCEPTED_PUZZLE = LIBRARY_BENCHMARK_SECONDS / LIBRARY_BENCHMARK_ACCEPTED
ESTIMATED_LIBRARY_BUILD_HOURS = (SECONDS_PER_ACCEPTED_PUZZLE * 10_000) / 3600

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import streamlit as st

from generators.generator_resources import detect_form_subtype

st.set_page_config(page_title="Infinite Connections v4", page_icon=":puzzle_piece:", layout="centered")


def shuffle_words(words: list[str], seed: int) -> list[str]:
    """Shuffle the board words for display only."""
    shuffled_words = list(words)
    random.Random(seed).shuffle(shuffled_words)
    return shuffled_words


def is_trivial_form_group(group: dict[str, Any]) -> bool:
    """Return True when one form group is a too-obvious prefix/suffix category."""
    if str(group.get("type", "")).lower() != "form":
        return False

    subtype = str(group.get("metadata", {}).get("subtype") or detect_form_subtype(group) or "")
    return subtype in {"prefix", "suffix"}


def is_allowed_library_puzzle(puzzle: dict[str, Any]) -> bool:
    """Reject saved puzzles that still contain trivial surface-pattern form groups."""
    groups = list(puzzle.get("groups", []))

    if len(groups) != 4:
        return False

    return not any(is_trivial_form_group(group) for group in groups)


@st.cache_data(show_spinner=False)
def load_saved_accepted_puzzles() -> list[dict[str, Any]]:
    """Load accepted v4 puzzles from disk and drop trivial prefix/suffix form puzzles."""
    if not ACCEPTED_PUZZLES_PATH.exists():
        return []

    with ACCEPTED_PUZZLES_PATH.open("r", encoding="utf-8") as file:
        saved_puzzles = json.load(file)

    return [puzzle for puzzle in saved_puzzles if is_allowed_library_puzzle(puzzle)]


def store_puzzle_in_state(puzzle: dict[str, Any], seed: int, source_label: str) -> None:
    """Persist the currently displayed puzzle in Streamlit session state."""
    st.session_state["puzzle"] = puzzle
    st.session_state["display_words"] = shuffle_words(list(puzzle["all_words"]), seed + 1000)
    st.session_state["show_answer"] = False
    st.session_state["board_seed"] = seed + 1
    st.session_state["puzzle_source_label"] = source_label


def reset_current_puzzle_view() -> None:
    """Hide answers and reshuffle the current puzzle board."""
    current_puzzle = st.session_state.get("puzzle")

    if not current_puzzle:
        return

    next_seed = st.session_state.get("board_seed", 561)
    st.session_state["display_words"] = shuffle_words(list(current_puzzle["all_words"]), next_seed + 1000)
    st.session_state["show_answer"] = False
    st.session_state["board_seed"] = next_seed + 1


def load_library_puzzle(seed: int) -> dict[str, Any] | None:
    """Pick a puzzle from the saved library."""
    accepted_puzzles = load_saved_accepted_puzzles()

    if not accepted_puzzles:
        return None

    return random.Random(seed).choice(accepted_puzzles)


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
    """Render the solved groups with NYT-style colors."""
    for color, group in zip(ANSWER_COLORS, groups):
        words = " · ".join(str(word) for word in group["words"])
        column_label = group.get("label", "")
        column_type = group.get("type", "")
        st.markdown(
            (
                f"<div class='answer-card' style='background:{color};'>"
                f"<strong>{column_label}</strong> "
                f"<span class='answer-type'>({column_type})</span><br>{words}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


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
        min-height: 74px;
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
        opacity: 0.75;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "board_seed" not in st.session_state:
    st.session_state["board_seed"] = 561

accepted_library = load_saved_accepted_puzzles()

if "puzzle" not in st.session_state:
    initial_puzzle = load_library_puzzle(st.session_state["board_seed"])

    if initial_puzzle is not None:
        store_puzzle_in_state(initial_puzzle, st.session_state["board_seed"], "Library puzzle (fast)")

header_columns = st.columns([5, 1.4], vertical_alignment="center")
header_columns[0].title("Infinite Connections v4")

if header_columns[1].button("Reset Puzzle", use_container_width=True):
    reset_current_puzzle_view()

st.caption("This web app only samples from a pre-generated v4 library. Trivial `Starts with...` and `Ends with...` form groups are excluded.")
st.caption(
    f"Offline benchmark on this machine: 10 accepted puzzles took {LIBRARY_BENCHMARK_SECONDS:.1f}s "
    f"({SECONDS_PER_ACCEPTED_PUZZLE:.1f}s per accepted puzzle), so building a 10,000-puzzle library is roughly "
    f"{ESTIMATED_LIBRARY_BUILD_HOURS:.1f} hours of offline batch generation."
)

if not accepted_library:
    st.error(
        "No saved `accepted_v4.json` library is available yet. "
        "This app no longer falls back to live generation."
    )
    st.info(
        "Build the offline library first with "
        "`python src/batch_generate_and_score.py --target-accepted 10000 --num-candidates 20000 --seed 561`."
    )
    st.stop()

control_columns = st.columns(2)

if control_columns[0].button("Generate New Puzzle", use_container_width=True):
    puzzle = load_library_puzzle(st.session_state["board_seed"])

    if puzzle is not None:
        store_puzzle_in_state(puzzle, st.session_state["board_seed"], "Library puzzle (fast)")

if control_columns[1].button("Reveal Answers", use_container_width=True):
    st.session_state["show_answer"] = True

current_puzzle = st.session_state.get("puzzle")
display_words = st.session_state.get("display_words")

if current_puzzle is not None and display_words is not None:
    metadata_columns = st.columns(3)
    metadata_columns[0].metric("Puzzle ID", current_puzzle["puzzle_id"])
    metadata_columns[1].metric("Source", st.session_state.get("puzzle_source_label", current_puzzle["source"]))
    metadata_columns[2].metric("Saved library", len(accepted_library))

    if current_puzzle.get("difficulty"):
        difficulty_columns = st.columns(2)
        difficulty_columns[0].metric("Puzzle difficulty", f"{current_puzzle['difficulty']['puzzle_score']:.3f}")
        difficulty_columns[1].metric("Tier mix", ", ".join(current_puzzle["difficulty"]["group_tiers"]))

    render_board(display_words)

    if st.session_state.get("show_answer"):
        st.subheader("Answer")
        render_answer(current_puzzle["groups"])
    else:
        st.caption("Use Reveal Answers to show the four hidden categories.")
