# Infinite Connections

## Project Overview

This repository contains the STA561 **Infinite Connections** project: a generator for NYT-style Connections puzzles.

The original v1.0 pipeline is still present, but the main workflow now targets a more data-driven **v3.0** pipeline built on the earlier v2 architecture. It:

- ingests the HuggingFace `tm21cy/NYT-Connections` dataset,
- derives category banks and dataset statistics from official puzzles,
- mixes multiple generation mechanisms,
- validates puzzles for structure, duplication, ambiguity, multi-solution risk, and cohesion/confusion,
- batch-generates a library of accepted puzzles,
- and serves them in a Streamlit UI.

## What v3.0 Adds

The v3 pipeline extends the repo without removing the earlier MVP pieces.

- `src/data_utils/dataset_loader.py`
  Downloads or reads the HuggingFace dataset, normalizes each record into the shared internal schema, and saves:
  - `data/processed/nyt_official.json`
  - `data/processed/nyt_dataset_stats.json`
- `src/generators/semantic_generator.py`
  Uses dataset-derived semantic banks and an optional WordNet fallback.
- `src/generators/theme_generator.py`
  Uses dataset-derived theme groups plus a small curated theme bank.
- `src/generators/form_generator.py`
  Uses dataset-derived form categories plus generated prefix/suffix groups and a few curated rhyme/homophone sets.
- `src/generators/anagram_generator.py`
  Adds optional anagram-specific groups for variety.
- `src/generators/puzzle_assembler.py`
  Adds `generate_candidate_puzzle_v2(...)` and enforces mechanism variety.
- `src/validators/puzzle_validators.py`
  Adds a backtracking uniqueness check and similarity-based cohesion/confusion scoring.
- `src/batch_generate_and_score.py`
  Batch-generates and validates candidate puzzles, and can now generate until a target accepted-count is reached.
- `src/app/app.py`
  Loads puzzles from `accepted_v2.json` or generates one live on demand.

## Dataset Usage

The v3 loader targets the HuggingFace dataset:

- Dataset: `tm21cy/NYT-Connections`
- Source file: `ConnectionsFinalDataset.json`
- Normalized output: `data/processed/nyt_official.json`
- Statistics output: `data/processed/nyt_dataset_stats.json`

Each normalized puzzle uses the shared schema:

```json
{
  "puzzle_id": "nyt_0358",
  "source": "nyt_official",
  "groups": [
    {
      "label": "REMOVE, AS BODY HAIR",
      "type": "semantic",
      "words": ["LASER", "PLUCK", "THREAD", "WAX"]
    }
  ],
  "all_words": ["LASER", "PLUCK", "THREAD", "WAX", "..."]
}
```

The stats file stores:

- word frequency counts,
- category label frequency counts,
- inferred mechanism counts,
- a reusable word pool,
- and category banks split into `semantic`, `theme`, and `form`.

## Generator Mechanisms

v3 puzzle assembly mixes four groups with a variety constraint: every puzzle must include at least one `semantic` group and at least one `theme` group, plus additional `form` or `anagram` groups.

Current mechanism modules:

- `semantic`
  Uses official dataset categories and can optionally try WordNet if available.
- `theme`
  Uses official theme-like labels plus a curated bank such as cities, monsters, foods, and event contexts.
- `form`
  Uses official wordplay-style groups and dynamic shared-prefix/shared-suffix groups.
- `anagram`
  Uses explicit anagram sets to increase mechanism diversity.

## Validation

The v3 validator keeps the earlier lightweight checks and adds stronger filters:

- `validate_structure`
  Requires exactly 4 groups, 4 words per group, 16 total words, and no repeated words.
- `validate_style`
  Rejects labels that are generic, repeated, or too revealing.
- `validate_ambiguity_and_overlap`
  Rejects obvious cross-group surface conflicts.
- `exact_duplicate_check`
  Rejects exact duplicates of official puzzles.
- `solve_puzzle_backtracking`
  Searches valid 4-word partitions using the generator banks and counts how many full puzzle solutions exist.
- `embedding_score`
  Computes average within-group and cross-group similarity.
  If a spaCy model is installed, it will use that; otherwise it falls back to a lightweight lexical plus dataset-context representation.
- `validate_puzzle`
  Combines all checks and returns detailed rejection reasons and metrics.

## Batch Generation

Default output files:

- `data/generated/accepted_v2.json`
- `data/generated/generation_report_v2.json`

The batch script now supports:

- `--num-candidates`
- `--target-accepted`
- `--seed`
- `--within-threshold`
- `--cross-threshold`
- `--max-solutions`
- `--progress-every`
- `--force-refresh-dataset`

Example:

```bash
python src/batch_generate_and_score.py --target-accepted 10000 --num-candidates 13000 --seed 561
```

## Streamlit UI

The UI supports two puzzle sources:

- `Generate New Puzzle`
  Generates a fresh v3 puzzle and validates it before display.
- `Load from Library`
  Loads a puzzle from `data/generated/accepted_v2.json`, either randomly or by index.

The board is shown as a 4x4 grid, and revealed answers are color-coded in NYT-style yellow, green, blue, and purple.

## How to Run

Install the current project dependency set:

```bash
pip install -r requirements.txt
```

Build the official dataset assets:

```bash
python src/data_utils/dataset_loader.py
```

Generate the 10K accepted puzzle library:

```bash
python src/batch_generate_and_score.py --target-accepted 10000 --num-candidates 13000 --seed 561
```

Launch the app:

```bash
streamlit run src/app/app.py
```

## Repository Structure

```text
data/
  raw/
  processed/
  generated/

docs/
  puzzle_format.md
  v2_dataset_and_generation_report.md

src/
  app/
  data_utils/
  generators/
  validators/
  batch_generate_and_score.py
  load_data.py
  pipeline_demo.py
```

## v3 Library Snapshot

The checked-in `generation_report_v2.json` now comes from a full library-generation run with seed `561`:

- candidate budget: 20,000
- generated until target reached: 12,399
- accepted: 10,000
- target met: `True`
- acceptance rate: 80.65%
- rejected by structure: 122
- rejected by style: 861
- rejected by ambiguity: 969
- rejected by low cohesion: 447
- average within-group similarity of accepted puzzles: about `0.339`
- average cross-group similarity of accepted puzzles: about `0.003`

## Limitations

- The generator is still heuristic and bank-based, even though it is now data-driven.
- `solve_puzzle_backtracking` only searches solutions expressible through the current generator banks and pattern detectors, so it may still miss some alternate human-valid partitions.
- The similarity scorer uses a lightweight fallback when spaCy vectors are unavailable, so cohesion estimates are only approximate.
- Theme versus semantic labels are inferred heuristically from official labels, not hand-annotated.
- Puzzle quality is improved, but not guaranteed to meet the course's strongest human-evaluation target without manual review.

## Compatibility Note

The earlier v1 files and schema are still present so the original submission pipeline is not broken. The v3 workflow is additive and still uses the assignment-compatible outputs `nyt_official.json`, `accepted_v2.json`, and `generation_report_v2.json`.
