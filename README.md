# Infinite Connections

## Project Overview

This project builds a lightweight generator for NYT-style **Connections** puzzles for the STA561 final project.

A Connections puzzle contains 16 words that should be partitioned into 4 groups of 4. Each group shares a hidden relationship, such as semantic meaning, a shared theme, or a shallow word-form pattern. The goal here is to generate new puzzles, not just solve existing ones.

For this course project, we want to:
1. generate new Connections-style puzzles,
2. avoid copying official puzzles,
3. reduce obvious multi-solution puzzles with practical heuristics,
4. show the results in a clean demo interface.

## What Is Implemented

The repo now includes a submission-ready v1.0 MVP with:

- a unified internal puzzle schema shared across loaders, generators, validators, and UI
- `src/load_data.py` for loading raw official puzzle data and saving normalized official puzzles
- separate generator modules for `semantic`, `theme`, and `form` mechanisms
- a puzzle assembly layer that combines four groups into one 16-word candidate puzzle
- exact duplicate checking against official normalized puzzles
- lightweight structure, style, and ambiguity/overlap validators
- a batch generation pipeline that saves accepted puzzles plus a generation report
- a minimal Streamlit app for viewing generated puzzles on a shuffled 4x4 board

## Generator Mechanisms

Current supported generation mechanisms:

- **Semantic**
  Example style: `Kitchen tools`, `Tree types`, `Chess pieces`
- **Theme**
  Example style: `At the beach`, `At the airport`, `In a detective story`
- **Form**
  Example style: `Starts with SH`, `Contains OO`, `Ends with IGHT`

The current generator is intentionally simple and bank-based. Each mechanism has its own small curated category bank, and the puzzle assembler mixes them into full candidate puzzles.

## Validation

Current validators include:

- **Structure validation**
  - exactly 4 groups
  - exactly 4 words per group
  - exactly 16 words total
  - each word used exactly once
  - `all_words` must match the flattened group words
- **Style validation**
  - rejects overly generic labels such as `VERBS` or `5-LETTER WORDS`
  - rejects labels that directly appear inside one of their own words when that makes the category too obvious
  - rejects repeated or near-identical category labels within the same puzzle
- **Ambiguity / overlap validation**
  - uses simple prefix/suffix surface-pattern heuristics
  - rejects puzzles that appear to create strong alternate groupings across multiple groups
  - intentionally stays lightweight rather than using a heavy solver
- **Exact duplicate validation**
  - preserves exact duplicate checking against official puzzles

## Repository Structure

```text
data/
  raw/
  processed/
  generated/

src/
  app/
  generators/
  validators/
  batch_generate_and_score.py
  load_data.py
  pipeline_demo.py

docs/
  Notes on schema and project design.

notebooks/
  Optional exploratory work.
```

## Puzzle Format

All components use the same internal schema:

```json
{
  "puzzle_id": "gen_000001",
  "source": "generated",
  "groups": [
    {
      "label": "Kitchen tools",
      "type": "semantic",
      "words": ["LADLE", "PEELER", "SPATULA", "WHISK"]
    },
    {
      "label": "Tree types",
      "type": "semantic",
      "words": ["CEDAR", "MAPLE", "OAK", "PINE"]
    },
    {
      "label": "At the beach",
      "type": "theme",
      "words": ["BUCKET", "SANDCASTLE", "SEASHELL", "TOWEL"]
    },
    {
      "label": "Starts with SH",
      "type": "form",
      "words": ["SHELL", "SHINE", "SHIRT", "SHOCK"]
    }
  ],
  "all_words": [
    "LADLE", "PEELER", "SPATULA", "WHISK",
    "CEDAR", "MAPLE", "OAK", "PINE",
    "BUCKET", "SANDCASTLE", "SEASHELL", "TOWEL",
    "SHELL", "SHINE", "SHIRT", "SHOCK"
  ]
}
```

The schema is unchanged from the project specification:

- `puzzle_id`
- `source`
- `groups`
- `all_words`

Each group stores:

- `label`
- `type`
- `words`

## How to Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Normalize official data:

```bash
python src/load_data.py
```

Run the simple pipeline demo:

```bash
python src/pipeline_demo.py
```

Run batch generation and scoring:

```bash
python src/batch_generate_and_score.py --num-candidates 200 --seed 561
```

Launch the Streamlit UI:

```bash
streamlit run src/app/app.py
```

## Batch Output Files

The batch script writes:

- `data/generated/accepted_puzzles.json`
- `data/generated/generation_report.json`

The report includes:

- total candidates generated
- rejected by duplicate check
- rejected by structure validation
- rejected by style validation
- rejected by ambiguity validation
- accepted count
- rough counts by generator type

## What Makes This a Good v1.0

This version is a good course-project MVP because it:

- clearly focuses on **generation**, not just solving
- uses **multiple explicit grouping mechanisms**
- preserves a **clean shared schema**
- includes **practical validation** instead of no filtering
- supports **batch generation** for producing many candidates
- includes a **simple web demo** for evaluation and presentation

It is small enough to understand quickly, but complete enough to demonstrate a coherent end-to-end puzzle generation pipeline.

## Known Limitations

- The generator is curated and bank-based, so category variety is still limited.
- The ambiguity filter is heuristic-based and does not guarantee unique solutions.
- The current system does not rank puzzles by human difficulty beyond the lightweight filters.
- Some accepted puzzles may still need manual review before being shown in a polished final demo.

## Notes

This repository is for a course final project focused on puzzle generation. The current implementation aims for clarity, reliability, and assignment alignment over heavy modeling or research complexity.
