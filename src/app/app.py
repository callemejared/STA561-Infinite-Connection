"""Streamlit UI for browsing and generating Infinite Connections v4 puzzles."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import streamlit as st

from data_utils.dataset_loader import load_or_build_dataset_assets
from generators.puzzle_assembler import generate_candidate_puzzle_v4
from validators.puzzle_validators import ValidationConfig, validate_puzzle

ACCEPTED_PUZZLES_PATH = PROJECT_ROOT / "data" / "generated" / "accepted_v4.json"
ANSWER_COLORS = ["#f9dc5c", "#8cc084", "#6aa6ff", "#9b72cf"]

st.set_page_config(page_title="Infinite Connections v4", page_icon=":puzzle_piece:", layout="centered")


@st.cache_data(show_spinner=False)
def load_official_puzzles_for_validation() -> list[dict[str, Any]]:
    """Load the normalized official HuggingFace puzzles when available."""
    try:
        official_puzzles, _ = load_or_build_dataset_assets()
        return official_puzzles
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def load_saved_accepted_puzzles() -> list[dict[str, Any]]:
    """Load accepted v4 puzzles from disk if present."""
    if not ACCEPTED_PUZZLES_PATH.exists():
        return []

    with ACCEPTED_PUZZLES_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def shuffle_words(words: list[str], seed: int) -> list[str]:
    """Shuffle the board words for display only."""
    shuffled_words = list(words)
    random.Random(seed).shuffle(shuffled_words)
    return shuffled_words


def store_puzzle_in_state(puzzle: dict[str, Any], seed: int, source_label: str) -> None:
    """Persist the currently displayed puzzle in Streamlit session state."""
    st.session_state["puzzle"] = puzzle
    st.session_state["display_words"] = shuffle_words(list(puzzle["all_words"]), seed + 1000)
    st.session_state["show_answer"] = False
    st.session_state["board_seed"] = seed + 1
    st.session_state["puzzle_source_label"] = source_label


def choose_valid_generated_puzzle(seed: int) -> dict[str, Any]:
    """Generate one valid puzzle for the UI."""
    official_puzzles = load_official_puzzles_for_validation() or None
    rng = random.Random(seed)
    validation_config = ValidationConfig()

    for attempt in range(250):
        puzzle = generate_candidate_puzzle_v4(puzzle_id=f"ui_v4_{seed:06d}_{attempt:03d}", rng=rng, seed=seed)
        validation = validate_puzzle(puzzle, official_puzzles=official_puzzles, config=validation_config)

        if validation["is_valid"]:
            return puzzle

    raise RuntimeError("Could not generate a valid v4 puzzle for the UI after 250 attempts.")


def load_library_puzzle(seed: int, mode: str, index: int | None) -> dict[str, Any] | None:
    """Pick a puzzle from the saved library."""
    accepted_puzzles = load_saved_accepted_puzzles()

    if not accepted_puzzles:
        return None

    if mode == "By index" and index is not None:
        clamped_index = max(0, min(index, len(accepted_puzzles) - 1))
        return accepted_puzzles[clamped_index]

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
        words = " • ".join(str(word) for word in group["words"])
        st.markdown(
            (
                f"<div class='answer-card' style='background:{color};'>"
                f"<strong>{group['label']}</strong> "
                f"<span class='answer-type'>({group['type']})</span><br>{words}"
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

if "puzzle" not in st.session_state:
    initial_puzzle = choose_valid_generated_puzzle(st.session_state["board_seed"])
    store_puzzle_in_state(initial_puzzle, st.session_state["board_seed"], "Generated live")

accepted_library = load_saved_accepted_puzzles()
library_mode = st.radio("Library mode", ["Random", "By index"], horizontal=True)
library_index: int | None = None

if library_mode == "By index":
    max_index = max(len(accepted_library) - 1, 0)
    library_index = int(
        st.number_input(
            "Library index",
            min_value=0,
            max_value=max_index,
            value=0,
            step=1,
            disabled=not accepted_library,
        )
    )

st.title("Infinite Connections v4")
st.caption("A data-driven NYT-style generator with v4 difficulty balancing and decoy-aware assembly.")

control_columns = st.columns(3)

if control_columns[0].button("Generate New Puzzle", use_container_width=True):
    puzzle = choose_valid_generated_puzzle(st.session_state["board_seed"])
    store_puzzle_in_state(puzzle, st.session_state["board_seed"], "Generated live")

if control_columns[1].button("Load from Library", use_container_width=True):
    puzzle = load_library_puzzle(st.session_state["board_seed"], library_mode, library_index)

    if puzzle is None:
        st.warning("No saved `accepted_v4.json` library was found yet.")
    else:
        source_label = f"Library puzzle ({library_mode.lower()})"
        store_puzzle_in_state(puzzle, st.session_state["board_seed"], source_label)

if control_columns[2].button("Reveal Answers", use_container_width=True):
    st.session_state["show_answer"] = True

current_puzzle = st.session_state["puzzle"]
display_words = st.session_state["display_words"]

metadata_columns = st.columns(3)
metadata_columns[0].metric("Puzzle ID", current_puzzle["puzzle_id"])
metadata_columns[1].metric("Source", st.session_state.get("puzzle_source_label", current_puzzle["source"]))
metadata_columns[2].metric("Saved library", len(accepted_library))

if current_puzzle.get("difficulty"):
    difficulty_columns = st.columns(2)
    difficulty_columns[0].metric("Puzzle difficulty", f"{current_puzzle['difficulty']['puzzle_score']:.3f}")
    difficulty_columns[1].metric("Tier mix", ", ".join(current_puzzle["difficulty"]["group_tiers"]))

render_board(display_words)

if st.session_state["show_answer"]:
    st.subheader("Answer")
    render_answer(current_puzzle["groups"])
else:
    st.caption("Use Reveal Answers to show the four hidden categories in yellow, green, blue, and purple.")
