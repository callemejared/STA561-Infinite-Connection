"""Basic starter generator for draft Infinite Connections puzzles."""

EXAMPLE_CATEGORY_BANK = [
    {"label": "COLORS", "words": ["BLUE", "GREEN", "RED", "YELLOW"]},
    {"label": "DOG BREEDS", "words": ["BEAGLE", "COLLIE", "POODLE", "PUG"]},
    {"label": "BREAKFAST FOODS", "words": ["BACON", "CEREAL", "EGGS", "TOAST"]},
    {"label": "MUSICAL INSTRUMENTS", "words": ["DRUM", "FLUTE", "HARP", "TUBA"]},
]


def generate_basic_puzzle() -> dict[str, object]:
    """Return a simple example puzzle built from the starter category bank."""
    groups = [
        {"label": group["label"], "difficulty": index, "words": group["words"]}
        for index, group in enumerate(EXAMPLE_CATEGORY_BANK)
    ]

    all_words = [word for group in groups for word in group["words"]]

    return {
        "puzzle_id": "generated-example-001",
        "source": "generator/basic_generator",
        "groups": groups,
        "all_words": all_words,
    }
