# Steam Reviews Collection and Metrics Toolkit

A reproducible Python toolkit for collecting Steam user reviews and preparing datasets and metrics for **multiple games**, one title at a time.

## Author

**Rubén Alcaraz Martínez**

## Licence

This project is distributed under the terms of the **GNU General Public License v3.0 (GPL-3.0)**.

## Overview

This repository is designed as a research-oriented and publication-ready toolkit for working with Steam user reviews across multiple games.

Its purpose is to provide a reusable workflow for:

- collecting reviews from the Steam Store Reviews endpoint;
- storing raw review data in a consistent directory structure;
- documenting datasets and methods;
- preparing the data for later analysis;
- extracting descriptive, lexical, temporal, thematic, emotional, and interaction-based metrics;
- generating figure workbooks in Excel format;
- generating word clouds from unigrams, bigrams, and trigrams;
- validating the structural integrity and consistency of outputs;
- orchestrating the full workflow through a single pipeline runner;
- and supporting reproducible publication of both scripts and derived outputs.

The repository is intentionally **game-agnostic**. It is not centred on any single title. Instead, each game can be processed individually within the same shared framework.

## Main design principles

This repository follows five principles:

1. **One workflow, multiple games**  
   The same scripts and directory conventions should work for different Steam games.

2. **One game at a time**  
   Each collection or analysis run should target a single game, but the repository should support as many games as needed.

3. **Clear separation of stages**  
   Data collection, preparation, analysis, validation, and visualisation are kept in separate scripts and directories.

4. **Transparent outputs**  
   Raw data, processed data, metrics, logs, validation summaries, manifests, and documentation are stored in predictable locations.

5. **Reproducibility**  
   Parameters, outputs, validation results, and methodological decisions should be easy to inspect and replicate.

## Data source

The raw data are collected from the Steam Store Reviews endpoint:

`GET store.steampowered.com/appreviews/<appid>?json=1`

The endpoint supports cursor-based pagination and returns review records together with metadata on the review, the reviewer, and selected platform-specific attributes.

## Repository structure

```text
steam-reviews-collection-and-metrics-toolkit/
│
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
│
├── config/
│   └── games/
│       ├── example_game.json
│       └── ...
│
├── resources/
│   ├── lexicons/
│   │   └── nrc/
│   │       └── NRC-Emotion-Lexicon-Wordlevel-v0.92.txt
│   └── dictionaries/
│       └── themes/
│           └── general_game_themes.json
│
├── data/
│   ├── raw/
│   │   └── steam_reviews/
│   │       └── <game_slug>/
│   │           ├── chunks/
│   │           ├── combined/
│   │           ├── metadata/
│   │           └── logs/
│   │
│   └── processed/
│       └── steam_reviews/
│           └── <game_slug>/
│               ├── cleaned/
│               ├── enriched/
│               └── metrics/
│
├── docs/
│   ├── data_dictionary.md
│   ├── methodology.md
│   └── repository_workflow.md
│
├── scripts/
│   ├── run_pipeline.py
│   ├── validate_outputs.py
│   │
│   ├── 01_data_collection/
│   │   └── collect_steam_reviews.py
│   │
│   ├── 02_data_preparation/
│   │   └── prepare_reviews.py
│   │
│   ├── 03_analysis/
│   │   ├── compute_basic_metrics.py
│   │   ├── compute_temporal_metrics.py
│   │   ├── compute_text_metrics.py
│   │   ├── compute_emotion_metrics.py
│   │   └── compute_theme_metrics.py
│   │
│   └── 04_visualisation/
│       ├── create_excel_figures.py
│       └── create_word_clouds.py
│
└── results/
    └── <game_slug>/
        ├── tables/
        └── figures/
```

## Game-based workflow

Each game should be handled through its own configuration and output directories.

A typical workflow is:

1. define a game configuration file;
2. collect raw reviews for that game;
3. prepare and clean the exported files;
4. compute descriptive, temporal, textual, emotional, and thematic metrics;
5. generate figure workbooks in Excel format;
6. generate word clouds from the cleaned textual corpus;
7. validate the outputs;
8. optionally execute all these steps through the pipeline runner;
9. store tables and figures under that game’s result directory.

## Suggested game configuration

Each game should have its own configuration file in:

`config/games/`

Example:

```json
{
  "app_id": 123456,
  "game_slug": "example_game",
  "game_title": "Example Game",
  "language": "all",
  "filter": "updated",
  "review_type": "all",
  "purchase_type": "all",
  "num_per_page": 100,
  "filter_offtopic_activity": 0,
  "chunk_size": 1000,
  "sleep_seconds": 1.2,
  "request_timeout": 60,
  "max_consecutive_errors": 5,
  "user_agent": "Mozilla/5.0 (compatible; AcademicResearchBot/1.0; +research use)",
  "text_metrics": {
    "min_reviews_per_language": 100,
    "min_share_per_language": 1.0,
    "top_n_unigrams": 200,
    "top_n_bigrams": 100,
    "top_n_trigrams": 50,
    "min_token_length": 2,
    "remove_stopwords": true,
    "use_lemmatisation": false,
    "export_per_language": true
  },
  "emotion_metrics": {
    "lexicon_path": "resources/lexicons/nrc/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt",
    "target_language": "english",
    "min_token_length": 2,
    "remove_stopwords": true,
    "export_review_level_enriched_csv": true,
    "top_n_emotion_terms": 100
  },
  "theme_metrics": {
    "dictionary_path": "resources/dictionaries/themes/general_game_themes.json",
    "target_language": "english",
    "min_token_length": 2,
    "remove_stopwords": true,
    "export_review_level_enriched_csv": true,
    "count_multiple_hits_per_theme": true
  },
  "word_cloud": {
    "target_language": "english",
    "min_token_length": 2,
    "remove_stopwords": true,
    "max_words_unigrams": 200,
    "max_words_bigrams": 150,
    "max_words_trigrams": 100,
    "min_frequency_unigrams": 2,
    "min_frequency_bigrams": 2,
    "min_frequency_trigrams": 2,
    "width": 1800,
    "height": 1200,
    "background_colour": "white",
    "collocations": false
  }
}
```

## Theme dictionary structure

The current thematic workflow uses a JSON dictionary organised as:

```json
{
  "theme_name": ["term_1", "term_2", "term_3"]
}
```

Example:

```json
{
  "difficulty": ["hard", "challenging", "punishing"],
  "combat": ["combat", "fight", "battle"],
  "story": ["story", "plot", "narrative"]
}
```

This JSON can be **expanded at any time** by adding new themes or new terms to existing themes, as long as the same structure is respected:

- one key per theme
- one list of terms or expressions per theme
- valid JSON syntax throughout

This makes the theme-analysis stage extensible without modifying the Python script itself.

## Features

- Python-based workflow
- Reusable structure for multiple Steam games
- Cursor-based pagination
- Full multilingual retrieval with `language=all`
- Chunked CSV and JSON export
- Combined CSV and JSON export
- Review preparation and derivation of analytical variables
- Basic descriptive metrics and cross-tabulations
- Temporal metrics and timeline-based tables
- Text metrics with hybrid output: global + by language
- Emotion metrics based on the NRC Emotion Lexicon
- Theme metrics based on a configurable JSON dictionary
- Figure generation as one Excel workbook per figure
- Word-cloud generation for unigrams, bigrams, and trigrams
- Output validation through a dedicated validation script
- Pipeline execution through a single orchestration script
- Output manifest generation for traceability
- Progress tracking and run logging
- Separate directories for raw data, processed data, metrics, and results
- Documentation-oriented structure suitable for GitHub publication

## Requirements

- Python 3.10 or later
- `pip`
- Internet access for API requests

Dependencies are listed in `requirements.txt`.

## Installation

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd steam-reviews-collection-and-metrics-toolkit
```

### 2. Create and activate a virtual environment

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

This step is required for all stages, including:

- data collection
- preparation
- metrics computation
- Excel figure generation
- word-cloud generation
- validation
- full pipeline orchestration

In particular:

- `create_excel_figures.py` depends on **openpyxl**
- `create_word_clouds.py` depends on **wordcloud**
- `validate_outputs.py` uses **openpyxl** again when checking workbook sheet names

All dependencies must be available in the active virtual environment.

## Usage model

The intended usage model is:

1. create or edit a game configuration file;
2. run the collection script for that specific game;
3. generate raw exports;
4. run the preparation script for the same game slug;
5. run the analysis scripts on the prepared dataset;
6. run the visualisation scripts to generate Excel workbooks and word clouds;
7. run validation;
8. or run the complete workflow through the pipeline script;
9. save outputs in the corresponding processed-data and results folders.

## Stage-by-stage execution

### Collection stage

```bash
python scripts/01_data_collection/collect_steam_reviews.py --config config/games/example_game.json
```

Optional flags:

```bash
python scripts/01_data_collection/collect_steam_reviews.py --config config/games/example_game.json --resume
python scripts/01_data_collection/collect_steam_reviews.py --config config/games/example_game.json --no-combined-json
```

### Preparation stage

```bash
python scripts/02_data_preparation/prepare_reviews.py --config config/games/example_game.json
```

Optional flag:

```bash
python scripts/02_data_preparation/prepare_reviews.py --config config/games/example_game.json --no-cleaned-json
```

### Basic metrics stage

```bash
python scripts/03_analysis/compute_basic_metrics.py --config config/games/example_game.json
```

### Temporal metrics stage

```bash
python scripts/03_analysis/compute_temporal_metrics.py --config config/games/example_game.json
```

### Text metrics stage

```bash
python scripts/03_analysis/compute_text_metrics.py --config config/games/example_game.json
```

### Emotion metrics stage

```bash
python scripts/03_analysis/compute_emotion_metrics.py --config config/games/example_game.json
```

### Theme metrics stage

```bash
python scripts/03_analysis/compute_theme_metrics.py --config config/games/example_game.json
```

### Figure generation stage

```bash
python scripts/04_visualisation/create_excel_figures.py --config config/games/example_game.json
```

The figure-generation script reads previously generated CSV tables, transforms each selected source table into chart-ready data, and creates **one Excel workbook per figure**.

### Word-cloud generation stage

```bash
python scripts/04_visualisation/create_word_clouds.py --config config/games/example_game.json
```

The word-cloud generation script reads the cleaned review dataset, tokenises the review text, optionally filters by language, builds unigram, bigram, and trigram frequency tables, and generates three PNG word clouds together with the exact frequency tables used to produce them.

### Validation stage

```bash
python scripts/validate_outputs.py --config config/games/example_game.json
```

The validation script checks:

- presence of key outputs across raw, processed, tables, and figures;
- required columns in selected CSV files;
- selected consistency rules between outputs;
- presence of `data`, `chart`, and `metadata` worksheets in generated Excel figure workbooks;
- presence and structure of the word-cloud output files.

Validation writes:

- `<game_slug>_validation.log`
- `<game_slug>_validation_summary.json`

under:

`data/processed/steam_reviews/<game_slug>/metrics/`

## Full pipeline execution

### Run the complete workflow

```bash
python scripts/run_pipeline.py --config config/games/example_game.json
```

This runs, in order:

1. collection
2. preparation
3. basic metrics
4. temporal metrics
5. text metrics
6. emotion metrics
7. theme metrics
8. Excel figure generation
9. word-cloud generation
10. validation

### Run the pipeline but skip collection

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --skip-collection
```

This is useful when the raw dataset has already been collected and you only want to regenerate downstream outputs.

### Run the pipeline but skip selected downstream stages

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --skip-figures --skip-wordcloud
```

### Run the pipeline but skip validation

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --skip-validation
```

### Continue even if one stage fails

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --continue-on-error
```

This can be useful for diagnostic runs, although the default behaviour is to stop when a stage fails.

### Available skip flags

The pipeline currently supports the following skip options:

- `--skip-collection`
- `--skip-preparation`
- `--skip-basic`
- `--skip-temporal`
- `--skip-text`
- `--skip-emotion`
- `--skip-theme`
- `--skip-figures`
- `--skip-wordcloud`
- `--skip-validation`

These allow the workflow to be rerun selectively without regenerating all outputs.

## Pipeline outputs

For each `game_slug`, the pipeline runner creates:

### Metrics files

Stored in:

`data/processed/steam_reviews/<game_slug>/metrics/`

Files:

- `<game_slug>_pipeline.log`
- `<game_slug>_pipeline_summary.json`
- `<game_slug>_output_manifest.json`

### Pipeline summary

`<game_slug>_pipeline_summary.json` includes, at minimum:

- repository and game identifiers
- the configuration path
- the pipeline log path
- the output manifest path
- total number of stages
- counts of executed, successful, failed, and skipped stages
- final pipeline status

### Output manifest

`<game_slug>_output_manifest.json` provides a structured inventory of outputs and typically includes:

- repository and game identifiers
- root paths for raw, processed, and result directories
- stage results
- important output files and their existence status
- file listings for:
  - raw combined outputs
  - raw chunks
  - raw metadata
  - raw logs
  - processed cleaned outputs
  - processed enriched outputs
  - processed metrics outputs
  - result tables
  - result figures

This manifest is intended as a traceability and audit artefact rather than as a metrics table.

## Figure outputs

For each `game_slug`, the figure-generation stage creates:

### Excel figure workbooks

Stored in:

`results/<game_slug>/figures/`

Subfolders:

- `basic_metrics/`
- `temporal_metrics/`
- `text_metrics/`
- `emotion_metrics/`
- `theme_metrics/`

Typical files include:

- `figure_01_polarity_distribution.xlsx`
- `figure_02_language_distribution_top10.xlsx`
- `figure_03_polarity_by_playtime_band.xlsx`
- `figure_04_monthly_review_volume.xlsx`
- `figure_05_monthly_polarity_trends.xlsx`
- `figure_06_monthly_positive_percentage.xlsx`
- `figure_07_monthly_language_trends_top5.xlsx`
- `figure_08_developer_response_timeline.xlsx`
- `figure_09_top_unigrams_positive.xlsx`
- `figure_10_top_unigrams_negative.xlsx`
- `figure_11_distinctive_terms_positive_vs_negative.xlsx`
- `figure_12_distinctive_terms_negative_vs_positive.xlsx`
- `figure_13_emotion_distribution_summary.xlsx`
- `figure_14_emotion_by_polarity.xlsx`
- `figure_15_emotion_by_month_selected.xlsx`
- `figure_16_theme_distribution_summary.xlsx`
- `figure_17_theme_by_polarity.xlsx`
- `figure_18_theme_by_month_selected.xlsx`

### Figure index

Stored in:

`results/<game_slug>/figures/`

File:

- `<game_slug>_figure_index.csv`

### Processed metrics files

Stored in:

`data/processed/steam_reviews/<game_slug>/metrics/`

Files:

- `<game_slug>_figures_summary.json`
- `<game_slug>_figures.log`

### Internal structure of each Excel figure workbook

Each figure workbook contains exactly three worksheets:

- `data`: the transformed data table used to build the figure
- `chart`: the Excel chart itself
- `metadata`: figure metadata such as figure ID, source table, chart type, output file, and notes

This structure ensures that every figure remains traceable and editable.

## Word-cloud outputs

For each `game_slug`, the word-cloud generation stage creates:

### Word-cloud images

Stored in:

`results/<game_slug>/figures/word_cloud/`

Files:

- `<game_slug>_wordcloud_unigrams.png`
- `<game_slug>_wordcloud_bigrams.png`
- `<game_slug>_wordcloud_trigrams.png`

### Frequency tables used to build the clouds

Stored in the same directory:

- `<game_slug>_wordcloud_unigrams_frequencies.csv`
- `<game_slug>_wordcloud_bigrams_frequencies.csv`
- `<game_slug>_wordcloud_trigrams_frequencies.csv`

### Processed metrics files

Stored in:

`data/processed/steam_reviews/<game_slug>/metrics/`

Files:

- `<game_slug>_word_cloud_summary.json`
- `<game_slug>_word_cloud.log`

## Definition of columns in results tables and output-control files

A full table-by-table definition of the columns exported in:

- `results/<game_slug>/tables/basic_metrics/`
- `results/<game_slug>/tables/temporal_metrics/`
- `results/<game_slug>/tables/text_metrics/`
- `results/<game_slug>/tables/emotion_metrics/`
- `results/<game_slug>/tables/theme_metrics/`
- `results/<game_slug>/figures/`
- `results/<game_slug>/figures/<game_slug>_figure_index.csv`
- `results/<game_slug>/figures/word_cloud/`
- `data/processed/steam_reviews/<game_slug>/metrics/<game_slug>_validation_summary.json`
- `data/processed/steam_reviews/<game_slug>/metrics/<game_slug>_pipeline_summary.json`
- `data/processed/steam_reviews/<game_slug>/metrics/<game_slug>_output_manifest.json`

is documented in `docs/methodology.md`.

## Important limitations

### Text analysis

The current text-analysis workflow uses regex tokenisation and simple stopword lists. As a result, textual outputs are most robust for languages that are whitespace-delimited and explicitly supported by the stopword lists. For languages such as Chinese, Japanese, and Korean, the resulting token, type-token ratio, and n-gram tables should be interpreted with particular caution unless language-specific segmentation is added in a later version.

### Emotion analysis

The current emotion-analysis workflow applies the NRC Emotion Lexicon through direct lexical matching. It is therefore most appropriate for the language covered by the lexicon in use and should be interpreted as a lexicon-based approximation. It does not robustly resolve irony, negation, sarcasm, idiomatic usage, or polysemy.

### Theme analysis

The current theme-analysis workflow applies a configurable dictionary through direct lexical and expression matching. It is therefore transparent and extensible, but it should be interpreted as a rule-based approximation of thematic presence. It does not automatically resolve irony, negation, broader semantic context, or implicit thematic references that are not represented in the dictionary.

### Figure generation

The current figure-generation workflow does not calculate new substantive metrics. It only reuses and transforms previously generated tables into chart-ready Excel workbooks. Any interpretive limitation of the source tables also applies to the derived figures.

### Word clouds

The current word-cloud workflow is frequency-based and inherits the same tokenisation and stopword-filtering constraints as the text-preparation stage. The resulting visual prominence of a term depends on the selected frequency thresholds, tokenisation, and optional language filter, not on semantic importance in any deeper sense.

### Validation

The current validation stage checks structural expectations and selected consistency rules, but it does not replace substantive interpretation or manual inspection of the outputs.

### Pipeline orchestration

The pipeline runner does not change the analytical logic of the underlying scripts. It only automates execution order, captures stage status, and summarises generated outputs.

## Output philosophy

The repository should always preserve:

- **raw outputs** exactly as collected and normalised from Steam;
- **processed outputs** used for downstream analysis;
- **metrics outputs** derived from the processed data;
- **visual outputs** derived from those metrics and from cleaned textual frequencies;
- **validation outputs** that document structural checks and consistency checks;
- **pipeline-control outputs** that document execution and inventory;
- **logs and metadata** documenting each run.

## Metrics and control artefacts generated at analysis, validation, and visualisation stage

The scripts may generate, among others:

- dataset overview metrics
- polarity summaries
- language distributions
- reviewer profile summaries
- playtime summaries
- interaction summaries
- text-length summaries
- temporal interval summaries
- purchase and access summaries
- missingness summaries
- concentration summaries
- polarity cross-tabulations
- review volume timelines
- language timelines
- playtime timelines
- reviewer-profile timelines
- interaction timelines
- review-update timelines
- developer-response timelines
- peak-activity summaries
- token frequencies
- n-gram frequencies
- distinctive-term tables
- textual comparisons by polarity
- textual comparisons by language
- review-level emotion enrichment
- emotion distributions
- emotion summaries by polarity
- emotion summaries by playtime band
- emotion summaries by month
- top lexical items by emotion
- review-level theme enrichment
- theme distributions
- theme summaries by polarity
- theme summaries by playtime band
- theme summaries by month
- top lexical items by theme
- Excel figure workbooks built from selected result tables
- unigram, bigram, and trigram word clouds built from cleaned review text
- validation summaries
- pipeline summaries
- output manifests

See `docs/data_dictionary.md` for the raw field definitions and `docs/methodology.md` for the full workflow and exhaustive definition of result-table columns, figure-workbook structure, validation outputs, pipeline outputs, and word-cloud outputs.
