# Infinite Connections

## Project Overview

This repository contains the STA561 **Infinite Connections** project: a generator for NYT-style Connections puzzles.

The repository now contains **three complementary workflows**:

- **v4**: a higher-cost, validator-heavy pipeline for carefully filtered single puzzles
- **v5**: a lower-cost, batch-oriented pipeline designed to generate large libraries quickly and support both reviewer and player-facing Streamlit interfaces
- **v6 final**: the submission-ready branch, built on v5's cheap batch generator but with independently authored semantic/theme/form/anagram banks that hard-fail or filter out any overlap with official NYT groups

The v4 pipeline keeps the v3 repository structure, but extends the existing loader, generators, assembler, validator, batch runner, and Streamlit app so puzzles have:

- stronger difficulty calibration,
- deliberate but controlled misleadingness,
- phoneme-level rhyme handling,
- earlier rejection of trivial form groups,
- and unified v4 naming for generation functions and outputs.

The newer v5 branch work keeps those reusable banks and metadata, but pivots toward the competition workflow of generating **10K puzzles**, sampling a subset for TA/instructor review, and exposing a cleaner player-facing app on top of the cheaper generator. The current **v6 final** branch keeps that low-cost workflow, then adds the final submission requirement that all reusable banked groups must be independent from official NYT groups.

## Version Progression (v1-v6 Final)

- **v1**: initial prototype for loading Connections-style groups and proving the 4-group / 16-word schema.
- **v2**: dataset-loading and normalization stage, with reusable category-bank extraction from the official dataset.
- **v3**: stronger generator/assembler baseline built on those banks, plus early puzzle validation and Streamlit integration.
- **v4**: higher-cost quality pipeline with tier balancing, deeper ambiguity checks, rhyme handling, singleton-word checks, and validator-heavy acceptance.
- **v5**: low-cost compatibility-graph batch generator designed for 10K-scale production, plus separate reviewer and player-facing Streamlit interfaces.
- **v6 final**: submission-ready version built on v5, with independently authored semantic/theme/form/anagram banks, hard overlap protection against official NYT groups, and practical low-cost constraints so 10K puzzle generation stays fast.

## v5 Progress Update

Compared with v4, the current `codex-sta561-v5` branch adds four major pieces of progress:

- a **low-cost batch generator** that builds many structurally sound puzzles without relying on repeated heavy generate-and-reject loops,
- a **compatibility-graph-based sampling path** that directly encodes cheap hard constraints such as word overlap, mechanism-family duplication, rhyme-ending reuse, and theme-frame reuse,
- a **batch review dashboard** where instructors can generate 10K puzzles with a visible progress bar, then sample and inspect puzzles by ID,
- and a separate **player-facing game page** that presents one-click puzzle generation, shuffle/submit/deselect interactions, mistake tracking, solved-group colors, and end-of-game sharing.

v4 remains useful as the stricter reference pipeline; v5 focuses on throughput, maintainability, and practical evaluation at scale.

## v6 Final Update

Compared with v5, the current `codex-sta561-v6-final` branch adds the final submission guarantees:

- an **all-bank independence check** that compares independently authored semantic/theme/form/anagram banks against the official NYT banks and fails runtime initialization if any curated overlap is found,
- a **final low-cost batch generator** that still uses compatibility-graph sampling instead of v4-style heavy rejection loops,
- a **default reviewer interface** centered on final-batch generation and audit sampling,
- a cleaned-up **player-facing final page** layered on top of the same cheap final generator,
- and final generated groups that no longer carry `source_puzzle_id` references into output puzzles because the final banked groups are no longer sourced from official NYT entries.

The purpose of v6 final is not to recover every expensive v4 guarantee. Instead, it is to produce a submission-ready version that scales to the competition workflow: generate a large batch quickly, then let instructors review a random subset manually.

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

## v5 Architecture

The v5 pipeline is intentionally different from v4. Instead of repeatedly assembling a candidate, running heavy ambiguity analysis, and rejecting most attempts, v5 moves the expensive work into one-time preprocessing and keeps the per-puzzle sampling path cheap.

Main v5 modules:

1. `src/generators/puzzle_generator_v5.py`
   Loads the semantic/theme/form/anagram banks once, normalizes them into reusable group records, assigns `mechanism_family` and `theme_frame_family`, and builds a lightweight compatibility graph. Puzzle generation then samples four mutually compatible groups directly from that graph.
2. `src/batch_generate_v5.py`
   Batch-generates `generated_v5.json` and `generation_report_v5.json`, with defaults oriented toward the 10K-puzzle audit workflow.
3. `src/app/app.py`
   Established the reviewer-dashboard pattern that the final branch still uses: generate a large batch on demand, show a progress bar during runtime build and puzzle generation, save the resulting JSON files, and let instructors draw or manually select puzzle IDs for review.
4. `src/app/pages/Play_Final.py`
   The final branch's player-facing page inherits the same v5 interaction model: a 4x4 tile board, shuffle/submit/deselect controls, mistake tracking, solved-group reveal order, and a share summary layered on top of the cheap generator.
5. `src/app/final_game_logic.py`
   The final branch's game-state module keeps player-game state, guess evaluation, solved-group ordering, shuffle behavior, and share-string construction separate from the Streamlit presentation layer.

### v5 Hard Constraints

v5 still enforces cheap but important structural constraints during compatibility-graph construction:

- no word overlap between groups,
- no duplicate normalized labels,
- no repeated rhyme ending,
- no repeated form-like `mechanism_family`,
- and no repeated theme `theme_frame_family`.

This means one puzzle will not contain two rhyme groups with the same mechanism role, or two theme groups that both use the same broad frame such as `AT ...` or `WORDS AFTER ...`.

### v5 Outputs

Default v5 outputs:

- `data/generated/generated_v5.json`
- `data/generated/generation_report_v5.json`

Example:

```bash
python src/batch_generate_v5.py --count 10000 --seed 561
```

The report includes lightweight batch statistics such as runtime build time, generation time, throughput, mechanism-family counts, theme-frame counts, and difficulty-tier counts.

## v6 Final Architecture

The final branch keeps the cheap v5 batch-generation strategy, but changes the semantic-source rule and tightens the branch around the actual submission target.

Main v6 final modules:

1. `src/generators/puzzle_generator_v6.py`
   Uses the same low-cost compatibility-graph approach as v5, but swaps in independent semantic/theme/form/anagram inputs for the final branch, blocks curated-bank overlap with official NYT groups, and applies practical diversity caps to keep 10K-scale generation cheap.
2. `src/batch_generate_v6.py`
   Batch-generates `generated_v6_final.json` and `generation_report_v6_final.json`, with defaults aimed at the final submission workflow.
3. `src/app/app.py`
   Acts as the **final batch reviewer dashboard** on this branch. It can generate the final library on demand, show progress during runtime build and puzzle generation, save the resulting JSON files, and let instructors draw or manually select puzzle IDs for review.
4. `src/app/pages/Play_Final.py`
   Provides the separate **player-facing final page** with one-click puzzle generation, shuffle/submit/deselect controls, mistake tracking, solved-group colors, and share text.
5. `src/app/final_game_logic.py`
   Keeps player-game state, guess evaluation, solved-group ordering, shuffle behavior, and share-string construction separate from the Streamlit presentation layer.

### v6 Final Independence Rule

The final branch adds one hard submission rule:

- semantic, theme, form, and anagram base banks must come from independently authored sources,
- those banks are checked against the corresponding official NYT banks by normalized label-plus-word signature and by normalized word-set signature,
- and generation/runtime initialization fails immediately if any curated overlap is found.

For dynamic form-like groups such as runtime-built rhyme or homophone sets, v6 final filters out any group whose normalized label/word signature would directly reuse an official NYT form group.

This makes official-bank independence a hard invariant rather than a soft filtering preference.

### v6 Final Speed-Oriented Limits

v6 final still avoids the high-cost parts of v4, but it also adds a few cheap guardrails so the final 10K batch remains fast:

- a tighter candidate-order cap during clique expansion,
- a smaller global attempt multiplier for large batches,
- a smaller duplicate-skip budget so the generator does not waste time chasing global uniqueness,
- and simple per-puzzle type caps such as limiting how many semantic, theme, or form-like groups can appear in one puzzle.

These are all low-cost controls that reduce branching without bringing back heavy puzzle-level validation.

### v6 Final Outputs

Default final outputs:

- `data/generated/generated_v6_final.json`
- `data/generated/generation_report_v6_final.json`

Example:

```bash
python src/batch_generate_v6.py --count 10000 --seed 561
```

## Streamlit App

Launch the app with:

```bash
streamlit run src/app/app.py
```

On the `codex-sta561-v6-final` branch, the default Streamlit entrypoint is now the **final batch reviewer dashboard**. It can:

- generate a large final library directly from the app,
- show progress during runtime build and batch generation,
- save `generated_v6_final.json` and `generation_report_v6_final.json`,
- sample puzzles by ID for manual review,
- and display the full answer set plus cheap metadata for each sampled puzzle.

This branch also includes a separate **Play Final** page under Streamlit's multipage navigation. The player page can:

- generate a fresh playable final puzzle,
- show a 4x4 clickable tile grid,
- support `Shuffle`, `Submit`, and `Deselect All`,
- track `Mistakes Remaining`,
- reveal solved groups in yellow/green/blue/purple order,
- and show a simple share string after the game ends.

The underlying v4 and v5 generation modules are still present in the repository for comparison and history, but the default app flow on this branch is centered on final generation/review/play rather than the older v4 live-generator page.

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

Generate a v5 library:

```bash
python src/batch_generate_v5.py --count 10000 --seed 561
```

Generate the final submission library:

```bash
python src/batch_generate_v6.py --count 10000 --seed 561
```

Start Streamlit:

```bash
streamlit run src/app/app.py
```

After Streamlit starts on the final branch:

- the main page is the **final batch reviewer**,
- and the sidebar/page navigation exposes **Play Final** as the player-facing interface.

## v5 vs v6 Final

Main differences from v5:

- v5 focuses on cheap large-scale generation from reused banks; v6 final keeps that batch strategy but changes the source policy so semantic/theme/form/anagram base banks must come from independently authored inputs.
- v5 treats official banks as reusable inputs; v6 final hard-fails if its independently authored banks overlap with the official NYT banks, and it filters out dynamic form-like groups that would still recreate an official form group.
- v5 already removed v4's heaviest per-puzzle validation from the main loop; v6 final keeps that cheap path and adds a few practical diversity caps so 10K-scale generation stays reliable on modest compute.
- v5 introduced reviewer/player interfaces; v6 final keeps both interfaces but makes them the default submission-ready surfaces for the branch.

## v4 vs v5

Main differences from v4:

- v4 is optimized for carefully filtered single-puzzle acceptance; v5 is optimized for generating large libraries quickly.
- v4 keeps heavy validator-driven checks such as backtracking-based uniqueness and richer ambiguity/confusion analysis in the main path; v5 removes those expensive steps from its primary batch-generation loop.
- v4 assembles candidates and rejects many of them; v5 preprocesses group metadata once, builds a compatibility graph, and samples directly from compatible group neighborhoods.
- v4's default app on earlier branches focused on live generation of one puzzle at a time; v5's default app now focuses on batch generation plus manual review, with a separate player-facing page layered on top.
- v4 is better for demonstrating the stricter puzzle-quality pipeline; v5 is better for the competition workflow of generating 10K puzzles and auditing a random subset.

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

Additional v5 files added under `src/`:

- `src/generators/puzzle_generator_v5.py`
- `src/batch_generate_v5.py`

Additional v5 files modified under `src/`:

- `src/app/app.py`

Additional v6 final files added under `src/`:

- `src/generators/puzzle_generator_v6.py`
- `src/batch_generate_v6.py`
- `src/app/final_game_logic.py`
- `src/app/pages/Play_Final.py`

Additional v6 final files modified under `src/`:

- `src/generators/generator_resources.py`
- `src/generators/semantic_generator.py`
- `src/app/app.py`

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
