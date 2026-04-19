"""Game-state helpers for the player-facing Infinite Connections v5 page.

The UI layer should only render controls and session state. Puzzle generation,
tile ordering, guess evaluation, solved-group ordering, and share-summary logic
live here so the play page stays focused on presentation.
"""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Any

from generators.puzzle_generator_v5 import generate_puzzle_v5, initialize_v5_runtime

MISTAKE_LIMIT = 4
COLOR_SEQUENCE = (
    ("yellow", "#f9dc5c"),
    ("green", "#8cc084"),
    ("blue", "#6aa6ff"),
    ("purple", "#9b72cf"),
)
RESULT_EMOJI = {
    "yellow": "🟨",
    "green": "🟩",
    "blue": "🟦",
    "purple": "🟪",
    "one_away": "🟧",
    "wrong": "⬛",
}


def order_groups_for_play(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort groups into an easiest-to-hardest display order and attach colors.

    v5 groups do not have four named NYT difficulty colors, so we derive the play
    order from their numeric difficulty score and then map that order onto the
    yellow/green/blue/purple palette for the user-facing game.
    """
    sorted_groups = sorted(
        [deepcopy(group) for group in groups],
        key=lambda group: (
            float(group.get("difficulty", {}).get("score", 0.5)),
            str(group.get("label", "")),
        ),
    )
    decorated_groups: list[dict[str, Any]] = []

    for index, group in enumerate(sorted_groups):
        color_name, color_hex = COLOR_SEQUENCE[index]
        group["play_group_id"] = f"group_{index + 1}"
        group["play_color_name"] = color_name
        group["play_color_hex"] = color_hex
        decorated_groups.append(group)

    return decorated_groups


def shuffled_unsolved_words(game_state: dict[str, Any], seed: int) -> list[str]:
    """Return a shuffled view of the unresolved words only."""
    unresolved_words = [
        word
        for group in game_state["groups"]
        if group["play_group_id"] not in set(game_state["solved_group_ids"])
        for word in group["words"]
    ]
    random.Random(seed).shuffle(unresolved_words)
    return unresolved_words


def build_game_state(puzzle: dict[str, Any], display_seed: int) -> dict[str, Any]:
    """Create one fresh game-state payload from a generated v5 puzzle."""
    ordered_groups = order_groups_for_play(list(puzzle.get("groups", [])))
    tile_ids = {
        word: f"tile_{index:02d}"
        for index, word in enumerate(word for group in ordered_groups for word in group["words"])
    }

    game_state = {
        "puzzle": puzzle,
        "groups": ordered_groups,
        "tile_ids": tile_ids,
        "solved_group_ids": [],
        "selected_words": [],
        "mistakes_remaining": MISTAKE_LIMIT,
        "feedback": None,
        "guess_history": [],
        "game_over": False,
        "won": False,
        "display_seed": display_seed,
    }
    game_state["board_words"] = shuffled_unsolved_words(game_state, seed=display_seed)
    return game_state


def generate_v5_game(seed: int) -> dict[str, Any]:
    """Generate one player-facing puzzle from the cached v5 runtime."""
    runtime = initialize_v5_runtime()
    puzzle = generate_puzzle_v5(
        puzzle_id=f"play_v5_{seed:06d}",
        rng=random.Random(seed),
        runtime=runtime,
    )
    return build_game_state(puzzle, display_seed=seed + 17)


def toggle_word_selection(game_state: dict[str, Any], word: str) -> None:
    """Toggle one unresolved word in the current guess."""
    if game_state["game_over"]:
        return

    selected_words = list(game_state["selected_words"])

    if word in selected_words:
        selected_words.remove(word)
    elif len(selected_words) < 4:
        selected_words.append(word)

    game_state["selected_words"] = selected_words


def deselect_all(game_state: dict[str, Any]) -> None:
    """Clear the current guess without changing the board."""
    game_state["selected_words"] = []


def shuffle_board(game_state: dict[str, Any]) -> None:
    """Reorder only the unresolved words, keeping solved rows fixed above."""
    game_state["display_seed"] += 1
    game_state["board_words"] = shuffled_unsolved_words(game_state, seed=game_state["display_seed"])


def solved_groups_in_order(game_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return solved groups in their color difficulty order."""
    solved_ids = set(game_state["solved_group_ids"])
    return [group for group in game_state["groups"] if group["play_group_id"] in solved_ids]


def unsolved_groups(game_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the groups that are still hidden from the player."""
    solved_ids = set(game_state["solved_group_ids"])
    return [group for group in game_state["groups"] if group["play_group_id"] not in solved_ids]


def one_away_guess(selected_words: set[str], groups: list[dict[str, Any]], solved_ids: set[str]) -> bool:
    """Return True when the guess is only one word away from an unsolved group."""
    for group in groups:
        if group["play_group_id"] in solved_ids:
            continue
        if len(selected_words.intersection(set(group["words"]))) == 3:
            return True

    return False


def submit_guess(game_state: dict[str, Any]) -> None:
    """Evaluate the current four-word guess and update the game state."""
    if game_state["game_over"]:
        return

    selected_words = list(game_state["selected_words"])

    if len(selected_words) != 4:
        game_state["feedback"] = {
            "kind": "invalid",
            "message": "Select exactly four words before submitting.",
        }
        return

    selected_set = set(selected_words)
    solved_ids = set(game_state["solved_group_ids"])

    for group in game_state["groups"]:
        if group["play_group_id"] in solved_ids:
            continue
        if selected_set == set(group["words"]):
            game_state["solved_group_ids"].append(group["play_group_id"])
            game_state["selected_words"] = []
            game_state["feedback"] = {
                "kind": "correct",
                "message": f"Solved: {group['label']}",
                "color_name": group["play_color_name"],
            }
            game_state["guess_history"].append(
                {
                    "result": "correct",
                    "group_id": group["play_group_id"],
                    "color_name": group["play_color_name"],
                }
            )
            game_state["board_words"] = shuffled_unsolved_words(game_state, seed=game_state["display_seed"])

            if len(game_state["solved_group_ids"]) == len(game_state["groups"]):
                game_state["game_over"] = True
                game_state["won"] = True

            return

    if one_away_guess(selected_set, game_state["groups"], solved_ids):
        game_state["feedback"] = {
            "kind": "one_away",
            "message": "One away!",
        }
        game_state["guess_history"].append({"result": "one_away"})
        return

    game_state["mistakes_remaining"] -= 1
    game_state["feedback"] = {
        "kind": "wrong",
        "message": "Try Again",
    }
    game_state["guess_history"].append({"result": "wrong"})

    if game_state["mistakes_remaining"] <= 0:
        game_state["mistakes_remaining"] = 0
        game_state["game_over"] = True
        game_state["won"] = False
        game_state["selected_words"] = []


def share_summary(game_state: dict[str, Any]) -> str:
    """Build a lightweight share string once the game is finished."""
    solved_count = len(game_state["solved_group_ids"])
    mistakes_used = MISTAKE_LIMIT - int(game_state["mistakes_remaining"])
    headline = f"Infinite Connections v5 {solved_count}/4 with {mistakes_used} mistake"

    if mistakes_used != 1:
        headline += "s"

    emoji_rows = []

    for guess in game_state["guess_history"]:
        if guess["result"] == "correct":
            emoji_rows.append(RESULT_EMOJI.get(str(guess["color_name"]), "⬜"))
        else:
            emoji_rows.append(RESULT_EMOJI.get(str(guess["result"]), "⬜"))

    if emoji_rows:
        return headline + "\n" + "".join(emoji_rows)

    return headline
