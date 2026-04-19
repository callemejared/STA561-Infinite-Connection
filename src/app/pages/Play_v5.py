"""Player-facing Streamlit page for Infinite Connections v5."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = Path(__file__).resolve().parents[2]

for candidate in (PAGE_ROOT, SRC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from v5_game_logic import (
    MISTAKE_LIMIT,
    deselect_all,
    generate_v5_game,
    share_summary,
    shuffle_board,
    solved_groups_in_order,
    submit_guess,
    toggle_word_selection,
    unsolved_groups,
)

DEFAULT_SEED = 561

st.set_page_config(page_title="Play Infinite Connections v5", page_icon=":puzzle_piece:", layout="centered")


def ensure_session_defaults() -> None:
    """Populate session state for the play page."""
    defaults = {
        "play_seed": DEFAULT_SEED,
        "play_game": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def start_new_game() -> None:
    """Generate a fresh v5 puzzle and reset the current play session."""
    seed = int(st.session_state["play_seed"])

    with st.spinner("Generating a fresh v5 puzzle..."):
        st.session_state["play_game"] = generate_v5_game(seed)

    st.session_state["play_seed"] = seed + 1


def render_feedback(feedback: dict[str, str] | None) -> None:
    """Render the latest submission feedback with lightweight status styling."""
    if not feedback:
        return

    kind = feedback.get("kind", "")
    message = feedback.get("message", "")

    if kind == "correct":
        st.success(message)
    elif kind == "one_away":
        st.warning("⚠ One away!")
    elif kind == "wrong":
        st.error("❌ Try Again")
    elif kind == "invalid":
        st.info(message)


def render_solved_groups(game_state: dict[str, object]) -> None:
    """Render solved groups in their color order above the live board."""
    for group in solved_groups_in_order(game_state):
        words = " · ".join(str(word) for word in group["words"])
        st.markdown(
            (
                f"<div class='solved-group' style='background:{group['play_color_hex']};'>"
                f"<strong>{group['label']}</strong><br>{words}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def render_tile_grid(game_state: dict[str, object]) -> None:
    """Render the unresolved tile grid with selectable buttons."""
    board_words = list(game_state["board_words"])
    selected_words = set(game_state["selected_words"])
    disabled = bool(game_state["game_over"])

    for row_start in range(0, len(board_words), 4):
        row_words = board_words[row_start : row_start + 4]
        columns = st.columns(4, gap="small")

        for column, word in zip(columns, row_words):
            tile_type = "primary" if word in selected_words else "secondary"

            if column.button(
                str(word),
                key=f"play_tile_{game_state['tile_ids'][word]}",
                use_container_width=True,
                disabled=disabled,
                type=tile_type,
            ):
                toggle_word_selection(game_state, str(word))
                st.rerun()


def render_game_end(game_state: dict[str, object]) -> None:
    """Render the end-of-game summary and share text."""
    if not game_state["game_over"]:
        return

    solved_count = len(game_state["solved_group_ids"])

    if game_state["won"]:
        st.success(f"Puzzle solved! You found all 4 groups with {MISTAKE_LIMIT - game_state['mistakes_remaining']} mistake(s).")
    else:
        st.error(f"Game over. You solved {solved_count}/4 groups.")

    st.subheader("All Answers")
    for group in game_state["groups"]:
        words = " · ".join(str(word) for word in group["words"])
        st.markdown(
            (
                f"<div class='solved-group' style='background:{group['play_color_hex']};'>"
                f"<strong>{group['label']}</strong><br>{words}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    st.subheader("Share")
    st.code(share_summary(game_state), language=None)


st.markdown(
    """
    <style>
    .stButton > button {
        border-radius: 14px;
        font-weight: 700;
        min-height: 78px;
        white-space: normal;
    }
    .solved-group {
        border-radius: 16px;
        color: #1f2937;
        margin-bottom: 0.7rem;
        padding: 0.95rem 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

ensure_session_defaults()

st.title("Play Infinite Connections v5")
st.caption(
    "A player-facing Connections-style game built on the v5 generator. "
    "Generate a puzzle, solve the four hidden groups, and share your result when you finish."
)

control_columns = st.columns([1.3, 1, 1, 1], vertical_alignment="center")

if control_columns[0].button("Generate New Puzzle", use_container_width=True):
    start_new_game()
    st.rerun()

game_state = st.session_state.get("play_game")

if game_state is None:
    st.info("Click `Generate New Puzzle` to start a game.")
    st.stop()

if control_columns[1].button("Shuffle", use_container_width=True, disabled=bool(game_state["game_over"])):
    shuffle_board(game_state)
    st.rerun()

if control_columns[2].button("Deselect All", use_container_width=True, disabled=not bool(game_state["selected_words"])):
    deselect_all(game_state)
    st.rerun()

if control_columns[3].button("Submit", use_container_width=True, disabled=bool(game_state["game_over"])):
    submit_guess(game_state)
    st.rerun()

status_columns = st.columns(3)
status_columns[0].metric("Puzzle ID", str(game_state["puzzle"]["puzzle_id"]))
status_columns[1].metric("Selected", f"{len(game_state['selected_words'])}/4")
status_columns[2].metric("Mistakes Remaining", f"{game_state['mistakes_remaining']}/{MISTAKE_LIMIT}")

render_feedback(game_state.get("feedback"))
render_solved_groups(game_state)

remaining_groups = unsolved_groups(game_state)

if remaining_groups and not game_state["game_over"]:
    render_tile_grid(game_state)

render_game_end(game_state)
