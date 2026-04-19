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
    """Render the latest submission feedback with custom editorial styling."""
    if not feedback:
        return

    kind = feedback.get("kind", "")
    message = feedback.get("message", "")
    icon = ""
    css_class = "feedback-info"

    if kind == "correct":
        icon = "Solved"
        css_class = "feedback-success"
    elif kind == "one_away":
        icon = "One away"
        css_class = "feedback-warning"
        message = "You have three of the four words."
    elif kind == "wrong":
        icon = "Try again"
        css_class = "feedback-error"
        message = "That set does not form a valid group."
    elif kind == "invalid":
        icon = "Select four"
        css_class = "feedback-info"

    st.markdown(
        (
            f"<div class='feedback-banner {css_class}'>"
            f"<span class='feedback-kicker'>{icon}</span>"
            f"<span class='feedback-text'>{message}</span>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_solved_groups(game_state: dict[str, object]) -> None:
    """Render solved groups in their color order above the live board."""
    solved_groups = solved_groups_in_order(game_state)

    if not solved_groups:
        return

    st.markdown("<div class='section-label'>Solved Groups</div>", unsafe_allow_html=True)

    for group in solved_groups:
        words = " · ".join(str(word) for word in group["words"])
        st.markdown(
            (
                f"<div class='solved-group' style='background:{group['play_color_hex']};'>"
                f"<div class='solved-title'>{group['label']}</div>"
                f"<div class='solved-words'>{words}</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def render_tile_grid(game_state: dict[str, object]) -> None:
    """Render the unresolved tile grid with selectable buttons."""
    board_words = list(game_state["board_words"])
    selected_words = set(game_state["selected_words"])
    disabled = bool(game_state["game_over"])

    st.markdown("<div class='section-label'>Board</div>", unsafe_allow_html=True)

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
    mistakes_used = MISTAKE_LIMIT - int(game_state["mistakes_remaining"])

    if game_state["won"]:
        st.markdown(
            (
                "<div class='endcap endcap-success'>"
                f"<div class='endcap-title'>Puzzle solved</div>"
                f"<div class='endcap-copy'>You found all four groups with {mistakes_used} mistake(s).</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            (
                "<div class='endcap endcap-error'>"
                f"<div class='endcap-title'>Game over</div>"
                f"<div class='endcap-copy'>You solved {solved_count}/4 groups before running out of mistakes.</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div class='section-label'>All Answers</div>", unsafe_allow_html=True)

    for group in game_state["groups"]:
        words = " · ".join(str(word) for word in group["words"])
        st.markdown(
            (
                f"<div class='solved-group' style='background:{group['play_color_hex']};'>"
                f"<div class='solved-title'>{group['label']}</div>"
                f"<div class='solved-words'>{words}</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div class='section-label'>Share</div>", unsafe_allow_html=True)
    st.code(share_summary(game_state), language=None)


st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(244, 236, 216, 0.9), transparent 28%),
            radial-gradient(circle at top right, rgba(221, 231, 242, 0.95), transparent 25%),
            linear-gradient(180deg, #fcfaf4 0%, #f7f2e7 100%);
    }
    .block-container {
        max-width: 820px;
        padding-top: 2.2rem;
        padding-bottom: 3rem;
    }
    .hero-shell {
        background: rgba(255, 252, 245, 0.82);
        border: 1px solid rgba(85, 68, 48, 0.09);
        border-radius: 28px;
        box-shadow: 0 24px 60px rgba(87, 73, 52, 0.08);
        margin-bottom: 1.2rem;
        overflow: hidden;
    }
    .hero-band {
        background: linear-gradient(135deg, rgba(242, 217, 139, 0.55), rgba(191, 208, 228, 0.52));
        padding: 1.1rem 1.3rem 0.55rem 1.3rem;
    }
    .hero-title {
        color: #1f2430;
        font-family: Georgia, "Times New Roman", serif;
        font-size: 2.35rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        line-height: 1.02;
        margin: 0;
    }
    .hero-copy {
        color: #5f584b;
        font-size: 1rem;
        line-height: 1.55;
        margin: 0;
        padding: 0 1.3rem 1.2rem 1.3rem;
    }
    .section-label {
        color: #6e6658;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        margin: 0.4rem 0 0.65rem 0;
        text-transform: uppercase;
    }
    .status-strip {
        display: grid;
        gap: 0.7rem;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        margin: 1rem 0 1rem 0;
    }
    .status-card {
        background: rgba(255, 253, 248, 0.88);
        border: 1px solid rgba(102, 86, 62, 0.09);
        border-radius: 20px;
        box-shadow: 0 10px 24px rgba(92, 77, 54, 0.05);
        padding: 0.9rem 1rem;
    }
    .status-kicker {
        color: #8a7e69;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }
    .status-value {
        color: #1f2430;
        font-family: Georgia, "Times New Roman", serif;
        font-size: 1.75rem;
        font-weight: 700;
        margin-top: 0.2rem;
    }
    .feedback-banner {
        align-items: baseline;
        border-radius: 18px;
        display: flex;
        gap: 0.7rem;
        margin: 0.45rem 0 1rem 0;
        padding: 0.9rem 1rem;
    }
    .feedback-kicker {
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        min-width: 6.6rem;
        text-transform: uppercase;
    }
    .feedback-text {
        font-size: 0.98rem;
        line-height: 1.45;
    }
    .feedback-success {
        background: rgba(169, 197, 140, 0.28);
        border: 1px solid rgba(108, 134, 84, 0.18);
        color: #304225;
    }
    .feedback-warning {
        background: rgba(240, 217, 139, 0.28);
        border: 1px solid rgba(162, 131, 36, 0.18);
        color: #5a4a15;
    }
    .feedback-error {
        background: rgba(231, 202, 194, 0.45);
        border: 1px solid rgba(167, 104, 88, 0.18);
        color: #6b2f22;
    }
    .feedback-info {
        background: rgba(191, 208, 228, 0.3);
        border: 1px solid rgba(108, 136, 170, 0.18);
        color: #294866;
    }
    .solved-group {
        border-radius: 20px;
        box-shadow: 0 10px 26px rgba(78, 68, 52, 0.07);
        color: #1f2430;
        margin-bottom: 0.8rem;
        padding: 1rem 1.05rem;
    }
    .solved-title {
        font-size: 0.98rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        margin-bottom: 0.3rem;
        text-transform: uppercase;
    }
    .solved-words {
        font-size: 1rem;
        line-height: 1.5;
    }
    .endcap {
        border-radius: 22px;
        margin: 1rem 0 1rem 0;
        padding: 1rem 1.1rem;
    }
    .endcap-title {
        font-family: Georgia, "Times New Roman", serif;
        font-size: 1.4rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .endcap-copy {
        font-size: 0.98rem;
        line-height: 1.45;
    }
    .endcap-success {
        background: rgba(169, 197, 140, 0.3);
        border: 1px solid rgba(108, 134, 84, 0.18);
        color: #2d4323;
    }
    .endcap-error {
        background: rgba(231, 202, 194, 0.45);
        border: 1px solid rgba(167, 104, 88, 0.18);
        color: #6b2f22;
    }
    .stButton > button {
        background: rgba(255, 251, 243, 0.95);
        border: 1px solid rgba(95, 82, 60, 0.14);
        border-radius: 16px;
        box-shadow: 0 8px 18px rgba(78, 68, 52, 0.05);
        color: #1f2430;
        font-size: 0.97rem;
        font-weight: 700;
        min-height: 78px;
        transition: all 0.18s ease;
        white-space: normal;
    }
    .stButton > button:hover {
        border-color: rgba(95, 82, 60, 0.28);
        box-shadow: 0 12px 22px rgba(78, 68, 52, 0.08);
        transform: translateY(-1px);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(180deg, #2d384d 0%, #232c3f 100%);
        border-color: #232c3f;
        color: #f9f6ee;
    }
    .stButton > button[kind="primary"]:hover {
        border-color: #232c3f;
        box-shadow: 0 14px 24px rgba(34, 46, 69, 0.24);
    }
    .stCodeBlock {
        border-radius: 18px;
        overflow: hidden;
    }
    @media (max-width: 768px) {
        .hero-title {
            font-size: 1.95rem;
        }
        .status-strip {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

ensure_session_defaults()

st.markdown(
    """
    <div class="hero-shell">
      <div class="hero-band">
        <div class="hero-title">Infinite Connections v5</div>
      </div>
      <div class="hero-copy">
        Sort sixteen words into four hidden groups. The easiest category appears first in yellow, then green, blue,
        and purple. Shuffle the board, submit a set of four, and see how cleanly you can solve it.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

control_columns = st.columns([1.35, 1, 1, 1], vertical_alignment="center")

if control_columns[0].button("Generate New Puzzle", use_container_width=True, type="primary"):
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

if control_columns[3].button("Submit", use_container_width=True, disabled=bool(game_state["game_over"]), type="primary"):
    submit_guess(game_state)
    st.rerun()

solved_count = len(game_state["solved_group_ids"])

st.markdown(
    f"""
    <div class="status-strip">
      <div class="status-card">
        <div class="status-kicker">Selected</div>
        <div class="status-value">{len(game_state["selected_words"])}/4</div>
      </div>
      <div class="status-card">
        <div class="status-kicker">Groups Solved</div>
        <div class="status-value">{solved_count}/4</div>
      </div>
      <div class="status-card">
        <div class="status-kicker">Mistakes Remaining</div>
        <div class="status-value">{game_state["mistakes_remaining"]}/{MISTAKE_LIMIT}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

render_feedback(game_state.get("feedback"))
render_solved_groups(game_state)

remaining_groups = unsolved_groups(game_state)

if remaining_groups and not game_state["game_over"]:
    render_tile_grid(game_state)

render_game_end(game_state)
