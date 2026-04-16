"""Basic starter generator for draft Infinite Connections puzzles."""

EXAMPLE_CATEGORY_BANK = [
    {"label": "Birds", "type": "semantic", "words": ["eagle", "crow", "owl", "sparrow"]},
    {"label": "Colors", "type": "semantic", "words": ["red", "blue", "green", "yellow"]},
    {
        "label": "Associated with New York",
        "type": "theme",
        "words": ["subway", "broadway", "yankees", "manhattan"],
    },
    {"label": "Starts with sh", "type": "form", "words": ["ship", "shoe", "shock", "shell"]},
]


def generate_basic_puzzle() -> dict[str, object]:
    """Return a simple example puzzle built from the starter category bank."""
    groups = [
        {
            "label": group["label"],
            "type": group["type"],
            "words": list(group["words"]),
        }
        for group in EXAMPLE_CATEGORY_BANK
    ]

    all_words = [word for group in groups for word in group["words"]]

    return {
        "puzzle_id": "gen_000001",
        "source": "generated",
        "groups": groups,
        "all_words": all_words,
    }
