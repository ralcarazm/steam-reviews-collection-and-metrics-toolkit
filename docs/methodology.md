# Methodology

## Overview

This document describes the general workflow used in this repository to build, prepare, analyse, validate, and orchestrate Steam review datasets for **multiple games**, one game at a time. The workflow is designed for reuse, reproducibility, and transparent publication of scripts, intermediate files, derived outputs, editable figure workbooks, word-cloud visualisations, validation artefacts, and pipeline manifests.

## Data source

The datasets are collected from the Steam Store Reviews endpoint:

`GET store.steampowered.com/appreviews/<appid>?json=1`

The endpoint returns review data in JSON format together with metadata about the review, the reviewer, and selected platform-related variables.

Each collection run targets **one game**, identified at minimum by:

- `app_id`
- `game_slug`
- `game_title`

## Configuration-driven workflow

The repository follows a configuration-driven approach. Each game should have its own JSON configuration file, typically stored in `config/games/`. In addition to collection parameters, the configuration may contain optional blocks such as `text_metrics`, `emotion_metrics`, `theme_metrics`, and `word_cloud` controlling thresholds, filtering, lexicon or dictionary paths, and export behaviour for later stages.

## Software environment

The repository is intended to be executed in a dedicated Python virtual environment in order to ensure dependency isolation and reproducibility.

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Dependencies for visual and validation outputs

The figure-generation stage depends on `openpyxl`.

The word-cloud stage depends on `wordcloud`.

The validation stage uses `openpyxl` again when checking generated Excel workbooks.

All dependencies must be installed in the active virtual environment and should be listed in `requirements.txt`.

## Stage 1: data collection

The collection script retrieves reviews through cursor-based pagination. The process starts with `cursor="*"` and continues until the endpoint stops returning review records.

Default parameters typically include:

- `json=1`
- `language=all`
- `filter=updated`
- `review_type=all`
- `purchase_type=all`
- `num_per_page=100`
- `filter_offtopic_activity=0`

The workflow deduplicates reviews using `recommendationid`.

The collection script also creates the downstream directory structure needed by later stages, including:

- `data/raw/steam_reviews/<game_slug>/...`
- `data/processed/steam_reviews/<game_slug>/...`
- `results/<game_slug>/tables/`
- `results/<game_slug>/figures/`

The workflow does **not** create a `results/<game_slug>/reports/` directory.

## Stage 2: data preparation

The preparation stage reads:

`data/raw/steam_reviews/<game_slug>/combined/<game_slug>_reviews_all.csv`

and exports a cleaned dataset after normalising types, timestamps, text fields, and derived indicators.

## Stage 3: basic descriptive analysis

The basic analysis stage reads:

`data/processed/steam_reviews/<game_slug>/cleaned/<game_slug>_reviews_cleaned.csv`

and exports descriptive tables under `results/<game_slug>/tables/basic_metrics/` together with a JSON summary and analysis log.

## Exhaustive definition of columns in basic metrics result tables

### `dataset_overview.csv`
- `metric`
- `value`

### `polarity_summary.csv`
- `metric`
- `value`

### `language_distribution.csv`
- `language`
- `review_count`
- `review_percentage`

### `reviewer_profile_summary.csv`
- `variable`
- `count_non_null`
- `count_null`
- `count_zero`
- `mean`
- `median`
- `std`
- `min`
- `p10`
- `p25`
- `p50`
- `p75`
- `p90`
- `p95`
- `max`
- `sum`

### `playtime_summary.csv`
Same column structure as `reviewer_profile_summary.csv`, with playtime variables expressed in minutes.

### `interaction_summary.csv`
Same column structure as `reviewer_profile_summary.csv`.

### `text_summary.csv`
Same column structure as `reviewer_profile_summary.csv`.

### `temporal_interval_summary.csv`
Same column structure as `reviewer_profile_summary.csv`, with interval variables expressed in days.

### `purchase_and_access_summary.csv`
- `metric`
- `count_true`
- `percentage_true`

### `missingness_summary.csv`
- `column`
- `row_count`
- `non_null_count`
- `null_count`
- `null_percentage`

### `concentration_summary.csv`
- `variable`
- `sum_total`
- `share_top_1_percent`
- `share_top_5_percent`
- `share_top_10_percent`

### `cross_tab_polarity_by_language.csv`
- `language`
- `False`
- `True`
- `False_percentage_of_total`
- `True_percentage_of_total`

### `cross_tab_polarity_by_playtime_band.csv`
- `playtime_at_review_band`
- `False`
- `True`
- `False_percentage_of_total`
- `True_percentage_of_total`

### `cross_tab_polarity_by_reviewer_activity_band.csv`
- `num_reviews_band`
- `False`
- `True`
- `False_percentage_of_total`
- `True_percentage_of_total`

### `cross_tab_polarity_by_library_size_band.csv`
- `num_games_owned_band`
- `False`
- `True`
- `False_percentage_of_total`
- `True_percentage_of_total`

### `monthly_review_volume.csv`
- `review_created_year_month`
- `review_count`
- `positive_reviews`
- `negative_reviews`
- `positive_percentage`
- `negative_percentage`

## Stage 4: temporal descriptive analysis

The temporal analysis stage also reads the cleaned CSV and exports timeline-based tables under `results/<game_slug>/tables/temporal_metrics/`.

## Exhaustive definition of columns in temporal metrics result tables

### `temporal_coverage.csv`
- `metric`
- `value`

### `daily_review_volume.csv`
- `review_created_date_day`
- `review_count`
- `positive_reviews`
- `negative_reviews`
- `positive_percentage`
- `negative_percentage`
- `cumulative_reviews`
- `review_count_change_vs_previous_day`
- `positive_percentage_change_vs_previous_day`

### `weekly_review_volume.csv`
- `review_created_date_week`
- `review_count`
- `positive_reviews`
- `negative_reviews`
- `positive_percentage`
- `negative_percentage`
- `cumulative_reviews`
- `review_count_change_vs_previous_week`
- `positive_percentage_change_vs_previous_week`

### `monthly_review_volume_extended.csv`
- `review_created_date_month`
- `review_count`
- `positive_reviews`
- `negative_reviews`
- `unique_reviewers`
- `positive_percentage`
- `negative_percentage`
- `cumulative_reviews`
- `review_count_change_vs_previous_month`
- `positive_percentage_change_vs_previous_month`
- `review_count_rolling_mean_3m`
- `positive_percentage_rolling_mean_3m`

### `monthly_polarity_trends.csv`
- `review_created_date_month`
- `review_count`
- `positive_reviews`
- `negative_reviews`
- `positive_percentage`
- `negative_percentage`
- `positive_negative_ratio`
- `positive_percentage_change_vs_previous_month`

### `monthly_language_trends.csv`
- `review_created_date_month`
- `language`
- `review_count`
- `positive_reviews`
- `month_total_reviews`
- `review_percentage_within_month`
- `positive_percentage_within_language_month`

### `monthly_text_length_trends.csv`
Base columns:
- `review_created_date_month`
- `review_length_words_count_non_null`
- `review_length_words_mean`
- `review_length_words_median`
- `review_length_words_std`
- `review_length_words_min`
- `review_length_words_p25`
- `review_length_words_p75`
- `review_length_words_p90`
- `review_length_words_max`
- `review_length_chars_count_non_null`
- `review_length_chars_mean`
- `review_length_chars_median`
- `review_length_chars_std`
- `review_length_chars_min`
- `review_length_chars_p25`
- `review_length_chars_p75`
- `review_length_chars_p90`
- `review_length_chars_max`
- `review_length_lines_count_non_null`
- `review_length_lines_mean`
- `review_length_lines_median`
- `review_length_lines_std`
- `review_length_lines_min`
- `review_length_lines_p25`
- `review_length_lines_p75`
- `review_length_lines_p90`
- `review_length_lines_max`

Additional columns beginning `review_length_words_band_` represent the monthly percentage in each review-length band.

### `monthly_playtime_trends.csv`
May include:
- `review_created_date_month`
- `playtime_at_review_count_non_null`
- `playtime_at_review_mean`
- `playtime_at_review_median`
- `playtime_at_review_std`
- `playtime_at_review_min`
- `playtime_at_review_p25`
- `playtime_at_review_p75`
- `playtime_at_review_p90`
- `playtime_at_review_max`
- `playtime_forever_count_non_null`
- `playtime_forever_mean`
- `playtime_forever_median`
- `playtime_forever_std`
- `playtime_forever_min`
- `playtime_forever_p25`
- `playtime_forever_p75`
- `playtime_forever_p90`
- `playtime_forever_max`
- `playtime_post_review_count_non_null`
- `playtime_post_review_mean`
- `playtime_post_review_median`
- `playtime_post_review_std`
- `playtime_post_review_min`
- `playtime_post_review_p25`
- `playtime_post_review_p75`
- `playtime_post_review_p90`
- `playtime_post_review_max`
- `played_after_review_review_count`
- `played_after_review_true_count`
- `played_after_review_percentage`
- `recent_playtime_recorded_review_count`
- `recent_playtime_recorded_true_count`
- `recent_playtime_recorded_percentage`
- `used_steam_deck_at_review_review_count`
- `used_steam_deck_at_review_true_count`
- `used_steam_deck_at_review_percentage`

Additional columns beginning `playtime_at_review_band_` contain monthly counts by playtime band.

### `monthly_reviewer_profile_trends.csv`
May include:
- `review_created_date_month`
- `num_reviews_count_non_null`
- `num_reviews_mean`
- `num_reviews_median`
- `num_reviews_std`
- `num_reviews_min`
- `num_reviews_p25`
- `num_reviews_p75`
- `num_reviews_p90`
- `num_reviews_max`
- `num_games_owned_count_non_null`
- `num_games_owned_mean`
- `num_games_owned_median`
- `num_games_owned_std`
- `num_games_owned_min`
- `num_games_owned_p25`
- `num_games_owned_p75`
- `num_games_owned_p90`
- `num_games_owned_max`

Additional columns beginning `num_reviews_band_` and `num_games_owned_band_` contain monthly counts by reviewer bands.

### `monthly_interaction_trends.csv`
May include:
- `review_created_date_month`
- `votes_up_count_non_null`
- `votes_up_mean`
- `votes_up_median`
- `votes_up_std`
- `votes_up_min`
- `votes_up_p25`
- `votes_up_p75`
- `votes_up_p90`
- `votes_up_max`
- `votes_funny_count_non_null`
- `votes_funny_mean`
- `votes_funny_median`
- `votes_funny_std`
- `votes_funny_min`
- `votes_funny_p25`
- `votes_funny_p75`
- `votes_funny_p90`
- `votes_funny_max`
- `comment_count_count_non_null`
- `comment_count_mean`
- `comment_count_median`
- `comment_count_std`
- `comment_count_min`
- `comment_count_p25`
- `comment_count_p75`
- `comment_count_p90`
- `comment_count_max`
- `has_helpful_votes_review_count`
- `has_helpful_votes_true_count`
- `has_helpful_votes_percentage`
- `has_funny_votes_review_count`
- `has_funny_votes_true_count`
- `has_funny_votes_percentage`
- `has_comments_review_count`
- `has_comments_true_count`
- `has_comments_percentage`

### `review_update_metrics.csv`
- `review_created_year_month`
- `review_count`
- `updated_reviews`
- `mean_days_between_creation_and_update`
- `median_days_between_creation_and_update`
- `updated_reviews_percentage`

### `developer_response_timeline.csv`
- `review_created_date_month`
- `review_count`
- `reviews_with_developer_response`
- `mean_days_to_developer_response`
- `median_days_to_developer_response`
- `developer_response_percentage`
- `developer_responses_created_in_month`
- `negative_reviews`
- `negative_reviews_with_response`
- `negative_response_percentage`
- `positive_reviews`
- `positive_reviews_with_response`
- `positive_response_percentage`

### `monthly_polarity_by_language.csv`
- `review_created_date_month`
- `language`
- `review_count`
- `positive_reviews`
- `negative_reviews`
- `positive_percentage`
- `negative_percentage`

### `monthly_polarity_by_playtime_band.csv`
- `review_created_date_month`
- `playtime_at_review_band`
- `review_count`
- `positive_reviews`
- `negative_reviews`
- `positive_percentage`
- `negative_percentage`

### `peak_activity_summary.csv`
- `metric`
- `value`

## Stage 5: textual descriptive analysis

The text-analysis stage reads the cleaned CSV and first filters to rows with usable text after tokenisation. It then produces:

1. **global textual outputs** for the whole corpus;
2. **comparative textual outputs by language**;
3. **separate by-language outputs** for languages that exceed configured thresholds.

### Text-analysis input

`data/processed/steam_reviews/<game_slug>/cleaned/<game_slug>_reviews_cleaned.csv`

### Text-analysis tasks

The text-analysis stage is intended to:

- restore expected data types from the cleaned CSV;
- retain only rows with usable review text after cleaning and tokenisation;
- tokenise text using regex-based tokenisation;
- optionally remove stopwords using language-specific stopword lists when available;
- build unigram, bigram, and trigram frequency tables;
- compare positive and negative review language;
- compare textual behaviour across playtime bands;
- compare languages globally;
- select languages for separate output using configurable thresholds;
- export global, by-language, and machine-readable summary outputs.

### Language-selection logic

A language is eligible for separate output when it satisfies at least one configured threshold:

- `review_count >= min_reviews_per_language`
- or `review_percentage >= min_share_per_language`

### Important limitation of the current text-analysis stage

The current workflow uses regex tokenisation and simple stopword lists. It is therefore most robust for whitespace-delimited languages explicitly covered by the stopword dictionaries. For Chinese, Japanese, Korean, and other languages requiring segmentation, token counts, type-token ratios, and n-gram tables should be interpreted as approximate outputs of the current implementation rather than as linguistically optimal segmentations.

### Text-analysis outputs

For each `game_slug`, the text-analysis workflow exports:

1. **a text metrics summary JSON file**
2. **a text analysis log file**
3. **global CSV tables under `results/<game_slug>/tables/text_metrics/global/`**
4. **by-language CSV tables under `results/<game_slug>/tables/text_metrics/by_language/<language>/` for selected languages**

## Exhaustive definition of columns in text metrics result tables

### Global text metrics tables

#### `text_corpus_overview.csv`
- `metric`
- `value`

Typical `metric` values may include:
- `scope`
- `app_id`
- `game_slug`
- `game_title`
- `reviews_with_text`
- `positive_review_count`
- `negative_review_count`
- `total_tokens`
- `total_unique_tokens`
- `type_token_ratio`
- `average_review_length_words`
- `median_review_length_words`
- `average_review_length_chars`
- `median_review_length_chars`
- `languages_with_text`
- `selected_languages_for_separate_output`

#### `text_metrics_by_polarity.csv`
- `segment`
- `review_count`
- `total_tokens`
- `unique_tokens`
- `type_token_ratio`
- `mean_review_length_words`
- `median_review_length_words`
- `mean_review_length_chars`
- `median_review_length_chars`

#### `text_metrics_by_playtime_band.csv`
- `playtime_at_review_band`
- `review_count`
- `total_tokens`
- `unique_tokens`
- `type_token_ratio`
- `mean_review_length_words`
- `median_review_length_words`

#### `text_metrics_by_language.csv`
- `language`
- `review_count`
- `review_percentage`
- `total_tokens`
- `unique_tokens`
- `type_token_ratio`
- `mean_review_length_words`
- `median_review_length_words`

#### `top_terms_by_language.csv`
- `language`
- `rank`
- `token`
- `frequency`
- `relative_frequency_per_1000_tokens`

#### `top_unigrams_overall.csv`, `top_unigrams_positive.csv`, `top_unigrams_negative.csv`
- `rank`
- `token`
- `frequency`
- `relative_frequency_per_1000_tokens`

#### `top_bigrams_overall.csv`, `top_bigrams_positive.csv`, `top_bigrams_negative.csv`
- `rank`
- `bigram`
- `frequency`
- `relative_frequency_per_1000_bigrams`

#### `top_trigrams_overall.csv`
- `rank`
- `trigram`
- `frequency`
- `relative_frequency_per_1000_trigrams`

#### `distinctive_terms_positive_vs_negative.csv`
- `token`
- `positive_frequency`
- `negative_frequency`
- `positive_relative_per_1000`
- `negative_relative_per_1000`
- `difference_per_1000`
- `log_ratio`

#### `distinctive_terms_negative_vs_positive.csv`
- `token`
- `negative_frequency`
- `positive_frequency`
- `negative_relative_per_1000`
- `positive_relative_per_1000`
- `difference_per_1000`
- `log_ratio`

### By-language text metrics tables

Each selected language directory may contain the following tables.

#### `text_corpus_overview.csv`
- `metric`
- `value`

#### `text_metrics_by_polarity.csv`
- `segment`
- `review_count`
- `total_tokens`
- `unique_tokens`
- `type_token_ratio`
- `mean_review_length_words`
- `median_review_length_words`
- `mean_review_length_chars`
- `median_review_length_chars`

#### `text_metrics_by_playtime_band.csv`
- `playtime_at_review_band`
- `review_count`
- `total_tokens`
- `unique_tokens`
- `type_token_ratio`
- `mean_review_length_words`
- `median_review_length_words`

#### `top_unigrams_overall.csv`, `top_unigrams_positive.csv`, `top_unigrams_negative.csv`
- `rank`
- `token`
- `frequency`
- `relative_frequency_per_1000_tokens`

#### `top_bigrams_overall.csv`, `top_bigrams_positive.csv`, `top_bigrams_negative.csv`
- `rank`
- `bigram`
- `frequency`
- `relative_frequency_per_1000_bigrams`

#### `distinctive_terms_positive_vs_negative.csv`
- `token`
- `positive_frequency`
- `negative_frequency`
- `positive_relative_per_1000`
- `negative_relative_per_1000`
- `difference_per_1000`
- `log_ratio`

#### `distinctive_terms_negative_vs_positive.csv`
- `token`
- `negative_frequency`
- `positive_frequency`
- `negative_relative_per_1000`
- `positive_relative_per_1000`
- `difference_per_1000`
- `log_ratio`

## Stage 6: emotion descriptive analysis

The emotion-analysis stage reads the cleaned CSV, filters the corpus to a configured target language, tokenises the text, and matches tokens against the NRC Emotion Lexicon.

### External resource

The current implementation expects the NRC lexicon in a repository resource path such as:

`resources/lexicons/nrc/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt`

### Emotion-analysis input

`data/processed/steam_reviews/<game_slug>/cleaned/<game_slug>_reviews_cleaned.csv`

### Emotion-analysis tasks

The emotion-analysis stage is intended to:

- restore expected data types from the cleaned CSV;
- recreate `playtime_at_review_band` if it is not already present in the cleaned CSV;
- filter to the configured `target_language`;
- retain only rows with usable review text after tokenisation;
- tokenise text using regex-based tokenisation;
- optionally remove stopwords;
- match tokens against NRC emotion categories;
- enrich each review with emotion counts and normalised rates;
- export a review-level enriched CSV;
- aggregate the enriched data by corpus, polarity, playtime band, and month;
- extract top lexical items associated with each emotion;
- export both machine-readable and reporting-oriented outputs.

### Emotion-analysis outputs

For each `game_slug`, the emotion-analysis workflow exports:

1. **an emotion metrics summary JSON file**
2. **an emotion analysis log file**
3. **a review-level enriched CSV under `data/processed/steam_reviews/<game_slug>/enriched/`**
4. **CSV tables under `results/<game_slug>/tables/emotion_metrics/`**

### Important limitation of the current emotion-analysis stage

The current workflow is lexicon-based. It therefore reflects direct word-level associations present in the NRC lexicon and should be interpreted as an approximate affective signal rather than as deep semantic understanding. It does not robustly resolve irony, negation, sarcasm, idioms, or polysemy. It is also most appropriate for the language covered by the lexicon being used.

## Exhaustive definition of columns in emotion metrics result tables

### Review-level enriched CSV

The enriched review-level file may include all columns retained from the filtered cleaned dataset plus the following added columns:

- `tokens`
- `token_count_for_emotion_analysis`
- `emotion_token_count`
- `<emotion>_count`
- `<emotion>_per_100_tokens`

Where `<emotion>` may be:
- `positive`
- `joy`
- `anticipation`
- `trust`
- `surprise`
- `negative`
- `fear`
- `sadness`
- `anger`
- `disgust`

### `emotion_corpus_overview.csv`
- `metric`
- `value`

### `emotion_distribution_summary.csv`
- `emotion`
- `total_hits`
- `hits_per_1000_tokens`
- `reviews_with_emotion`
- `review_share_with_emotion`
- `mean_count_per_review`
- `mean_per_100_tokens`

### `emotion_by_polarity.csv`
- `segment`
- `review_count`
- `total_tokens`
- `emotion_token_count`
- `<emotion>_mean_count`
- `<emotion>_mean_per_100_tokens`
- `<emotion>_review_share`

### `emotion_by_playtime_band.csv`
- `playtime_at_review_band`
- `review_count`
- `total_tokens`
- `emotion_token_count`
- `<emotion>_mean_count`
- `<emotion>_mean_per_100_tokens`
- `<emotion>_review_share`

### `emotion_by_month.csv`
- `review_created_year_month`
- `review_count`
- `total_tokens`
- `emotion_token_count`
- `<emotion>_mean_count`
- `<emotion>_mean_per_100_tokens`
- `<emotion>_review_share`

### `emotion_top_terms_by_emotion.csv`
- `emotion`
- `rank`
- `token`
- `frequency`
- `relative_frequency_per_1000_emotion_hits`

## Stage 7: thematic descriptive analysis

The theme-analysis stage reads the cleaned CSV, filters the corpus to a configured target language, tokenises the text, and matches tokens and selected expressions against a configurable JSON theme dictionary.

### External resource

The current implementation expects the theme dictionary in a repository resource path such as:

`resources/dictionaries/themes/general_game_themes.json`

### Theme dictionary structure

The dictionary is expected to use the following structure:

```json
{
  "theme_name": ["term_1", "term_2", "term_3"]
}
```

This dictionary can be expanded at any time by adding:

- new themes as new keys
- new terms to existing theme lists

as long as valid JSON syntax and the same theme-to-list structure are preserved.

### Theme-analysis input

`data/processed/steam_reviews/<game_slug>/cleaned/<game_slug>_reviews_cleaned.csv`

### Theme-analysis tasks

The theme-analysis stage is intended to:

- restore expected data types from the cleaned CSV;
- recreate `playtime_at_review_band` if it is not already present in the cleaned CSV;
- filter to the configured `target_language`;
- retain only rows with usable review text after tokenisation;
- tokenise text using regex-based tokenisation;
- optionally remove stopwords;
- match tokens and selected multiword expressions against the theme dictionary;
- enrich each review with theme counts, presence flags, matched-term summaries, and normalised rates;
- export a review-level enriched CSV;
- aggregate the enriched data by corpus, polarity, playtime band, and month;
- extract top lexical items associated with each theme;
- export both machine-readable and reporting-oriented outputs.

### Theme-analysis outputs

For each `game_slug`, the theme-analysis workflow exports:

1. **a theme metrics summary JSON file**
2. **a theme analysis log file**
3. **a review-level enriched CSV under `data/processed/steam_reviews/<game_slug>/enriched/`**
4. **CSV tables under `results/<game_slug>/tables/theme_metrics/`**

### Important limitation of the current theme-analysis stage

The current workflow is rule-based and dictionary-based. It therefore detects only the themes that are explicitly represented in the configured term lists. It does not automatically infer implicit themes, broader semantic relations, irony, negation, or context not captured by the dictionary.

## Exhaustive definition of columns in theme metrics result tables

### Review-level enriched CSV

The enriched review-level file may include all columns retained from the filtered cleaned dataset plus the following added columns:

- `tokens`: internal token list representation serialised by pandas when exported.
- `token_count_for_theme_analysis`: number of analysed tokens in the review after tokenisation and filtering.
- `theme_match_count_total`: total number of theme matches found in the review across all themes.
- `themes_present_count`: number of distinct themes detected in the review.
- `<theme>_count`: raw count of matched occurrences for a given theme in the review.
- `<theme>_present`: boolean flag indicating whether the theme was detected at least once in the review.
- `<theme>_matched_terms`: semicolon-separated list of matched dictionary terms contributing to that theme in the review.
- `<theme>_per_100_tokens`: normalised frequency of that theme in the review, expressed per 100 analysed tokens.

### `theme_corpus_overview.csv`

- `metric`
- `value`

Typical `metric` values may include:
- `app_id`
- `game_slug`
- `game_title`
- `target_language`
- `rows_in_cleaned_dataset`
- `rows_in_target_language`
- `reviews_with_usable_text`
- `reviews_with_any_theme_match`
- `total_tokens_analysed`
- `total_theme_matches`
- `reviews_with_<theme>_signal`

### `theme_distribution_summary.csv`

- `theme`: theme label from the JSON dictionary.
- `total_hits`: total number of matched occurrences for that theme in the analysed corpus.
- `hits_per_1000_tokens`: normalised frequency of that theme over all analysed tokens, expressed per 1000 tokens.
- `reviews_with_theme`: number of reviews with at least one matched occurrence of that theme.
- `review_share_with_theme`: percentage of analysed reviews containing at least one occurrence of that theme.
- `mean_count_per_review`: arithmetic mean of the raw review-level theme count.
- `mean_per_100_tokens`: arithmetic mean of the review-level normalised theme rate per 100 tokens.

### `theme_by_polarity.csv`

- `segment`: corpus subset label, typically `overall`, `positive`, or `negative`.
- `review_count`: number of reviews in the segment.
- `total_tokens`: total number of analysed tokens in the segment.
- `theme_match_count_total`: total number of matched theme occurrences in the segment.
- `<theme>_mean_count`: arithmetic mean of the raw review-level count for the given theme within the segment.
- `<theme>_mean_per_100_tokens`: arithmetic mean of the normalised review-level rate per 100 tokens for the given theme within the segment.
- `<theme>_review_share`: percentage of reviews in the segment containing at least one occurrence of the given theme.

### `theme_by_playtime_band.csv`

- `playtime_at_review_band`: playtime band derived from `playtime_at_review`.
- `review_count`
- `total_tokens`
- `theme_match_count_total`
- `<theme>_mean_count`
- `<theme>_mean_per_100_tokens`
- `<theme>_review_share`

The playtime bands follow the same banding scheme used elsewhere in the repository.

### `theme_by_month.csv`

- `review_created_year_month`
- `review_count`
- `total_tokens`
- `theme_match_count_total`
- `<theme>_mean_count`
- `<theme>_mean_per_100_tokens`
- `<theme>_review_share`

Each row summarises the analysed target-language reviews created in that month.

### `theme_top_terms_by_theme.csv`

- `theme`: theme label from the dictionary.
- `rank`: descending frequency rank within that theme.
- `term`: matched lexical item or expression associated with that theme.
- `frequency`: raw frequency of that term among matched terms for that theme.
- `relative_frequency_per_1000_theme_hits`: normalised frequency of that term within all hits for that theme, expressed per 1000 theme hits.

## Stage 8: figure generation in Excel workbooks

The figure-generation stage reads previously generated CSV tables and creates one Excel workbook per figure.

### Figure-generation input

The figure-generation stage does **not** use the cleaned CSV directly. Instead, it reads selected result tables from:

- `results/<game_slug>/tables/basic_metrics/`
- `results/<game_slug>/tables/temporal_metrics/`
- `results/<game_slug>/tables/text_metrics/`
- `results/<game_slug>/tables/emotion_metrics/`
- `results/<game_slug>/tables/theme_metrics/`

### Figure-generation tasks

The figure-generation stage is intended to:

- load selected source CSV tables from previously completed analysis stages;
- apply small deterministic transformations to make the tables chart-ready;
- create one Excel workbook per figure;
- write the transformed source table to a `data` worksheet;
- create an Excel chart in a `chart` worksheet;
- write figure metadata to a `metadata` worksheet;
- group figure workbooks by metric family in subdirectories;
- export a figure index CSV;
- export a figures summary JSON file;
- export a figures log.

### Figure-generation outputs

For each `game_slug`, the figure-generation workflow exports:

1. **Excel workbooks under `results/<game_slug>/figures/`**
2. **a figure index CSV under `results/<game_slug>/figures/`**
3. **a figures summary JSON file under `data/processed/steam_reviews/<game_slug>/metrics/`**
4. **a figures log under `data/processed/steam_reviews/<game_slug>/metrics/`**

### Figure workbook structure

Each generated Excel workbook contains exactly three worksheets:

#### `data`
Contains the transformed table actually used to draw the figure. This sheet may be a subset, pivoted version, or simple reshaping of the original source CSV.

#### `chart`
Contains the Excel chart built from the `data` worksheet.

#### `metadata`
Contains figure metadata such as:
- `figure_id`
- `filename`
- `family`
- `title`
- `chart_type`
- `source_table`
- `output_file`
- `transform_name`
- `category_column`
- `value_columns`
- `notes`

### Figure families and output directories

Generated figure workbooks are grouped under:

- `results/<game_slug>/figures/basic_metrics/`
- `results/<game_slug>/figures/temporal_metrics/`
- `results/<game_slug>/figures/text_metrics/`
- `results/<game_slug>/figures/emotion_metrics/`
- `results/<game_slug>/figures/theme_metrics/`

### Figure index CSV

The figure index file is stored as:

`results/<game_slug>/figures/<game_slug>_figure_index.csv`

Columns:

- `figure_id`: unique figure identifier such as `figure_01`.
- `filename`: workbook filename.
- `family`: figure family or block.
- `title`: human-readable figure title.
- `chart_type`: Excel chart type used by the script.
- `source_table`: full source CSV path used by the figure generator.
- `output_file`: full output workbook path.
- `row_count`: number of rows in the transformed `data` sheet.
- `column_count`: number of columns in the transformed `data` sheet.
- `notes`: short description of the figure logic.

### Figures summary JSON

The summary JSON stored in:

`data/processed/steam_reviews/<game_slug>/metrics/<game_slug>_figures_summary.json`

contains, at minimum:

- repository and game identifiers
- generation timestamp
- total number of generated figures
- figure metadata entries corresponding to the figure index

### Figures log

The log stored in:

`data/processed/steam_reviews/<game_slug>/metrics/<game_slug>_figures.log`

records the execution of the figure-generation stage.

### Typical figure workbooks in the current implementation

The current implementation typically generates 18 Excel workbooks:

#### Basic metrics
- `figure_01_polarity_distribution.xlsx`
- `figure_02_language_distribution_top10.xlsx`
- `figure_03_polarity_by_playtime_band.xlsx`

#### Temporal metrics
- `figure_04_monthly_review_volume.xlsx`
- `figure_05_monthly_polarity_trends.xlsx`
- `figure_06_monthly_positive_percentage.xlsx`
- `figure_07_monthly_language_trends_top5.xlsx`
- `figure_08_developer_response_timeline.xlsx`

#### Text metrics
- `figure_09_top_unigrams_positive.xlsx`
- `figure_10_top_unigrams_negative.xlsx`
- `figure_11_distinctive_terms_positive_vs_negative.xlsx`
- `figure_12_distinctive_terms_negative_vs_positive.xlsx`

#### Emotion metrics
- `figure_13_emotion_distribution_summary.xlsx`
- `figure_14_emotion_by_polarity.xlsx`
- `figure_15_emotion_by_month_selected.xlsx`

#### Theme metrics
- `figure_16_theme_distribution_summary.xlsx`
- `figure_17_theme_by_polarity.xlsx`
- `figure_18_theme_by_month_selected.xlsx`

### Important limitation of the current figure-generation stage

The figure-generation workflow does not calculate new substantive metrics. It only transforms existing validated tables into chart-ready Excel workbooks. Therefore, any limitation affecting the underlying source table also affects the figure derived from it.

## Stage 9: word-cloud generation

The word-cloud stage reads the cleaned review dataset and generates unigram, bigram, and trigram word-cloud visualisations from tokenised text.

### Word-cloud input

The word-cloud stage reads:

`data/processed/steam_reviews/<game_slug>/cleaned/<game_slug>_reviews_cleaned.csv`

### Word-cloud tasks

The word-cloud stage is intended to:

- load the cleaned review dataset for the selected game;
- optionally filter the corpus to a configured `target_language`;
- retain only rows with usable review text;
- tokenise the review text using regex-based tokenisation;
- optionally remove stopwords;
- build unigram, bigram, and trigram frequency counters;
- apply configurable minimum-frequency thresholds and maximum-size cut-offs;
- generate PNG word-cloud images from the filtered frequencies;
- export the exact frequencies used to build each word cloud as CSV files;
- export a word-cloud summary JSON file;
- export a word-cloud log.

### Word-cloud configuration

The optional `word_cloud` block in the game configuration may control parameters such as:

- `target_language`
- `min_token_length`
- `remove_stopwords`
- `max_words_unigrams`
- `max_words_bigrams`
- `max_words_trigrams`
- `min_frequency_unigrams`
- `min_frequency_bigrams`
- `min_frequency_trigrams`
- `width`
- `height`
- `background_colour`
- `collocations`

### Word-cloud outputs

For each `game_slug`, the word-cloud workflow exports:

1. **PNG images under `results/<game_slug>/figures/word_cloud/`**
2. **frequency CSV files under `results/<game_slug>/figures/word_cloud/`**
3. **a word-cloud summary JSON file under `data/processed/steam_reviews/<game_slug>/metrics/`**
4. **a word-cloud log under `data/processed/steam_reviews/<game_slug>/metrics/`**

### Word-cloud output files

Typical files include:

#### PNG images
- `<game_slug>_wordcloud_unigrams.png`
- `<game_slug>_wordcloud_bigrams.png`
- `<game_slug>_wordcloud_trigrams.png`

#### Frequency CSV files
- `<game_slug>_wordcloud_unigrams_frequencies.csv`
- `<game_slug>_wordcloud_bigrams_frequencies.csv`
- `<game_slug>_wordcloud_trigrams_frequencies.csv`

#### Metrics files
- `<game_slug>_word_cloud_summary.json`
- `<game_slug>_word_cloud.log`

## Exhaustive definition of columns in word-cloud frequency tables

### `<game_slug>_wordcloud_unigrams_frequencies.csv`
- `rank`: descending frequency rank among exported unigrams.
- `unigram`: token included in the unigram word cloud.
- `frequency`: filtered unigram frequency used by the word-cloud generator.

### `<game_slug>_wordcloud_bigrams_frequencies.csv`
- `rank`: descending frequency rank among exported bigrams.
- `bigram`: bigram included in the bigram word cloud.
- `frequency`: filtered bigram frequency used by the word-cloud generator.

### `<game_slug>_wordcloud_trigrams_frequencies.csv`
- `rank`: descending frequency rank among exported trigrams.
- `trigram`: trigram included in the trigram word cloud.
- `frequency`: filtered trigram frequency used by the word-cloud generator.

## Word-cloud summary JSON

The summary JSON stored in:

`data/processed/steam_reviews/<game_slug>/metrics/<game_slug>_word_cloud_summary.json`

contains, at minimum:

- repository and game identifiers
- generation timestamp
- word-cloud configuration parameters
- corpus summary values such as:
  - `rows_in_cleaned_dataset`
  - `rows_used_for_word_clouds`
  - `total_tokens_used`
- output file paths
- frequency-table sizes for:
  - `unigrams`
  - `bigrams`
  - `trigrams`

## Word-cloud log

The log stored in:

`data/processed/steam_reviews/<game_slug>/metrics/<game_slug>_word_cloud.log`

records the execution of the word-cloud stage.

### Important limitation of the current word-cloud stage

The current workflow is frequency-based. It inherits the same tokenisation and stopword limitations that affect textual preprocessing. Therefore:

- the size of words in the clouds reflects filtered frequency, not semantic salience;
- language segmentation issues may affect results in non-whitespace-delimited languages;
- the visual output depends directly on the selected thresholds and frequency cut-offs.

## Stage 10: output validation

The validation stage checks the structural integrity of the generated outputs.

### Validation input

The validation stage reads selected files from:

- `data/raw/steam_reviews/<game_slug>/...`
- `data/processed/steam_reviews/<game_slug>/...`
- `results/<game_slug>/tables/...`
- `results/<game_slug>/figures/...`

### Validation tasks

The validation stage is intended to:

- verify the existence of key files;
- verify required columns in selected CSV tables;
- verify that selected tables are not unexpectedly empty;
- verify selected internal consistency rules across outputs;
- verify the presence of required worksheets in generated Excel figure workbooks;
- verify the presence and minimal structure of word-cloud outputs;
- export a machine-readable validation summary;
- export a validation log.

### Validation outputs

For each `game_slug`, the validation workflow exports:

1. **a validation summary JSON file under `data/processed/steam_reviews/<game_slug>/metrics/`**
2. **a validation log under `data/processed/steam_reviews/<game_slug>/metrics/`**

Files:

- `<game_slug>_validation_summary.json`
- `<game_slug>_validation.log`

## Exhaustive definition of validation summary structure

### `<game_slug>_validation_summary.json`

This JSON typically contains:

- `app_id`
- `game_slug`
- `game_title`
- `generated_at_utc`
- `check_count_total`
- `check_count_passed`
- `check_count_failed`
- `error_failures`
- `warning_failures`
- `final_status`
- `checks`

### `checks`

`checks` is a list of validation records. Each record may contain:

- `check_id`: unique identifier of the validation check.
- `passed`: boolean indicating whether the check passed.
- `severity`: usually `error` or `warning`.
- `message`: human-readable description of the result.
- `details`: structured object with additional information, such as missing columns, row counts, file paths, or missing worksheets.

### Validation scope note

The validation stage is not intended to replace substantive scholarly interpretation. It only checks structural expectations and selected consistency rules.

## Stage 11: pipeline orchestration

The pipeline runner executes the repository stages in sequence for one selected game configuration.

### Pipeline tasks

The pipeline stage is intended to:

- read the selected game configuration;
- execute the repository scripts in the expected order;
- allow selective skipping of stages;
- capture return codes, standard output, and standard error;
- stop on the first failed stage by default;
- optionally continue on error when configured to do so;
- export a pipeline log;
- export a pipeline summary JSON file;
- export an output manifest JSON file.

### Default pipeline order

The current implementation typically runs:

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

### Pipeline configuration and execution flags

The pipeline runner takes a configuration file and may be executed with skip flags such as:

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

It may also be executed with:

- `--continue-on-error`

### Pipeline outputs

For each `game_slug`, the pipeline workflow exports:

1. **a pipeline log under `data/processed/steam_reviews/<game_slug>/metrics/`**
2. **a pipeline summary JSON file under `data/processed/steam_reviews/<game_slug>/metrics/`**
3. **an output manifest JSON file under `data/processed/steam_reviews/<game_slug>/metrics/`**

Files:

- `<game_slug>_pipeline.log`
- `<game_slug>_pipeline_summary.json`
- `<game_slug>_output_manifest.json`

## Exhaustive definition of pipeline summary structure

### `<game_slug>_pipeline_summary.json`

This JSON typically contains:

- `app_id`
- `game_slug`
- `game_title`
- `generated_at_utc`
- `config_path`
- `pipeline_log`
- `output_manifest`
- `stage_count_total`
- `stage_count_executed`
- `stage_count_success`
- `stage_count_failed`
- `stage_count_skipped`
- `final_status`

## Exhaustive definition of output manifest structure

### `<game_slug>_output_manifest.json`

This JSON typically contains:

- `app_id`
- `game_slug`
- `game_title`
- `generated_at_utc`
- `roots`
- `stage_results`
- `important_outputs`
- `directories`

### `roots`

The `roots` object typically contains:

- `raw_root`
- `processed_root`
- `results_root`

### `stage_results`

`stage_results` is a list of stage records. Each record may contain:

- `stage_id`
- `stage_label`
- `script_path`
- `enabled`
- `status`
- `return_code`
- `started_at_utc`
- `finished_at_utc`

### `important_outputs`

The `important_outputs` object typically maps key output names to file records. Each file record may contain:

- `path`
- `exists`
- `is_file`
- `is_dir`
- `size_bytes`
- `modified_at_utc`

### `directories`

The `directories` object typically contains file listings for selected repository folders such as:

- raw combined outputs
- raw chunks
- raw metadata
- raw logs
- processed cleaned outputs
- processed enriched outputs
- processed metrics outputs
- results tables
- results figures

Directory listings usually consist of file-record objects similar to those in `important_outputs`.

### Pipeline manifest scope note

The output manifest is designed as a traceability and audit artefact. It should not be treated as a descriptive-results table.

## Variables retained and derived

The collection stage preserves the main review-level and author-level variables returned by the endpoint.

The preparation stage adds repository context variables, readable datetime fields, date-based variables, text-length variables, review-status variables, and interval variables.

The basic analysis stage computes descriptive, distributional, and cross-tabulated outputs.

The temporal analysis stage computes timeline-based, rate-based, and cross-tabulated outputs.

The text-analysis stage computes token-based, n-gram-based, polarity-based, language-based, and playtime-band-based outputs from the prepared dataset.

The emotion-analysis stage computes lexicon-based review enrichment and emotion aggregates from a target-language textual subset of the prepared dataset.

The theme-analysis stage computes dictionary-based review enrichment and theme aggregates from a target-language textual subset of the prepared dataset.

The figure-generation stage derives workbook-level visual outputs and chart-ready transformed tables from already-generated result tables.

The word-cloud stage derives filtered textual frequency tables and word-cloud images from the cleaned textual corpus.

The validation stage derives structural checks and consistency checks over already-generated outputs.

The pipeline stage derives execution metadata, stage summaries, and output manifests.

## Data quality considerations

The repository captures only the review data exposed through Steam’s store review system. It does not capture discourse from other environments such as discussion boards, social media, specialist press, or other digital storefronts.

Repeated collections may differ over time if reviews are edited, removed, moderated, or re-ranked.

Textual outputs for languages requiring language-specific segmentation should be interpreted cautiously under the current implementation.

Emotion outputs should be interpreted as lexicon-based approximations rather than as full semantic emotion recognition.

Theme outputs should be interpreted as dictionary-based approximations rather than as full semantic topic recognition.

Figure outputs should be interpreted as visual derivatives of source tables rather than as independent analytical stages.

Word-cloud outputs should be interpreted as filtered visual summaries of token frequency rather than as direct evidence of conceptual centrality by themselves.

Validation outputs should be interpreted as structural checks, not as guarantees of interpretive correctness.

Pipeline outputs should be interpreted as execution-control artefacts, not as analytical metrics in themselves.

## Reproducibility principles

This repository is structured to support reproducible research by preserving:

- explicit configuration files;
- a predictable directory structure;
- raw and processed outputs in separate locations;
- progress logs and collection metadata;
- reusable scripts that can be applied to multiple games;
- figure workbooks that retain their source data and metadata internally;
- word-cloud frequency tables that retain the exact filtered inputs behind each image;
- validation summaries that retain structural checks;
- and pipeline manifests that retain execution traceability.

## Recommended reporting practice

Any publication or report derived from datasets generated with this repository should state clearly:

- the target game;
- the Steam `app_id`;
- the date of collection;
- the parameter configuration used;
- the deduplication rule;
- the total number of unique reviews retrieved;
- the principal preparation steps applied before analysis;
- the scope of the descriptive outputs used in interpretation;
- the scope of textual preprocessing choices;
- the scope of emotion-analysis choices, including lexicon and target language;
- the scope of theme-analysis choices, including dictionary and target language;
- the source tables from which any published Excel figures were derived;
- the tokenisation and filtering settings used for any published word clouds;
- the validation scope, if validation results are cited;
- and, where relevant, the specific result tables on which claims are based.

## Scope of the repository

This repository is conceived as a reusable methodological framework rather than as a single-game archive. Each dataset should therefore be understood as one instance of a broader, repeatable collection, preparation, analysis, validation, figure-generation, word-cloud, and pipeline workflow for Steam review research.
