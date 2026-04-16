# Puzzle Format

Internal puzzles should be stored as a JSON object with a consistent shape.

## Schema

```json
{
  "puzzle_id": "generated-example-001",
  "source": "generator/basic_generator",
  "groups": [
    {
      "label": "COLORS",
      "difficulty": 0,
      "words": ["BLUE", "GREEN", "RED", "YELLOW"]
    },
    {
      "label": "DOG BREEDS",
      "difficulty": 1,
      "words": ["BEAGLE", "COLLIE", "POODLE", "PUG"]
    }
  ],
  "all_words": [
    "BLUE",
    "GREEN",
    "RED",
    "YELLOW",
    "BEAGLE",
    "COLLIE",
    "POODLE",
    "PUG"
  ]
}
```

## Field Notes

- `puzzle_id`: A stable unique ID for the puzzle.
- `source`: Where the puzzle came from, such as `official`, `generator/basic_generator`, or another pipeline stage.
- `groups`: A list of category objects. Each group should include a human-readable `label`, a simple `difficulty` value, and a list of `words`.
- `all_words`: A flat list of every word in the puzzle. This should stay in sync with the words inside `groups`.

## Intended Conventions

- Store words as uppercase strings after normalization.
- Use exactly four groups of four words for a standard puzzle.
- Keep `all_words` derived from `groups` so there is only one source of truth for membership.
