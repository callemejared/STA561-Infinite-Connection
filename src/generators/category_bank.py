"""Curated category banks for simple rule-based puzzle generation."""

from typing import Any

CategoryGroup = dict[str, Any]

SEMANTIC_GROUPS: list[CategoryGroup] = [
    {"label": "Kitchen tools", "type": "semantic", "words": ("LADLE", "PEELER", "SPATULA", "WHISK")},
    {"label": "Tree types", "type": "semantic", "words": ("CEDAR", "MAPLE", "OAK", "PINE")},
    {"label": "Chess pieces", "type": "semantic", "words": ("BISHOP", "KING", "KNIGHT", "ROOK")},
    {"label": "Gemstones", "type": "semantic", "words": ("AMETHYST", "EMERALD", "OPAL", "RUBY")},
    {"label": "Musical instruments", "type": "semantic", "words": ("BANJO", "CELLO", "DRUM", "FLUTE")},
    {"label": "Dog breeds", "type": "semantic", "words": ("BEAGLE", "POODLE", "PUG", "TERRIER")},
    {"label": "Writing tools", "type": "semantic", "words": ("CRAYON", "MARKER", "PEN", "PENCIL")},
    {"label": "Baked goods", "type": "semantic", "words": ("BAGEL", "BROWNIE", "MUFFIN", "SCONE")},
    {"label": "Farm animals", "type": "semantic", "words": ("DONKEY", "GOAT", "HORSE", "SHEEP")},
    {"label": "Winter clothing", "type": "semantic", "words": ("GLOVES", "PARKA", "SCARF", "SWEATER")},
    {"label": "Flower types", "type": "semantic", "words": ("DAISY", "IRIS", "ROSE", "TULIP")},
    {"label": "Desk items", "type": "semantic", "words": ("CALENDAR", "LAMPSHADE", "NOTEPAD", "STAPLER")},
]

THEME_GROUPS: list[CategoryGroup] = [
    {"label": "At the beach", "type": "theme", "words": ("BUCKET", "SANDCASTLE", "SEASHELL", "TOWEL")},
    {"label": "On a camping trip", "type": "theme", "words": ("CAMPFIRE", "COMPASS", "COOLER", "LANTERN")},
    {"label": "At a movie theater", "type": "theme", "words": ("POPCORN", "PREVIEW", "PROJECTOR", "TICKET")},
    {"label": "In a detective story", "type": "theme", "words": ("ALIBI", "CLUE", "SUSPECT", "WITNESS")},
    {"label": "At the airport", "type": "theme", "words": ("GATE", "PASSPORT", "RUNWAY", "SUITCASE")},
    {"label": "At a bakery", "type": "theme", "words": ("APRON", "FROSTING", "MIXER", "YEAST")},
    {"label": "At a carnival", "type": "theme", "words": ("CAROUSEL", "MIDWAY", "PRIZES", "TICKETS")},
    {"label": "In a classroom", "type": "theme", "words": ("CHALKBOARD", "HOMEWORK", "LOCKER", "QUIZ")},
    {"label": "At a baseball game", "type": "theme", "words": ("BLEACHERS", "BULLPEN", "HOTDOG", "SCOREBOARD")},
    {"label": "Associated with Paris", "type": "theme", "words": ("BAGUETTE", "EIFFEL", "LOUVRE", "SEINE")},
]

FORM_GROUPS: list[CategoryGroup] = [
    {"label": "Starts with SH", "type": "form", "words": ("SHELL", "SHINE", "SHIRT", "SHOCK")},
    {"label": "Starts with BR", "type": "form", "words": ("BRANCH", "BRIDGE", "BRICK", "BROOK")},
    {"label": "Ends with ER", "type": "form", "words": ("BAKER", "BOXER", "DIVER", "JOKER")},
    {"label": "Contains OO", "type": "form", "words": ("BLOOM", "BOOK", "SPOON", "STOOL")},
    {"label": "Ends with IGHT", "type": "form", "words": ("BRIGHT", "FLIGHT", "MIGHT", "TIGHT")},
    {"label": "Starts with SN", "type": "form", "words": ("SNACK", "SNAKE", "SNOW", "SNUG")},
]

CATEGORY_BANKS: dict[str, list[CategoryGroup]] = {
    "semantic": SEMANTIC_GROUPS,
    "theme": THEME_GROUPS,
    "form": FORM_GROUPS,
}


def clone_group(group: CategoryGroup) -> CategoryGroup:
    """Return a mutable copy of one category group."""
    return {
        "label": str(group["label"]),
        "type": str(group["type"]),
        "words": list(group["words"]),
    }


def get_groups_for_type(group_type: str) -> list[CategoryGroup]:
    """Return a fresh copy of every group for one mechanism."""
    if group_type not in CATEGORY_BANKS:
        raise ValueError(f"Unknown group type: {group_type}")

    return [clone_group(group) for group in CATEGORY_BANKS[group_type]]


def find_group_by_label(group_type: str, label: str) -> CategoryGroup:
    """Return one copied group that matches a label exactly."""
    for group in CATEGORY_BANKS.get(group_type, []):
        if str(group["label"]) == label:
            return clone_group(group)

    raise ValueError(f"Could not find group '{label}' for type '{group_type}'.")
