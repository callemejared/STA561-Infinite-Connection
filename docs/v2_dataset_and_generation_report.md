# V2 Dataset And Generation Report

## Dataset Summary

The v2 pipeline uses the HuggingFace `tm21cy/NYT-Connections` dataset and normalizes it into `data/processed/nyt_official.json`.

Statistics from the checked-in `data/processed/nyt_dataset_stats.json`:

- official puzzles: 652
- official answer groups: 2,608
- unique words: 5,435
- inferred mechanism counts:
  - semantic: 2,131
  - form: 339
  - theme: 138

Most frequent words in the official set:

1. `BALL` (18)
2. `RING` (16)
3. `FLY` (14)
4. `HEART` (14)
5. `CAN` (13)
6. `LEAD` (13)
7. `WING` (13)
8. `EGG` (12)
9. `LOVE` (12)
10. `BAR` (12)

Most frequent category labels:

1. `HOMOPHONES` (8)
2. `MUSICAL INSTRUMENTS` (5)
3. `FISH` (5)
4. `ANAGRAMS` (4)
5. `PALINDROMES` (4)
6. `EAT VORACIOUSLY` (4)
7. `MAGAZINES` (4)
8. `THINGS THAT ARE RED` (4)
9. `MUSIC GENRES` (4)
10. `DOG COMMANDS` (3)

## Generation Summary

The checked-in `data/generated/generation_report_v2.json` comes from the sanity run:

```bash
python src/batch_generate_and_score.py --num-candidates 100 --seed 561 --progress-every 25
```

Observed results:

- total candidates: 100
- accepted puzzles: 84
- acceptance rate: 84%
- rejected by structure: 0
- rejected by style: 5
- rejected by ambiguity: 10
- rejected by duplicate: 0
- rejected by multi-solution: 0
- rejected by low cohesion: 1
- rejected by high confusion: 0
- rejected by internal repeat: 0

Accepted-puzzle averages:

- average within-group similarity: 0.3225
- average cross-group similarity: 0.0035
- average solution count: 1.0

Mechanism mix during the sanity run:

- candidate groups:
  - theme: 121
  - semantic: 124
  - form: 132
  - anagram: 23
- accepted groups:
  - theme: 103
  - semantic: 102
  - form: 110
  - anagram: 21

## Interpretation

- The official dataset is dominated by semantic categories, with smaller but still useful theme and wordplay slices. That supports the v2 design choice of requiring at least one semantic group and one theme group, then filling the remaining slots with theme, form, or anagram mechanisms.
- The current validator is mostly rejecting puzzles for style leakage or cross-group ambiguity, which is a healthy sign: the generator is producing structurally valid puzzles, but some labels or surface patterns still need filtering.
- The multi-solution count stayed at `1.0` for the accepted sanity-run puzzles under the current backtracking search, but this should be treated as a heuristic success rather than a proof of uniqueness for every possible human interpretation.

## Remaining Caveats

- The similarity score is approximate, especially when the fallback lexical backend is used instead of spaCy vectors.
- Theme versus semantic labels are inferred automatically from official labels and are not manually annotated.
- A 100-candidate sanity batch is useful for smoke testing, but a full 10K run should still be inspected separately before final evaluation or presentation.
