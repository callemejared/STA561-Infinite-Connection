"""Helpers for loading and normalizing official Infinite Connections data."""

from pathlib import Path
from typing import Any


def load_official_puzzles(
    raw_path: str | Path = "data/raw/official_connections.json",
) -> list[dict[str, Any]]:
    """Load the raw official puzzle export from disk."""
    raise NotImplementedError("Implement official puzzle loading here.")


def normalize_official_puzzle(raw_puzzle: dict[str, Any]) -> dict[str, Any]:
    """Convert one raw puzzle record into the unified internal puzzle schema."""
    raise NotImplementedError("Implement puzzle normalization here.")
