# Infinite Connections Project Description

## Project Overview

The Infinite Connections project is a generator for puzzles similar to the New York Times *Connections* puzzle. The goal of the project is to automatically construct puzzles containing four groups of four words each, where each group has a clear thematic, semantic, or formal relationship, while also ensuring that the puzzle has a certain level of difficulty and misleadingness. The design of the project has gone through multiple iterative versions (v1-v6), developing from an initial proof of concept into the final submission version, and provides a complete toolchain for data loading, puzzle generation, batch production, validation, and visualization. In the current `main` branch, the code is based on the low-cost batch generator from v5 and uses independently authored semantic/theme/form/anagram banks, while ensuring that these banks do not overlap with the official New York Times puzzle bank.

This repository contains three complementary workflows: the v4 high-quality pipeline, the v5 large-scale low-cost pipeline, and the v6 final submission pipeline, where the v6 branch introduces original banks and strict independence checks while ensuring generation speed.

## Version Iteration History

The project has gone through six major versions, each improving on the previous one. The following summary will help readers understand the technical evolution of each version:

### v1 - Prototype Verification

Goal: Verify whether it is feasible to construct a puzzle with 4 groups and 16 words in total according to the Connections rules.  
Functions: Implement the most basic loader, parse the official dataset, and establish the group structure; prove the feasibility of word grouping and the basic puzzle structure.  
Shortcomings: Only a functional verification, lacking systematic bank management, difficulty evaluation, and validation mechanisms.

### v2 - Dataset Loading and Standardization

Goal: Convert the official dataset into a unified internal format and provide a unified bank for subsequent generators.  
Functions:

- Using the `tm21cy/NYT-Connections` dataset provided by Hugging Face, download the raw JSON to `data/raw/nyt_connections_hf.json`, and save the normalized puzzles to `data/processed/nyt_official.json`.
- Use the function `build_dataset_assets()` to standardize the official data, extract semantic, theme, and form banks, and collect information such as word frequency, label frequency, and prefix/suffix patterns.
- Infer the category of each official group (`semantic`, `theme`, or `form`), and build category banks and word-frequency statistics. These statistics are used in later versions to determine group difficulty and filtering rules.

Improvement: Established a unified data format and basic bank management for subsequent generators, and provided a foundation of word-frequency and label statistics for difficulty evaluation.

### v3 - Baseline Generator and Preliminary Validation

Goal: Build a basic puzzle generation and assembly pipeline on the unified bank, and add a preliminary validation and visualization interface.  
Functions:

- Introduce group generators (`semantic/theme/form/anagram`) and an assembler, enabling candidate groups to be generated from the bank and assembled into complete puzzles.
- Introduce a preliminary puzzle validation module to check basic structural correctness and simple duplication/ambiguity issues.
- Add a Streamlit frontend so users can generate and play puzzles online.

Limitations: v3 lacks systematic evaluation of group difficulty, has low generation efficiency, and produces puzzles with relatively unstable quality.

### v4 - High-Quality Validation Pipeline

Goal: Strengthen difficulty control, ambiguity detection, and puzzle quality on the basis of v3, and introduce a stricter validator.

Main features:

#### Generation/Assembly Flow

v4 retains the basic structure of v3, but comprehensively upgrades the loader, generator, assembler, and validator, forming a complete quality-oriented pipeline:

- Data loading: `src/data_utils/dataset_loader.py` loads and standardizes the official dataset while also building pattern statistics (such as prefix/suffix frequencies) to support form-group filtering.
- Resource management: `src/generators/generator_resources.py` is responsible for loading shared semantic, theme, form, and anagram banks, and provides auxiliary tools such as WordNet, pronunciation libraries, word frequency, and blacklists.
- Group generators: `semantic_generator.py`, `theme_generator.py`, `form_generator.py`, and others are responsible for generating candidate semantic, theme, and form groups and attaching difficulty metadata. The generators filter out candidates that are obviously self-revealing or overly vague.
- Similarity tools: `similarity_tools.py` uses GloVe word vectors to provide similarity calculations between words, and falls back to morphology-based approximations when word vectors are unavailable.
- Puzzle analysis: `puzzle_analysis.py` calculates puzzle-level difficulty, decoy/interference, ambiguity, and word isolation, providing detailed metrics for validation.
- Puzzle assembly: `puzzle_assembler.py` assembles 4 groups according to conditions such as difficulty tiers and rhyme-ending constraints, using a weighted selection strategy to balance misleadingness and ambiguity risk.
- Validator: `validators/puzzle_validators.py` rechecks issues such as structure, duplication, difficulty coverage, misleadingness, rhyme-ending conflicts, and singleton words, and outputs detailed rejection reasons.

#### Difficulty Control

- Semantic groups use WordNet hypernym depth to evaluate concept specificity; the greater the depth, the more specific and therefore the harder the group.
- Form groups evaluate difficulty based on the coverage of the shared pattern across the entire bank; the smaller the coverage, the greater the difficulty.
- Theme groups measure "distractibility" by calculating how strongly outside words relate to the label; the more related words there are, the harder the group.

#### Misleadingness and Similarity

v4 uses GloVe vectors to actively add misleading words, increasing puzzle challenge by controlling cross-group similarity while avoiding excessive ambiguity.

#### Rhymes and Pronunciation

With the help of the `pronouncing` library (CMU Pronouncing Dictionary), rhyme endings are identified, shared-rhyme-ending groups are constructed, and two rhyme-based groups with the same rhyme ending are forbidden from appearing in the same puzzle.

#### Batch Generation

`batch_generate_and_score.py` provides batch generation, allowing parameters such as the number of generated candidates, target accepted count, and random seed to be specified, and outputs both generation reports and accepted puzzles.

Advantages and disadvantages: v4 provides high-quality puzzles, but generation cost is high, making it suitable for single puzzles or small-batch generation and difficult to support the 10K-scale competition requirement.

### v5 - Low-Cost Batch Generation

Goal: Provide a fast large-scale generation pipeline for competition needs, significantly reducing the cost of generating a single puzzle and trading off some quality guarantees for high throughput.

Improvements:

- Low-cost batch generator: `puzzle_generator_v5.py` adopts a preprocessing mode, loading all candidate groups once, building a compatibility graph, and then directly sampling four compatible group combinations on the graph, avoiding the expensive per-puzzle generation and validation loop in v4.
- Compatibility constraints: During graph construction, the compatibility of each pair of groups is computed (no repeated words, labels, rhyme endings, mechanisms, or theme frames), thereby ensuring rapid sampling.
- Mechanism families and theme frames: Compute `mechanism_family` and `theme_frame_family` for each group, avoiding repeated mechanism types or identical theme frames during sampling and thereby making puzzles more diverse.
- Cheap metrics: v5 no longer computes complex distractibility or ambiguity scores, instead using group compatibility, category usage counts, and a small amount of randomness to rank candidate groups.
- Batch output: `batch_generate_v5.py` can generate tens of thousands of puzzles at once and produce a generation report including runtime, generation rate, mechanism-family statistics, theme-frame statistics, and difficulty statistics.
- Interface: `src/app/Evaluation.py` provides a reviewer dashboard that allows the generation of 10K puzzles and sampled inspection; `src/app/pages/Play.py` provides the player interface, including a 4x4 grid, shuffle/submit/deselect operations, error prompts, and a share string.

Main differences:

- v5 removes the complex validation in v4 and retains only structural hard constraints, greatly increasing generation speed.
- v5 uses reused banks, so generated groups may contain groups from the official bank; it is suitable for the competition training stage rather than the final submission.

### v6 Final - Submission Version

Goal: On the basis of v5's high throughput, satisfy the strict requirements of the final competition submission, namely that all semantic, theme, form, and anagram groups must be generated entirely from independently authored banks and must not overlap with the official New York Times bank.

Core changes:

- Independence checks: At runtime, compare the signatures of the independent semantic/theme/form/anagram banks with the official bank, and fail immediately if any overlap is found, ensuring that the final submitted puzzles are completely original.
- Low-cost final generator: `puzzle_generator_v6.py` maintains a compatibility-sampling strategy similar to v5, but further tightens the candidate-list cap (`SELECTION_CANDIDATE_CAP`) and generation attempt multiplier (`GENERATION_ATTEMPT_MULTIPLIER`), and sets limits on the number of semantic, theme, and form groups in each puzzle in order to maintain the speed of 10K-scale generation.
- Independent bank loading: `load_independent_semantic_bank()`, `load_independent_theme_bank()`, `load_independent_form_bank()`, and `load_independent_anagram_bank()` load the semantic, theme, form, and anagram banks written by the team, and use standardized signatures to check for overlap with the official bank.
- Cache clearing and warm start: v6 provides the function `clear_v6_runtime_caches()` to clear caches before batch generation, ensuring that the statistics show a more realistic initialization time.
- Type caps and compatibility: During sampling, separate maximum counts are set for semantic groups, theme groups, and form groups (defaulting to 1/2/2), preventing too much repetition of the same mechanism type within a puzzle.
- Output format: The generator records, for each puzzle, the bank modes used, such as `semantic_bank_mode` and `official_overlap_check`, in order to prove that the independence checks have passed.
- Interface adjustments: `src/app/Evaluation.py` focuses by default on generation and review; `src/app/pages/Play.py` provides the final player interface, allowing users to click once to generate a final puzzle and experience the complete gameplay process.

Summary of differences: Compared with v5, the biggest difference in v6 is the source of the semantic/theme/form/anagram banks and the independence checks; compared with v4, v6 abandons complex per-puzzle validation and still maintains low-cost generation, but adds bank independence and a small number of diversity limits, making it the final version suitable for large-scale submission.

## Architecture and Key Modules

To better understand this project, we introduce the main modules in the order from data processing to puzzle generation and then to interface presentation.

### 1. Data Loading and Standardization

Data source: The project uses the `tm21cy/NYT-Connections` dataset on Hugging Face, which contains hundreds of official puzzles and their four answer groups. The loader supports downloading data from a remote URL and caching it locally.

Standardization flow:

- `download_hf_dataset()` downloads the raw JSON (saved by default to `data/raw/nyt_connections_hf.json`).
- `normalize_hf_dataset()` converts each raw record into a unified internal format, including `puzzle_id`, the four groups' `label`, `words`, and grouping type `type`.
- `build_category_banks()` divides the standardized puzzle groups into semantic, theme, and form categories according to type, deduplicates them, and outputs category banks.
- `collect_dataset_statistics()` counts word frequency, label frequency, number of mechanisms, prefix/suffix patterns, and other information for difficulty estimation and filtering.

Inferring group type: `infer_group_type()` determines the mechanism type of a group (`semantic/theme/form`) based on the group label, word pattern, and common hint words. For example, labels containing keywords such as `___` or `ANAGRAM` are classified as form groups.

### 2. Resources and Helper Functions (`generator_resources`)

- Shared bank loading: This module provides methods to load and cache semantic, theme, form, and anagram banks and their metadata, including reading independent banks and official banks and computing standardized signatures.
- Difficulty/pattern recognition: It provides functions for detecting form subtypes (prefix, suffix, rhyme, homophone), pattern values, WordNet hierarchy depth, pronunciation, and rhyme-ending extraction, supplying foundational information for generators and validators.
- Independence checks: In v6, when independent banks are loaded, the label+word signatures are computed and compared with the official banks, and an error is raised if any duplication exists.

### 3. Group Generators

The generators construct candidate groups into a unified format according to mechanism type and attach difficulty information.

#### 3.1 Semantic Groups (`semantic_generator`)

Sources: Official semantic bank, independent semantic bank, and other backup groups.

Filtering rules:

- No repeated words may appear in the group.
- The label must not directly reveal the words.
- At least two words must not belong to an overly broad alternative category (such as `person` or `animal`).

Difficulty metric: Use WordNet hypernym depth; the more specific the concept is (the greater the depth), the higher the difficulty.

#### 3.2 Form Groups (`form_generator`)

Sources: Official form bank, independent form bank, dynamically constructed shared-prefix/shared-suffix groups, rhyme-ending groups, homophone groups, and so on.

Filtering rules:

- Block patterns in the blacklist (such as high-frequency prefixes/suffixes), and filter out patterns whose coverage exceeds 30%.
- Forbid self-revealing groups or the recreation of existing rhyme endings.
- Avoid groups whose words also form overly broad semantic categories.

Difficulty metric: Compute the number of words matching the pattern; the fewer there are, the higher the difficulty.

#### 3.3 Theme Groups (`theme_generator`)

Sources: Official theme bank, independent theme bank, and manually curated backup themes.

Filtering rules: Likewise, groups must not contain repeated words or self-revealing labels, and word vectors are used to evaluate similarity and distractibility between words and labels.

Difficulty metric: Estimate how many outside words are associated with the theme label; the more associations there are, the greater the misleadingness and the higher the difficulty.

#### 3.4 Anagram Groups (`anagram_generator`)

Sources: Construct all possible anagram groups from the existing bank (four words are mutual anagrams).

Filtering rules: Ensure that they do not duplicate official form groups; provide the anagram-group generation function `list_independent_anagram_groups_v6()` for the v6 independent bank.

### 4. Word Vectors and Misleadingness (`similarity_tools`)

GloVe vectors: The project uses `gensim.downloader` to load the `glove-wiki-gigaword-50` word vectors, which are used during generation and validation to measure similarity between words and labels or other words.

Misleading strategy: During assembly, v4 actively selects some words that also seem plausible under other groups' labels, creating a "decoy" effect and increasing puzzle interest, while using thresholds to prevent excessive ambiguity.

When word vectors are unavailable: If the vectors cannot be loaded, the system falls back to trigram similarity based on word form.

### 5. Pronunciation and Rhyme Endings (`pronouncing` and rhyme logic)

The project uses the `pronouncing` library (a wrapper around the CMU Pronouncing Dictionary) to identify the pronunciation of words and extract rhyme endings through `rhyme_ending()`, which is used to construct rhyme groups.

To ensure puzzle quality, the generator requires that no two rhyme-based groups sharing the same rhyme ending appear in the same puzzle.

v4 also adds a spelling-based tail check to prevent confusion caused by words that have different pronunciations but the same spelling tail.

### 6. Puzzle Analysis (`puzzle_analysis`)

Purpose: Evaluate overall puzzle quality after assembly, including metrics such as difficulty, misleadingness, ambiguity, and singleton words.

Metrics:

- `interference_score`: Measures the degree of misleadingness between different groups.
- `decoy_group_count`: Counts the number of tempting words each group provides to other groups.
- `ambiguous_word_count`: Counts overly ambiguous words.
- `singleton_word_count`: Detects singleton words (words that have no misleading effect at all).
- `average_within_group_similarity` and `average_cross_group_similarity`: Measure within-group and cross-group similarity.

Function: These metrics are used by the validator to decide whether a candidate puzzle meets the quality standards of v4.

### 7. Puzzle Assembly (`puzzle_assembler`, v4)

Mechanism plan: v4 randomly chooses among three mechanism orders (such as `[semantic, theme, form, semantic]`) and randomly assigns difficulty tiers (`easy`, `medium`, `hard`) to the four groups.

Compatibility checks: Whenever a candidate group is selected, repeated words, labels, and rhyme endings are checked, and difficulty and mechanism balance must be satisfied.

Candidate scoring: Scores are computed using interference, ambiguity penalties, base difficulty, and a small amount of noise, and the best candidates are selected by weight.

Analysis and validation: After assembly is completed, `puzzle_analysis.analyze_puzzle_groups()` is called to compute all metrics, and the puzzle is returned only if all thresholds are satisfied; otherwise, attempts continue until the maximum number of attempts is reached.

### 8. Low-Cost Batch Generator v5

`puzzle_generator_v5.py` quickly generates a large number of puzzles through the following steps:

- Preprocessing: Call `list_semantic_groups()`, `list_theme_groups()`, `list_form_groups()`, and `list_anagram_groups()` once to obtain all candidate groups and filter out structurally invalid groups.
- Normalized records: Each candidate group is converted into a `GroupRecord`, storing information such as the word-key set, mechanism family, theme frame, and difficulty tier.
- Compatibility graph construction: Precompute the compatibility of any two groups and store all compatible groups in adjacency lists so that sampling can query them quickly.
- Sampling strategy: Use backtracking weighted sampling, rank candidates according to mechanism usage counts and theme-frame usage counts, and randomly choose four compatible groups.
- Duplicate control: Use signatures (sorted by word sets) to identify duplicate puzzles, trying to skip duplicates early and allowing duplicates later for speed.
- Output: Build a puzzle object and record generation metadata such as group mechanism families and theme frames for evaluation and statistics.

### 9. Final Submission Generator v6

In v6, the generator `puzzle_generator_v6.py` retains the compatibility-sampling framework of v5, but strengthens the input source and sampling strategy:

- Independent bank loading: Use `load_independent_semantic_bank()`, `load_independent_theme_bank()`, `load_independent_form_bank()`, and `load_independent_anagram_bank()` to load completely independent banks and reject signatures contained in the official banks.
- Compatibility graph: Combine the semantic, theme, form, and anagram banks, then filter invalid groups and build the compatibility adjacency list.
- Type buckets and caps: Assign each group a `type_bucket` (`semantic`, `theme`, `form_like`) and set caps: each puzzle may contain at most 1 semantic group, 2 theme groups, and 2 form/anagram groups.
- Candidate ordering: Order candidates only according to compatibility (adjacency degree) and randomness, avoiding the global usage counts of v5 in order to reduce backtracking.
- Duplicate control: Similar to v5, use signatures to skip duplicate puzzles during generation, but allow duplicate restrictions to loosen later in the generation process to guarantee output volume.
- Generation metadata: The `generation` field of each puzzle records bank-source modes and independence-check results, such as `semantic_bank_mode: independent_v6` and `official_overlap_check: passed`.

### 10. Validator (`validators/puzzle_validators.py`)

Although v5 and v6 no longer run heavy validation in the main generation loop, the validator can still be used for analysis and scoring. Its main checks include:

- Structural validity: Whether there are 4 legal groups and no repeated words.
- Difficulty coverage: Includes at least one easiest and one hardest difficulty group.
- Misassigned-word detection: Prevents a word from fitting another label significantly better.
- Induction and ambiguity: Measures cross-group similarity and misleadingness to avoid overly vague puzzles.
- Rhyme-ending conflicts: Ensures that rhyme endings do not repeat within a puzzle.
- Singleton words: Rejects isolated words that have no misleading effect whatsoever.

These checks are mandatory in v4, while in v5/v6 they are more often used for evaluation and scoring rather than as blocking generation conditions.

## Repository Structure and Main Files

The project's code is distributed across the `data/`, `docs/`, and `src/` directories, among which the `src/` directory contains the main generation logic. According to the current `main` branch, the key added or modified files include:

| Version | Added/Modified Files | Function Summary |
| --- | --- | --- |
| v4 | `src/generators/similarity_tools.py`, `src/generators/puzzle_analysis.py` | Added similarity tools and puzzle-analysis modules for computing word-vector similarity and interference |
|  | `src/data_utils/dataset_loader.py` and multiple generator and validator modules | Improved the loader, generators, assembler, and validator to implement the high-quality pipeline |
|  | `data/raw/form_pattern_blacklist.txt` | Form-group pattern blacklist to improve filtering quality |
| v5 | `src/generators/puzzle_generator_v5.py`, `src/batch_generate_v5.py` | Added the v5 low-cost batch generator and batch script |
|  | `src/app/Evaluation.py`, `src/app/pages/Play.py` | Updated the Streamlit dashboard and player interface |
| v6 | `src/generators/puzzle_generator_v6.py`, `src/batch_generate_v6.py` | Added the v6 final generator and batch script |
|  | `src/app/final_game_logic.py`, `src/app/pages/Play.py` | Added player-state logic and the final player interface |
|  | Modified `src/generators/generator_resources.py`, `src/generators/semantic_generator.py`, `src/app/app.py` | Support independent banks, independence checks, and default interface adjustments |

The overall directory structure is as follows:

```text
project_root/
├── data/             # Data directory, divided into raw / processed / generated
│   ├── raw/
│   ├── processed/
│   └── generated/    # Generated puzzle libraries and generation reports
├── docs/             # Documentation directory, such as puzzle_format.md, v2_dataset_and_generation_report.md
├── src/              # Source code directory
│   ├── app/          # Streamlit app and pages
│   ├── data_utils/   # Data loading and standardization
│   ├── generators/   # Generators and helper modules for each version
│   ├── validators/   # Validator modules
│   ├── batch_generate_and_score.py  # v4 batch-generation script
│   ├── batch_generate_v5.py         # v5 batch-generation script
│   ├── batch_generate_v6.py         # v6 batch-generation script
│   └── ...
└── requirements.txt  # Python dependency list
```

## Usage Guide

### Environment Setup

Clone the repository and use the `main` branch.

Install dependencies:

```bash
pip install -r requirements.txt
```

### Build or Refresh the Dataset

Before using the generator, you need to download and standardize the official dataset (for certain statistics and helper information). Run:

```bash
python src/data_utils/dataset_loader.py
```

This command will download the dataset (if no local cache exists), generate the standardized files `data/processed/nyt_official.json` and `data/processed/nyt_dataset_stats.json`, and output a summary of bank statistics.

### Generate Puzzle Libraries

Depending on the generator, the following commands can be used to generate batch puzzle libraries:

#### v4 High-Quality Single-Puzzle/Small-Batch Generation

```bash
python src/batch_generate_and_score.py --target-accepted 100 --num-candidates 250 --seed 561
```

This command will attempt to generate 250 candidate puzzles and accept 100 of them, using heavy validation to ensure quality. The generated results are saved to `data/generated/accepted_v4.json` and `generation_report_v4.json`.

#### v5 Large-Scale Generation (Competition Training)

```bash
python src/batch_generate_v5.py --count 10000 --seed 561
```

In v5, the generator will rapidly produce 10K puzzles and output `data/generated/generated_v5.json` and `generation_report_v5.json`.

#### v6 Final Submission Batch Generation

```bash
python src/batch_generate_v6.py --count 10000 --seed 561
```

The v6 generator uses independent banks and performs independence checks. The results are saved to `data/generated/generated_v6_final.json` and `generation_report_v6_final.json`.

During generation, the `--seed` parameter can be used to guarantee reproducibility; for v4, options such as `--within-threshold`, `--cross-threshold`, and `--max-solutions` can be adjusted to control validation strictness.

### Start the Streamlit App

Use the following command to start the web application:

```bash
streamlit run src/app/app.py
```

In the `main` branch, the default homepage is the Play page, and the sidebar also exposes the Evaluation page for generating and reviewing puzzle libraries.

### Common Issues and Tips

- Random seed: Using `--seed` in batch generation ensures that each run produces the same puzzle order, making debugging and reproduction easier.
- Performance: The v5/v6 generators depend on a preprocessed compatibility graph and have relatively high memory usage, so it is recommended to run them in an environment with more memory.
- Independent banks: To update the independent banks in v6, you need to prepare new JSON files in `data/` or a custom directory and modify the corresponding loading paths in `generator_resources.py`.
- Custom difficulty range: v4 can control the quality of generated puzzles by adjusting validation thresholds, such as increasing `MIN_DECOY_GROUP_COUNT` or adjusting `MIN_INTERFERENCE_SCORE`, to obtain more challenging puzzles.

## Conclusion

Through six versions of iteration, the Infinite Connections project has developed a complete puzzle-generation ecosystem:

- v1/v2 establish the basic data structures and banks;
- v3 introduces generators and preliminary validation;
- v4 builds a heavily validated high-quality pipeline, providing precise difficulty control, decoy design, and rhyme filtering;
- v5 adopts a compatibility-graph sampling strategy for competition needs, significantly increasing generation speed and providing review and player interfaces;
- v6 introduces independent banks and strict independence checks while maintaining the high throughput of v5, ensuring that the final submitted puzzles are completely original.

Whether for teaching, competition, or personal entertainment, this project provides rich tools and flexible configuration, capable of generating both high-quality single puzzles and large numbers of puzzles for review and gameplay. Readers can choose appropriate versions and modules according to their needs and further extend or improve the generator.
