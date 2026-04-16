"""Minimal Streamlit UI for browsing generated Infinite Connections puzzles."""

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

from generators.basic_generator import generate_basic_puzzle
from generators.puzzle_assembler import generate_candidate_puzzle
from load_data import (
    load_official_puzzles,
    normalize_all_official_puzzles,
    save_normalized_official_puzzles,
)
from validators.duplicate_check import is_duplicate_of_official
from validators.puzzle_validators import (
    validate_ambiguity_and_overlap,
    validate_structure,
    validate_style,
)

RAW_OFFICIAL_PATH = PROJECT_ROOT / "data" / "raw" / "official_connections.json"
NORMALIZED_OFFICIAL_PATH = PROJECT_ROOT / "data" / "processed" / "official_connections_normalized.json"
ACCEPTED_PUZZLES_PATH = PROJECT_ROOT / "data" / "generated" / "accepted_puzzles.json"

st.set_page_config(page_title="Infinite Connections", page_icon=":puzzle_piece:", layout="centered")


@st.cache_data(show_spinner=False)
def load_or_build_normalized_official_puzzles() -> list[dict[str, Any]]:
    """Load normalized official puzzles relative to the project root."""
    if NORMALIZED_OFFICIAL_PATH.exists():
        with NORMALIZED_OFFICIAL_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)

    raw_puzzles = load_official_puzzles(raw_path=RAW_OFFICIAL_PATH)
    normalized_puzzles = normalize_all_official_puzzles(raw_puzzles)
    save_normalized_official_puzzles(normalized_puzzles, output_path=NORMALIZED_OFFICIAL_PATH)
    return normalized_puzzles


@st.cache_data(show_spinner=False)
def load_saved_accepted_puzzles() -> list[dict[str, Any]]:
    """Load accepted puzzles from the batch-generation output if present."""
    if not ACCEPTED_PUZZLES_PATH.exists():
        return []

    with ACCEPTED_PUZZLES_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def choose_valid_generated_puzzle(seed: int) -> dict[str, Any]:
    """Generate one valid puzzle for the UI when saved outputs are unavailable."""
    official_puzzles = load_or_build_normalized_official_puzzles()
    rng = random.Random(seed)

    for attempt in range(200):
        puzzle = generate_candidate_puzzle(puzzle_id=f"ui_{seed:06d}_{attempt:03d}", rng=rng)

        if validate_structure(puzzle):
            continue
        if validate_style(puzzle):
            continue
        if validate_ambiguity_and_overlap(puzzle):
            continue
        if is_duplicate_of_official(puzzle, official_puzzles):
            continue

        return puzzle

    return generate_basic_puzzle()


def shuffle_words(words: list[str], seed: int) -> list[str]:
    """Shuffle the board words for display only."""
    shuffled_words = list(words)
    random.Random(seed).shuffle(shuffled_words)
    return shuffled_words


def load_puzzle_for_display(seed: int) -> dict[str, Any]:
    """Pick a puzzle from saved output or generate one on demand."""
    accepted_puzzles = load_saved_accepted_puzzles()

    if accepted_puzzles:
        return random.Random(seed).choice(accepted_puzzles)

    return choose_valid_generated_puzzle(seed)


def generate_new_board() -> None:
    """Refresh the puzzle shown in session state."""
    seed = st.session_state.get("board_seed", 561)
    puzzle = load_puzzle_for_display(seed)

    st.session_state["puzzle"] = puzzle
    st.session_state["display_words"] = shuffle_words(list(puzzle["all_words"]), seed + 1000)
    st.session_state["show_answer"] = False
    st.session_state["board_seed"] = seed + 1


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


st.markdown(
    """
    <style>
    .word-tile {
        align-items: center;
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        display: flex;
        font-size: 1rem;
        font-weight: 600;
        justify-content: center;
        min-height: 70px;
        padding: 0.5rem;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "puzzle" not in st.session_state:
    generate_new_board()

st.title("Infinite Connections")
st.caption("A lightweight Connections-style generator for the STA561 course project.")

button_columns = st.columns(2)

if button_columns[0].button("Generate Puzzle", use_container_width=True):
    generate_new_board()
if button_columns[1].button("Reveal Answer", use_container_width=True):
    st.session_state["show_answer"] = True

current_puzzle = st.session_state["puzzle"]
display_words = st.session_state["display_words"]

st.write(f"Puzzle ID: `{current_puzzle['puzzle_id']}`")
st.write(f"Source: `{current_puzzle['source']}`")
render_board(display_words)

if st.session_state["show_answer"]:
    st.subheader("Answer")

    for group in current_puzzle["groups"]:
        words = ", ".join(group["words"])
        st.write(f"**{group['label']}** (`{group['type']}`): {words}")
else:
    st.caption("Use Reveal Answer to show the four hidden categories.")
