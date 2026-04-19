"""Streamlit UI for live-generated Infinite Connections v5 puzzles."""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
ANSWER_COLORS = ["#f9dc5c", "#8cc084", "#6aa6ff", "#9b72cf"]
DEFAULT_DISPLAY_SEED = 1561
DEFAULT_GENERATION_SEED = 561

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import streamlit as st

from app_runtime import generate_validated_live_puzzle, initialize_v4_runtime
from validators.duplicate_check import canonicalize_puzzle

st.set_page_config(page_title="Infinite Connections v5", page_icon=":puzzle_piece:", layout="centered")


def shuffle_words(words: list[str], seed: int) -> list[str]:
    """Shuffle the board words for display only."""
    shuffled_words = list(words)
    random.Random(seed).shuffle(shuffled_words)
    return shuffled_words


def ensure_session_defaults() -> None:
    """Populate the Streamlit session with the app defaults."""
    defaults: dict[str, Any] = {
        "display_seed": DEFAULT_DISPLAY_SEED,
        "generation_seed": DEFAULT_GENERATION_SEED,
        "generated_puzzle_count": 0,
        "seen_puzzle_keys": set(),
        "show_answer": False,
        "runtime_initialized": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def store_puzzle_in_state(puzzle: dict[str, Any], source_label: str, generation_stats: dict[str, Any]) -> None:
    """Persist the currently displayed puzzle in Streamlit session state."""
    display_seed = int(st.session_state.get("display_seed", DEFAULT_DISPLAY_SEED))
    st.session_state["puzzle"] = puzzle
    st.session_state["display_words"] = shuffle_words(list(puzzle["all_words"]), display_seed)
    st.session_state["display_seed"] = display_seed + 1
    st.session_state["show_answer"] = False
    st.session_state["puzzle_source_label"] = source_label
    st.session_state["generation_stats"] = generation_stats


def reset_current_puzzle_view() -> None:
    """Hide answers and reshuffle the current puzzle board."""
    current_puzzle = st.session_state.get("puzzle")

    if not current_puzzle:
        return

    display_seed = int(st.session_state.get("display_seed", DEFAULT_DISPLAY_SEED))
    st.session_state["display_words"] = shuffle_words(list(current_puzzle["all_words"]), display_seed)
    st.session_state["display_seed"] = display_seed + 1
    st.session_state["show_answer"] = False


@st.cache_resource(show_spinner=False)
def load_runtime() -> dict[str, Any]:
    """Load and warm the v5 generation runtime exactly once per app process."""
    return initialize_v4_runtime()


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
        words = " - ".join(str(word) for word in group["words"])
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

ensure_session_defaults()

if not st.session_state.get("runtime_initialized", False):
    with st.spinner("Initializing v5 runtime. First load warms embeddings, group banks, and the solver lookup..."):
        runtime = load_runtime()
    st.session_state["runtime_initialized"] = True
else:
    runtime = load_runtime()

warmup = runtime["warmup"]

header_columns = st.columns([5, 1.4], vertical_alignment="center")
header_columns[0].title("Infinite Connections v5")

if header_columns[1].button("Reset Board", use_container_width=True, disabled="puzzle" not in st.session_state):
    reset_current_puzzle_view()

st.caption(
    "The app now auto-initializes once on page load. After warmup, clicking `Generate New Puzzle` only runs "
    "live generation plus validation; it does not rebuild embeddings or the solver lookup."
)
st.caption(
    f"One-time warmup on this machine: {warmup['total_seconds']:.1f}s total "
    f"(embeddings {warmup['embedding_seconds']:.1f}s, lookup {warmup['lookup_seconds']:.1f}s, "
    f"group banks {warmup['group_bank_seconds']:.1f}s)."
)

control_columns = st.columns(2)

if control_columns[0].button("Generate New Puzzle", use_container_width=True):
    request_seed = int(st.session_state["generation_seed"])
    puzzle_index = int(st.session_state["generated_puzzle_count"]) + 1
    seen_puzzle_keys = set(st.session_state.get("seen_puzzle_keys", set()))
    st.session_state["generation_seed"] = request_seed + 1

    try:
        with st.spinner("Generating and validating a fresh v5 puzzle..."):
            generation_result = generate_validated_live_puzzle(
                runtime=runtime,
                seed=request_seed,
                puzzle_index=puzzle_index,
                seen_puzzle_keys=seen_puzzle_keys,
            )
    except ValueError as exc:
        st.error(str(exc))
    else:
        puzzle = generation_result["puzzle"]
        puzzle_key = canonicalize_puzzle(puzzle)
        seen_puzzle_keys.add(puzzle_key)
        st.session_state["seen_puzzle_keys"] = seen_puzzle_keys
        st.session_state["generated_puzzle_count"] = puzzle_index
        store_puzzle_in_state(
            puzzle=puzzle,
            source_label="Live generated + validated",
            generation_stats=generation_result["stats"],
        )

if control_columns[1].button("Reveal Answers", use_container_width=True, disabled="puzzle" not in st.session_state):
    st.session_state["show_answer"] = True

current_puzzle = st.session_state.get("puzzle")
display_words = st.session_state.get("display_words")
generation_stats = st.session_state.get("generation_stats", {})

if current_puzzle is None or display_words is None:
    st.info("Runtime is warm. Click `Generate New Puzzle` to build and validate a fresh puzzle.")
    st.stop()

metadata_columns = st.columns(4)
metadata_columns[0].metric("Puzzle ID", current_puzzle["puzzle_id"])
metadata_columns[1].metric("Source", st.session_state.get("puzzle_source_label", current_puzzle["source"]))
metadata_columns[2].metric("Last generation", f"{float(generation_stats.get('elapsed_seconds', 0.0)):.2f}s")
metadata_columns[3].metric("Candidate attempts", int(generation_stats.get("candidate_attempts", 0)))

if current_puzzle.get("difficulty"):
    difficulty_columns = st.columns(3)
    difficulty_columns[0].metric("Puzzle difficulty", f"{current_puzzle['difficulty']['puzzle_score']:.3f}")
    difficulty_columns[1].metric("Tier mix", ", ".join(current_puzzle["difficulty"]["group_tiers"]))
    difficulty_columns[2].metric("Similarity backend", str(generation_stats.get("validation_backend", warmup["embedding_backend"])))

rejections = generation_stats.get("rejection_counts", {})

if rejections:
    summary = ", ".join(f"{stage}: {count}" for stage, count in sorted(rejections.items()))
    st.caption(f"Retries before acceptance: {summary}")

render_board(display_words)

if st.session_state.get("show_answer"):
    st.subheader("Answer")
    render_answer(current_puzzle["groups"])
else:
    st.caption("Use Reveal Answers to show the four hidden categories.")
