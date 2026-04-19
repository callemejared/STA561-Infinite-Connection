# Infinite Connections

## Project Overview

This repository contains the STA561 **Infinite Connections** project: a generator for NYT-style Connections puzzles.

The active workflow is now the **v4** pipeline. It keeps the v3 repository structure, but extends the existing loader, generators, assembler, validator, batch runner, and Streamlit app so puzzles have:

- stronger difficulty calibration,
- deliberate but controlled misleadingness,
- phoneme-level rhyme handling,
- earlier rejection of trivial form groups,
- and unified v4 naming for generation functions and outputs.

## v4 Architecture

The v4 pipeline still follows the same high-level flow:

1. `src/data_utils/dataset_loader.py`
   Loads the HuggingFace `tm21cy/NYT-Connections` dataset, normalizes it into the shared schema, builds reusable category banks, and now also persists pattern-frequency statistics for the word pool.
2. `src/generators/generator_resources.py`
   Loads the reusable banks and word pool, reads the external form-pattern blacklist, exposes WordNet/pronouncing helpers, and provides shared scoring/filtering utilities.
3. `src/generators/semantic_generator.py`, `theme_generator.py`, `form_generator.py`
   Build and prefilter candidate groups, attach normalized v4 difficulty metadata, and reject self-revealing or overly ambiguous candidates before assembly.
4. `src/generators/similarity_tools.py`
   Provides pretrained-vector similarity through `gensim` GloVe embeddings, with a lexical fallback if embeddings are unavailable.
5. `src/generators/puzzle_analysis.py`
   Computes puzzle-level difficulty, decoys, ambiguity signals, singleton-word risk, and cross-group interference.
6. `src/generators/puzzle_assembler.py`
   Assembles four groups under difficulty-tier, misleadingness, rhyme-ending, and ambiguity constraints using seeded randomness.
7. `src/validators/puzzle_validators.py`
   Re-validates structure, style, ambiguity, difficulty profile, singleton-word checks, duplicate risk, multi-solution risk, and similarity metrics.
8. `src/batch_generate_and_score.py`
   Batch-generates accepted puzzles into `accepted_v4.json` with a corresponding `generation_report_v4.json`.
9. `src/app/app.py`
   Loads `accepted_v4.json` or generates a fresh v4 puzzle in Streamlit.

## Data Loading And Resources

The loader still writes:

- `data/processed/nyt_official.json`
- `data/processed/nyt_dataset_stats.json`

v4 extends the saved statistics with `pattern_statistics`, including reusable prefix and suffix counts over the alphabetic word pool. Those stats support the new form-group rarity filtering and README-visible reporting.

The form generator also loads an external blacklist from:

- `data/raw/form_pattern_blacklist.txt`

Patterns in that file, or any spelling/phonetic pattern covering more than 30% of the reusable word pool, are treated as too broad and filtered out before puzzle assembly. This prevents trivial groups such as words that all begin with a meaningless high-frequency chunk.

## Group Generation

### Semantic Groups

Semantic groups come from the official semantic bank plus curated fallback banks. v4 rejects a semantic candidate if:

- it repeats a word,
- its label directly reveals one of its words,
- or two or more words also collapse into a broad alternate category such as `person`, `animal`, `food`, `place`, `plant`, or `body_part`.

**Difficulty metric:** WordNet concept specificity.

For each semantic label, v4 looks up noun synsets in WordNet and uses the minimum hypernym depth (`synset.min_depth()`) as a specificity signal. Deeper concepts are treated as harder. The raw depths are normalized across the semantic bank and mapped into `easy`, `medium`, and `hard`.

### Form Groups

Form groups come from:

- the official form bank,
- curated fallback form groups,
- dynamic shared-prefix groups,
- dynamic shared-suffix groups,
- phoneme-level rhyme groups,
- and phoneme-level homophone groups.

v4 filters form groups if:

- the spelling/phonetic pattern is blacklisted,
- the pattern covers more than 30% of the word pool,
- the group is self-revealing,
- the group reuses a rhyme ending already chosen for the same puzzle,
- or the words also create an overly broad alternate category.

**Difficulty metric:** pattern rarity.

The fewer words in the reusable word pool that match the group’s pattern, the higher the difficulty. v4 stores the match count, coverage ratio, normalized difficulty score, and tier for every form group.

### Theme Groups

Theme groups still come from the official theme bank plus curated fallbacks, but they now receive the same ambiguity/self-reveal prefilters as semantic groups.

**Difficulty metric:** distractibility.

At load time, v4 estimates how many outside words in the full reusable word pool still point toward the theme label. During assembly, that score is adjusted again using the actual 12 outside words in the current 16-word puzzle. Themes with more outside associations are treated as harder because they create more plausible false leads.

## Word Vectors And Decoys

v4 deliberately adds misleadingness during assembly instead of treating all cross-group similarity as a bug.

`src/generators/similarity_tools.py` uses pretrained GloVe word vectors via `gensim.downloader`:

- backend: `glove-wiki-gigaword-50`
- fallback: lexical token/trigram similarity if embeddings cannot be loaded

These vectors are used to:

- compare a word to its own label and competing labels,
- identify decoy words that also fit another group’s label,
- estimate theme distractibility,
- detect over-ambiguous assignments,
- and reject singleton words that have no meaningful cross-group hook.

During assembly, v4 prefers combinations where every group has at least one word that looks plausible under another group’s label, but it penalizes combinations where too many words fit the wrong label more strongly than the intended one.

## WordNet Specificity

Semantic difficulty relies on the WordNet hypernym/hyponym “is-a” hierarchy:

- shallow nodes are more general,
- deeper nodes are more specific,
- and more specific labels are treated as harder.

This is why v4 uses `min_depth()` from the label’s noun synsets: it is a compact proxy for concept professionalism/specificity.

If WordNet is unavailable, the code degrades gracefully, but for best results install the corpus data with:

```bash
python -m nltk.downloader wordnet omw-1.4
```

## Pronouncing / CMU Dictionary Rhyme Logic

v4 uses the `pronouncing` library, which wraps the CMU Pronouncing Dictionary, so rhyme groups are based on phoneme endings rather than spelling.

That means differently spelled words with the same sound can still be grouped together.

Example:

```python
import pronouncing

for word in ["ell", "el"]:
    phones = pronouncing.phones_for_word(word)
    print(word, phones, pronouncing.rhyming_part(phones[0]))
```

In v4, rhyme generation works like this:

- look up pronunciations with `pronouncing.phones_for_word(...)`,
- derive the rhyme ending with `pronouncing.rhyming_part(...)`,
- bucket candidate words by that phoneme suffix,
- require the visible rhyme target in the label to be absent from the actual group,
- and lower the sampling weight of high-frequency rhyme endings.

The assembler also forbids two rhyme groups with the same phoneme ending from appearing in one puzzle.

v4 also adds a visual rhyme-tail safeguard on top of the CMU-based rhyme logic. Phoneme-level validation correctly separates words that look similar but do not actually rhyme, such as `HAD` and `WAD`, but those words can still create low-quality overlap because they share a strong visible tail like `-AD`. To reduce that ambiguity, the pipeline checks whether outside words visually match the target-centered spelling tail of a rhyme family, and rejects the candidate puzzle if the overlap is too strong.

## Puzzle Assembly

`src/generators/puzzle_assembler.py` now exposes:

- `generate_candidate_puzzle_v4(...)`
- `generate_candidate_puzzles_v4(...)`

Assembly is seeded and deterministic with respect to sampling order.

Each candidate puzzle must satisfy all of the following before it is returned:

- exactly 4 groups with no repeated words,
- difficulty-tier coverage across `easy`, `medium`, and `hard`,
- puzzle-average difficulty inside a fixed interval,
- at least one easiest-tier group and one hardest-tier group,
- no repeated rhyme ending across rhyme groups,
- every group must contain at least one decoy word,
- no self-revealing group,
- no word that is more strongly pulled to the wrong label by too large a margin,
- and no singleton word with no plausible cross-group link.

The assembler does not simply pick groups independently. It scores candidate combinations by:

- embedding similarity from words to competing labels,
- pattern-match spillover into other groups,
- cross-word similarity across groups,
- ambiguity risk penalties,
- and a small seeded random component.

That makes the final puzzles more misleading than v3, but still keeps them playable.

## Validation

`src/validators/puzzle_validators.py` still checks structure, duplication, solver uniqueness, and similarity metrics, but v4 adds explicit checks for:

- difficulty-tier coverage and puzzle difficulty range,
- decoy presence for all four groups,
- label-based ambiguity using embedding similarity,
- visual rhyme-tail overlap for non-rhyming but visibly similar outside words,
- singleton-word rejection,
- and updated high-confusion tolerance consistent with the new decoy-aware design.

The validator returns detailed `reason_groups` and metrics such as:

- `puzzle_difficulty`
- `interference_score`
- `decoy_group_count`
- `ambiguous_word_count`
- `singleton_word_count`
- `average_within_group_similarity`
- `average_cross_group_similarity`

## Batch Generation

Default v4 outputs:

- `data/generated/accepted_v4.json`
- `data/generated/generation_report_v4.json`

Example:

```bash
python src/batch_generate_and_score.py --target-accepted 100 --num-candidates 250 --seed 561
```

Useful flags:

- `--seed`
- `--num-candidates`
- `--target-accepted`
- `--within-threshold`
- `--cross-threshold`
- `--max-solutions`
- `--progress-every`
- `--force-refresh-dataset`
- `--accepted-output`
- `--report-output`

The `--seed` argument controls the v4 sampling order, so rerunning with the same seed and the same resource state produces reproducible candidate selection behavior.

## Streamlit App

Launch the app with:

```bash
streamlit run src/app/app.py
```

The app can:

- generate a fresh validated v4 puzzle,
- load a puzzle from `accepted_v4.json`,
- reveal answers with group types,
- and show the stored puzzle-level difficulty summary.

## How To Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Build or refresh the normalized dataset assets:

```bash
python src/data_utils/dataset_loader.py
```

Generate a v4 library:

```bash
python src/batch_generate_and_score.py --target-accepted 100 --num-candidates 250 --seed 561
```

Start Streamlit:

```bash
streamlit run src/app/app.py
```

## v3 vs v4

Main differences from v3:

- v3 mixed banked groups and simple validation; v4 adds typed difficulty scoring, tier balancing, and puzzle-level difficulty control.
- v3 form groups relied mostly on string patterns; v4 adds blacklist-based triviality filtering, pool-wide coverage checks, and CMU/phoneme-based rhyme detection through `pronouncing`.
- v3 treated cross-group similarity mostly as a rejection signal; v4 deliberately constructs decoys with pretrained word vectors, then rejects only the combinations that become unfairly ambiguous.
- v3 had limited rhyme handling and could reuse the same ending across one puzzle; v4 tracks rhyme endings and suppresses repeated endings.
- v3 did not explicitly reject singleton words; v4 validates that every word has some plausible cross-group distraction.
- v3 still exposed v2-oriented naming in several interfaces; v4 standardizes function names, output names, logs, and app/library references around `v4`.

## Files Added Or Modified Under `src/`

Added under `src/`:

- `src/generators/similarity_tools.py`
- `src/generators/puzzle_analysis.py`

Modified under `src/`:

- `src/data_utils/dataset_loader.py`
- `src/generators/anagram_generator.py`
- `src/generators/form_generator.py`
- `src/generators/generator_resources.py`
- `src/generators/puzzle_assembler.py`
- `src/generators/semantic_generator.py`
- `src/generators/theme_generator.py`
- `src/validators/puzzle_validators.py`
- `src/batch_generate_and_score.py`
- `src/app/app.py`

Related non-`src/` resource added:

- `data/raw/form_pattern_blacklist.txt`

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
