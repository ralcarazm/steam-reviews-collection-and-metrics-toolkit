# Data Dictionary

## Overview

This document describes the **base data fields** used in this repository for Steam review collection and preparation workflows.

Its primary purpose is to document:

- the original review fields returned by the Steam Store Reviews endpoint;
- the core structural meaning of those fields;
- the principal units, types, and interpretation notes associated with them.

This file is mainly concerned with the **source dataset** and its direct normalised representation in the repository.

More detailed documentation about:

- derived variables created during preparation,
- aggregated columns generated in metrics tables,
- enriched columns created during emotion or theme analysis,
- the structure of Excel figure workbooks,
- validation outputs,
- and pipeline manifest outputs

is documented in `docs/methodology.md`.

## Source

- **Platform**: Steam
- **Endpoint**: `store.steampowered.com/appreviews/<appid>?json=1`
- **Scope**: one dataset per game, identified by `app_id`, `game_slug`, and `game_title`

## Dataset structure

Each row in an exported dataset represents **one user review** for one selected game.

All raw outputs for a given game are stored under:

`data/raw/steam_reviews/<game_slug>/`

## Core source variables

| Field name | Type | Description |
|---|---|---|
| `recommendationid` | string | Unique identifier of the review. |
| `steamid` | string | Unique Steam identifier of the reviewer. |
| `num_games_owned` | integer | Number of games owned by the reviewer. |
| `num_reviews` | integer | Number of reviews written by the reviewer. |
| `playtime_forever` | integer | Total playtime recorded for the reviewed application. |
| `playtime_last_two_weeks` | integer | Playtime recorded for the reviewed application during the last two weeks. |
| `playtime_at_review` | integer | Playtime recorded for the reviewed application when the review was written. |
| `deck_playtime_at_review` | integer / null | Steam Deck playtime recorded when the review was written. |
| `last_played` | integer | Timestamp corresponding to the last time the reviewer played the application. |
| `language` | string | Language selected by the user when writing the review. |
| `review` | string | Full text of the review. |
| `timestamp_created` | integer | Unix timestamp indicating when the review was created. |
| `timestamp_updated` | integer | Unix timestamp indicating when the review was last updated. |
| `voted_up` | boolean | Whether the review is a positive recommendation. |
| `votes_up` | integer | Number of users who marked the review as helpful. |
| `votes_funny` | integer | Number of users who marked the review as funny. |
| `weighted_vote_score` | string | Helpfulness score returned by Steam. |
| `comment_count` | integer | Number of comments posted on the review. |
| `steam_purchase` | boolean | Whether the reviewer purchased the game on Steam. |
| `received_for_free` | boolean | Whether the reviewer indicated that the application was obtained for free. |
| `written_during_early_access` | boolean | Whether the review was posted while the game was in Early Access. |
| `developer_response` | string / null | Text of the developer response, if present. |
| `timestamp_dev_responded` | integer / null | Unix timestamp of the developer response, if present. |
| `primarily_steam_deck` | boolean / null | Whether the reviewer primarily played the game on Steam Deck at the time of writing. |

## Repository context fields

In downstream stages, the repository may also attach **contextual identifier fields** so that datasets remain traceable across multiple games.

Typical examples include:

| Field name | Type | Description |
|---|---|---|
| `app_id` | integer | Steam application identifier for the selected game. |
| `game_slug` | string | Normalised game identifier used in paths and filenames. |
| `game_title` | string | Human-readable game title used in logs and metadata. |

These fields are repository-level contextual variables rather than direct review fields returned by the Steam endpoint.

## Frequently derived variable families

In later stages of the repository workflow, additional columns may be created from the base fields above. These are **not exhaustively defined here**, but they usually belong to the following families:

### Datetime derivatives

Examples:
- readable UTC datetime fields derived from Unix timestamps
- year, month, day, or year-month grouping fields

These are typically derived from:
- `timestamp_created`
- `timestamp_updated`
- `timestamp_dev_responded`
- `last_played`

### Playtime derivatives

Examples:
- post-review playtime indicators
- playtime bands
- continuation-of-play indicators

These are typically derived from:
- `playtime_at_review`
- `playtime_forever`
- `playtime_last_two_weeks`

### Text-length derivatives

Examples:
- character counts
- word counts
- line counts
- text-presence flags

These are typically derived from:
- `review`

### Review-status and interval derivatives

Examples:
- updated-after-creation flags
- developer-response flags
- days between review creation and update
- days to developer response
- days between review and last played

These are typically derived from timestamp and review-status fields.

### Enriched text-analysis derivatives

Examples:
- token lists
- token counts
- frequency-based textual metrics
- emotion counts and rates
- theme counts and presence flags

These are created only in specific downstream analysis stages and are documented in `docs/methodology.md`.

### Validation and pipeline control artefacts

Examples:
- validation checks
- stage execution summaries
- output manifests
- inventory records

These are not review-level variables. They are control and traceability artefacts generated by `validate_outputs.py` and `run_pipeline.py`, and they are documented in `docs/methodology.md`.

## Notes on interpretation

### Review polarity

The field `voted_up` represents Steam’s native recommendation variable. It should be interpreted as recommendation status rather than as a fine-grained sentiment score.

### Use-related variables

The playtime variables refer to the **reviewed application**, not to the user’s whole Steam library. This distinction is important when comparing `playtime_at_review`, `playtime_forever`, and `playtime_last_two_weeks`.

### Interaction variables

The variables `votes_up`, `votes_funny`, `weighted_vote_score`, and `comment_count` can be used as indicators of visibility and reception within Steam’s review environment. They do not directly measure game quality.

### Developer-response variables

`developer_response` and `timestamp_dev_responded` refer to platform-visible responses made by the developer or publisher in Steam’s review interface. Their absence should not be interpreted as missing processing; in many datasets, no response exists for most reviews.

### Steam Deck-related variables

`deck_playtime_at_review` and `primarily_steam_deck` are platform-specific fields. They may be null because Steam did not provide a value, because the field was not applicable, or because the play session was not primarily associated with Steam Deck use.

### Missing values

Some fields may legitimately contain null values, especially:

- `deck_playtime_at_review`
- `developer_response`
- `timestamp_dev_responded`
- `primarily_steam_deck`

In most cases, null values indicate that the value was not present or not applicable in the source response.

## Units and storage conventions

Unless otherwise stated:

- **timestamp variables** are stored as Unix timestamps in the source dataset;
- **playtime variables** are stored in **minutes**;
- **boolean review-status variables** follow Steam’s native logic and may later be normalised in cleaned datasets.

## File organisation

For each `game_slug`, the repository may contain:

### Raw outputs

- chunked raw files in `data/raw/steam_reviews/<game_slug>/chunks/`
- combined raw files in `data/raw/steam_reviews/<game_slug>/combined/`
- collection metadata in `data/raw/steam_reviews/<game_slug>/metadata/`
- collection logs in `data/raw/steam_reviews/<game_slug>/logs/`

### Processed derivatives

Processed derivatives may later be stored in:

- `data/processed/steam_reviews/<game_slug>/cleaned/`
- `data/processed/steam_reviews/<game_slug>/enriched/`
- `data/processed/steam_reviews/<game_slug>/metrics/`

### Result artefacts

Derived result artefacts may later be stored in:

- `results/<game_slug>/tables/`
- `results/<game_slug>/figures/`

### Control and audit artefacts

The repository may also contain control-oriented outputs in:

- `data/processed/steam_reviews/<game_slug>/metrics/`

including:

- validation summaries
- validation logs
- pipeline summaries
- pipeline logs
- output manifests

## Scope note

This data dictionary should be read as the reference for the **base review fields** and the **main structural meaning of the dataset**.

It does **not** replace:

- `docs/methodology.md` for workflow, derived variables, aggregated result columns, figure outputs, validation outputs, and pipeline outputs;
- script-level comments for implementation details;
- or individual result tables for specific metric families.

## Recommended citation practice

If you use any dataset generated with this repository, cite both:

1. this repository;
2. the Steam reviews endpoint as the original raw-data source;
3. and the specific derived publication, where applicable.
