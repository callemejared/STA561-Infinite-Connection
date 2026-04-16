# Infinite Connections

## Project Overview

This project builds an AI-assisted generator for NYT-style **Connections** puzzles.

A Connections puzzle contains 16 words that should be partitioned into 4 groups of 4. Each group shares a hidden relationship, such as semantic meaning, sound pattern, theme, or wordplay. The goal of this project is not to solve existing puzzles, but to generate new puzzles that are coherent, interesting, and ideally feel similar to real NYT Connections puzzles.

For this course project, we aim to:
1. build a puzzle generator,
2. avoid copying past official puzzles,
3. reduce the chance of multiple plausible solutions,
4. create a simple web interface for viewing generated puzzles.

## Project Goal

We want to generate large numbers of original Connections-style puzzles automatically.

Our system will:
- generate candidate groups using different grouping mechanisms,
- combine four groups into a 16-word puzzle,
- filter out low-quality puzzles,
- check whether a puzzle is too ambiguous or has multiple plausible solutions,
- present puzzles in a clean interface.

## Motivation

Generating Connections puzzles is harder than solving them. A good puzzle needs:
- four internally coherent groups,
- enough challenge to be interesting,
- enough separation to avoid accidental multiple solutions,
- some variety in style and difficulty.

Because of this, we are designing the generator as a pipeline instead of asking an LLM to generate a full puzzle in one shot.

## Core Idea

We will build separate generators for different group types, then combine them.

Planned group types:
- **Semantic groups**  
  Example: words with similar meaning or shared category
- **Theme groups**  
  Example: words associated with a city, movie, brand, sport, etc.
- **Sound / form groups**  
  Example: same prefix, rhyme, homophone pattern, spelling pattern
- **Wordplay groups**  
  Example: hidden shared structure, phrase-based trick, misleading overlap

After generating groups, we will:
- assemble candidate puzzles,
- compare them against past official puzzles,
- run validation checks,
- keep only the better candidates.

## Planned System Pipeline

**Step 1:**  
Collect and organize past Connections data for reference and duplication checking.

**Step 2:**  
Build several independent group generators.

**Step 3:**  
Generate candidate 4-word groups.

**Step 4:**  
Combine 4 groups into a 16-word puzzle.

**Step 5:**  
Run filtering and validation:
- exact duplicate check,
- overlap check,
- ambiguity check,
- heuristic or solver-based quality check.

**Step 6:**  
Show accepted puzzles in a simple web interface.

## Repository Structure

```text
data/
  Stores historical Connections data, reference word lists, and generated puzzle outputs.

src/
  Main source code.

src/generators/
  Code for different puzzle group generators.

src/validators/
  Code for duplicate checking, ambiguity filtering, and puzzle validation.

src/app/
  Simple web interface for generating and viewing puzzles.

docs/
  Project notes, design decisions, and write-up materials.

notebooks/
  Optional exploratory notebooks for testing ideas and prompts.
```

## Current Development Plan

**Phase 1:**  
Set up repository, organize historical data, and define puzzle format.

**Phase 2:**  
Implement a basic semantic/theme generator.

**Phase 3:**  
Implement validation rules and duplicate checks.

**Phase 4:**  
Build a simple UI.

**Phase 5:**  
Generate many candidate puzzles and evaluate quality.

## Puzzle Format

Each puzzle will be stored in a structured format such as JSON.

Example:

```json
{
  "groups": [
    {
      "label": "Birds",
      "words": ["eagle", "sparrow", "owl", "crow"],
      "type": "semantic"
    },
    {
      "label": "Colors",
      "words": ["red", "blue", "green", "yellow"],
      "type": "semantic"
    },
    {
      "label": "Starts with 'sh'",
      "words": ["ship", "shoe", "shell", "shock"],
      "type": "sound_or_form"
    },
    {
      "label": "Associated with New York",
      "words": ["subway", "broadway", "yankees", "manhattan"],
      "type": "theme"
    }
  ]
}
```

## Evaluation Goals

A good generated puzzle should:
- contain 4 meaningful groups,
- not exactly match a past official puzzle,
- avoid obvious multi-solution structure,
- feel natural and interesting to a human player,
- resemble the style of real Connections puzzles.

## Initial Tech Stack

- Python
- pandas
- json
- nltk or other word-related libraries
- optional LLM API for candidate generation or editing
- Streamlit or Gradio for the web interface

## How to Run

This section will be updated as implementation progresses.

Tentative workflow:
1. install dependencies
2. load historical puzzle data
3. run a generator script
4. validate generated puzzles
5. launch the local web interface

Example future commands:
- `python src/generate_puzzles.py`
- `python src/validate_puzzles.py`
- `streamlit run src/app/app.py`

## What Is Implemented So Far

Currently in progress:
- project planning
- repository setup
- README drafting
- system design for generator + validator pipeline

## Next Steps

Immediate next tasks:
1. define a standard JSON format for puzzles,
2. add past official puzzle data,
3. implement a first simple generator,
4. implement duplicate detection,
5. generate and inspect sample outputs,
6. build the first version of the interface.

## Notes

This repository is for a course final project.  
The project focuses on puzzle generation, not only puzzle solving.  
The system will likely combine rule-based methods, curated data, and AI-assisted generation.
