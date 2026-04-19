"""Streamlit entrypoint for the final app.

The default page is the player-facing Play experience, while the sidebar
navigation also exposes the Evaluation dashboard for instructors.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

APP_ROOT = Path(__file__).resolve().parent

play_page = st.Page(
    str(APP_ROOT / "pages" / "Play.py"),
    title="Play",
    default=True,
)
evaluation_page = st.Page(
    str(APP_ROOT / "Evaluation.py"),
    title="Evaluation",
)

navigation = st.navigation(
    [play_page, evaluation_page],
    position="sidebar",
)

navigation.run()
