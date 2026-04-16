# V3 Dataset And Generation Report

## Dataset Summary

The v3 pipeline uses the HuggingFace `tm21cy/NYT-Connections` dataset and normalizes it into `data/processed/nyt_official.json`.

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

The checked-in `data/generated/generation_report_v2.json` now comes from the formal library-generation run:

```bash
python src/batch_generate_and_score.py --target-accepted 10000 --num-candidates 13000 --seed 561
```

Observed results:

- target accepted puzzles: 10,000
- target met: `True`
- candidate budget chosen by the script: 20,000
- candidates actually generated before stopping: 12,399
- accepted puzzles: 10,000
- acceptance rate: 80.65%
- rejected by structure: 122
- rejected by style: 861
- rejected by ambiguity: 969
- rejected by duplicate: 0
- rejected by multi-solution: 0
- rejected by low cohesion: 447
- rejected by high confusion: 0
- rejected by internal repeat: 0

Accepted-puzzle averages:

- average within-group similarity: about 0.339
- average cross-group similarity: about 0.003
- average solution count: 1.0

## Interpretation

- The official dataset is dominated by semantic categories, with smaller but still useful theme and wordplay slices. That supports the current design choice of requiring at least one semantic group and one theme group, then filling the remaining slots with theme, form, or anagram mechanisms.
- The main causes of rejection are still style leakage and ambiguity, which is expected for a generator that intentionally mixes different mechanisms.
- The library now satisfies the practical assignment goal of having at least 10K accepted puzzles available in the checked-in output file.
- The multi-solution count stayed at `1.0` for accepted puzzles under the current backtracking search, but this should still be treated as a heuristic success rather than a formal proof of uniqueness for every possible human interpretation.

## Remaining Caveats

- The similarity score is approximate, especially when the fallback lexical backend is used instead of spaCy vectors.
- Theme versus semantic labels are inferred automatically from official labels and are not manually annotated.
- Even with a 10K accepted library, some puzzles may still benefit from human review before final presentation or grading.
