# Puzzle Format

All generators, validators, loaders, and UI components should use the same
internal puzzle schema.

## Standard Puzzle Schema

```json
{
  "puzzle_id": "gen_000001",
  "source": "generated",
  "groups": [
    {
      "label": "Birds",
      "type": "semantic",
      "words": ["eagle", "crow", "owl", "sparrow"]
    },
    {
      "label": "Colors",
      "type": "semantic",
      "words": ["red", "blue", "green", "yellow"]
    },
    {
      "label": "Associated with New York",
      "type": "theme",
      "words": ["subway", "broadway", "yankees", "manhattan"]
    },
    {
      "label": "Starts with sh",
      "type": "form",
      "words": ["ship", "shoe", "shock", "shell"]
    }
  ],
  "all_words": [
    "eagle", "crow", "owl", "sparrow",
    "red", "blue", "green", "yellow",
    "subway", "broadway", "yankees", "manhattan",
    "ship", "shoe", "shock", "shell"
  ]
}
```

## Field Definitions

- `puzzle_id`: A unique identifier such as `gen_000001` or `official_000123`.
- `source`: Where the puzzle came from, such as `generated` or `official`.
- `groups`: A list of 4 answer groups. Each group must include `label`, `type`,
  and `words`.
- `all_words`: A flat list of all 16 words in the puzzle.

## Important Rules

1. `all_words` must always be present.
2. The words inside each group should stay in their original order in stored
   puzzle objects.
3. Duplicate checking may sort group words temporarily for comparison.
4. `label` must always be stored internally, even if it is hidden from players.
5. Use `type` instead of `difficulty` inside each group.
6. All generators, validators, loaders, and docs must follow this schema.
