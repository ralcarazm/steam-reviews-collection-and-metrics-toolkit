#!/usr/bin/env python3
"""
prepare_reviews.py

Generic Steam review preparation script for multiple games.

This script:
- reads a per-game JSON configuration file;
- loads the combined raw review dataset for one selected game;
- normalises data types;
- converts Unix timestamps to readable UTC date fields;
- derives analytical variables useful for later stages;
- exports a cleaned dataset under data/processed/steam_reviews/<game_slug>/cleaned/;
- optionally exports a cleaned JSON file;
- writes preparation metadata.

Usage examples:

    python scripts/02_data_preparation/prepare_reviews.py \
        --config config/games/example_game.json

    python scripts/02_data_preparation/prepare_reviews.py \
        --config config/games/example_game.json \
        --no-cleaned-json

Author:
    Rubén Alcaraz Martínez

Licence:
    GNU General Public License v3.0
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class GameConfig:
    """Configuration values for a single game preparation run."""
    app_id: int
    game_slug: str
    game_title: str


# ============================================================================
# ARGUMENT PARSING
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Prepare a cleaned Steam review dataset for one game using a JSON configuration file."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the JSON configuration file for the target game.",
    )
    parser.add_argument(
        "--no-cleaned-json",
        action="store_true",
        help="Skip export of the cleaned JSON file.",
    )
    return parser.parse_args()


# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def load_game_config(config_path: Path) -> GameConfig:
    """Load and validate the game configuration file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = json.load(handle)

    required_fields = ["app_id", "game_slug", "game_title"]
    missing_fields = [field for field in required_fields if field not in raw_config]
    if missing_fields:
        raise ValueError(
            f"Missing required configuration fields: {', '.join(missing_fields)}"
        )

    return GameConfig(
        app_id=int(raw_config["app_id"]),
        game_slug=str(raw_config["game_slug"]).strip(),
        game_title=str(raw_config["game_title"]).strip(),
    )


# ============================================================================
# PATH MANAGEMENT
# ============================================================================

def get_repository_root() -> Path:
    """
    Resolve the repository root assuming this file lives at:
    scripts/02_data_preparation/prepare_reviews.py
    """
    return Path(__file__).resolve().parents[2]


def build_paths(repository_root: Path, game_slug: str) -> Dict[str, Path]:
    """Build all input and output paths for one game."""
    raw_root = repository_root / "data" / "raw" / "steam_reviews" / game_slug
    processed_root = repository_root / "data" / "processed" / "steam_reviews" / game_slug

    paths = {
        "raw_root": raw_root,
        "combined_dir": raw_root / "combined",
        "metadata_dir_raw": raw_root / "metadata",
        "processed_root": processed_root,
        "cleaned_dir": processed_root / "cleaned",
        "enriched_dir": processed_root / "enriched",
        "metrics_dir": processed_root / "metrics",
    }

    paths["input_csv"] = paths["combined_dir"] / f"{game_slug}_reviews_all.csv"
    paths["input_json"] = paths["combined_dir"] / f"{game_slug}_reviews_all.json"

    paths["cleaned_csv"] = paths["cleaned_dir"] / f"{game_slug}_reviews_cleaned.csv"
    paths["cleaned_json"] = paths["cleaned_dir"] / f"{game_slug}_reviews_cleaned.json"
    paths["preparation_metadata_json"] = (
        paths["cleaned_dir"] / f"{game_slug}_preparation_metadata.json"
    )
    paths["preparation_log"] = paths["cleaned_dir"] / f"{game_slug}_preparation.log"

    return paths


def ensure_directories(paths: Dict[str, Path]) -> None:
    """Create all required output directories."""
    for key in ["cleaned_dir", "enriched_dir", "metrics_dir"]:
        paths[key].mkdir(parents=True, exist_ok=True)


# ============================================================================
# LOGGING
# ============================================================================

def configure_logging(log_file: Path) -> None:
    """Configure console and file logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


# ============================================================================
# DATA LOADING
# ============================================================================

def load_raw_reviews(input_csv: Path) -> pd.DataFrame:
    """Load the combined raw CSV dataset."""
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    df = pd.read_csv(input_csv, encoding="utf-8-sig", low_memory=False)
    if df.empty:
        raise ValueError("The input CSV exists but contains no rows.")

    return df


# ============================================================================
# NORMALISATION HELPERS
# ============================================================================

def ensure_expected_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all expected raw columns exist, adding missing ones as empty."""
    expected_columns = [
        "recommendationid",
        "steamid",
        "num_games_owned",
        "num_reviews",
        "playtime_forever",
        "playtime_last_two_weeks",
        "playtime_at_review",
        "deck_playtime_at_review",
        "last_played",
        "language",
        "review",
        "timestamp_created",
        "timestamp_updated",
        "voted_up",
        "votes_up",
        "votes_funny",
        "weighted_vote_score",
        "comment_count",
        "steam_purchase",
        "received_for_free",
        "written_during_early_access",
        "developer_response",
        "timestamp_dev_responded",
        "primarily_steam_deck",
    ]

    for column in expected_columns:
        if column not in df.columns:
            df[column] = pd.NA

    return df


def normalise_string_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Normalise string columns by stripping whitespace and harmonising blanks."""
    for column in columns:
        df[column] = df[column].astype("string")
        df[column] = df[column].str.replace(r"\r\n?", "\n", regex=True)
        df[column] = df[column].str.strip()
        df[column] = df[column].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    return df


def normalise_numeric_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Convert numeric columns using pandas nullable types."""
    for column in columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
    return df


def normalise_boolean_series(series: pd.Series) -> pd.Series:
    """Convert a mixed-format series to pandas nullable boolean."""
    mapping = {
        "true": True,
        "false": False,
        "1": True,
        "0": False,
        "yes": True,
        "no": False,
        "t": True,
        "f": False,
    }

    def convert(value: Any) -> Any:
        if pd.isna(value):
            return pd.NA
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in mapping:
            return mapping[text]
        return pd.NA

    return series.map(convert).astype("boolean")


def normalise_boolean_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Normalise boolean columns."""
    for column in columns:
        df[column] = normalise_boolean_series(df[column])
    return df


def normalise_language_column(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise the language field to lowercase labels."""
    df["language"] = df["language"].astype("string").str.strip().str.lower()
    df["language"] = df["language"].replace({"": pd.NA, "nan": pd.NA})
    return df


def clean_review_text(text: Any) -> Any:
    """Clean review text without changing substantive wording."""
    if pd.isna(text):
        return pd.NA

    cleaned = str(text)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()

    return cleaned if cleaned else pd.NA


def normalise_review_text(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise the review text field."""
    df["review"] = df["review"].map(clean_review_text).astype("string")
    return df


def convert_unix_timestamp_to_utc_datetime(series: pd.Series) -> pd.Series:
    """Convert Unix timestamps to pandas UTC datetimes."""
    numeric = pd.to_numeric(series, errors="coerce")
    return pd.to_datetime(numeric, unit="s", utc=True, errors="coerce")


# ============================================================================
# DERIVED VARIABLES
# ============================================================================

def add_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add readable UTC datetime and date columns derived from Unix timestamps."""
    df["review_created_datetime_utc"] = convert_unix_timestamp_to_utc_datetime(df["timestamp_created"])
    df["review_updated_datetime_utc"] = convert_unix_timestamp_to_utc_datetime(df["timestamp_updated"])
    df["last_played_datetime_utc"] = convert_unix_timestamp_to_utc_datetime(df["last_played"])
    df["developer_responded_datetime_utc"] = convert_unix_timestamp_to_utc_datetime(df["timestamp_dev_responded"])

    df["review_created_date"] = df["review_created_datetime_utc"].dt.date.astype("string")
    df["review_updated_date"] = df["review_updated_datetime_utc"].dt.date.astype("string")
    df["last_played_date"] = df["last_played_datetime_utc"].dt.date.astype("string")
    df["developer_responded_date"] = df["developer_responded_datetime_utc"].dt.date.astype("string")

    df["review_created_year"] = df["review_created_datetime_utc"].dt.year.astype("Int64")
    df["review_created_month"] = df["review_created_datetime_utc"].dt.month.astype("Int64")
    df["review_created_year_month"] = (
        df["review_created_datetime_utc"].dt.strftime("%Y-%m").astype("string")
    )

    return df


def add_text_length_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Add basic text-length variables."""
    review_text = df["review"].fillna("").astype("string")

    df["review_length_chars"] = review_text.str.len().astype("Int64")
    df["review_length_chars_no_spaces"] = (
        review_text.str.replace(r"\s+", "", regex=True).str.len().astype("Int64")
    )
    df["review_length_words"] = (
        review_text.str.findall(r"\S+").str.len().astype("Int64")
    )
    df["review_length_lines"] = (
        review_text.str.count(r"\n").fillna(0).astype("Int64") + 1
    )
    df.loc[df["review"].isna(), "review_length_lines"] = pd.NA

    return df


def add_review_status_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Add simple status and analytical flags."""
    df["is_positive"] = df["voted_up"].astype("boolean")
    df["is_negative"] = (~df["voted_up"]).where(df["voted_up"].notna(), pd.NA).astype("boolean")

    df["has_text_review"] = df["review"].notna().astype("boolean")
    df["has_developer_response"] = df["developer_response"].notna().astype("boolean")
    df["has_comments"] = (df["comment_count"].fillna(0) > 0).astype("boolean")
    df["has_helpful_votes"] = (df["votes_up"].fillna(0) > 0).astype("boolean")
    df["has_funny_votes"] = (df["votes_funny"].fillna(0) > 0).astype("boolean")
    df["is_steam_purchase"] = df["steam_purchase"].astype("boolean")
    df["is_free_copy"] = df["received_for_free"].astype("boolean")
    df["is_early_access_review"] = df["written_during_early_access"].astype("boolean")
    df["is_primarily_steam_deck"] = df["primarily_steam_deck"].astype("boolean")

    return df


def add_playtime_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Add playtime-derived metrics."""
    playtime_forever = pd.to_numeric(df["playtime_forever"], errors="coerce")
    playtime_at_review = pd.to_numeric(df["playtime_at_review"], errors="coerce")
    playtime_last_two_weeks = pd.to_numeric(df["playtime_last_two_weeks"], errors="coerce")
    deck_playtime_at_review = pd.to_numeric(df["deck_playtime_at_review"], errors="coerce")

    df["playtime_post_review"] = (playtime_forever - playtime_at_review).astype("Float64")
    df.loc[df["playtime_post_review"] < 0, "playtime_post_review"] = pd.NA
    df["playtime_post_review"] = df["playtime_post_review"].round().astype("Int64")

    played_after_review = (
        (playtime_forever.notna()) &
        (playtime_at_review.notna()) &
        (playtime_forever > playtime_at_review)
    )
    df["played_after_review"] = played_after_review.astype("boolean")
    df.loc[playtime_forever.isna() | playtime_at_review.isna(), "played_after_review"] = pd.NA

    df["review_updated_after_creation"] = (
        (df["timestamp_updated"].notna()) &
        (df["timestamp_created"].notna()) &
        (df["timestamp_updated"] > df["timestamp_created"])
    ).astype("boolean")
    df.loc[df["timestamp_updated"].isna() | df["timestamp_created"].isna(), "review_updated_after_creation"] = pd.NA

    df["used_steam_deck_at_review"] = (
        deck_playtime_at_review.fillna(0) > 0
    ).astype("boolean")
    df.loc[deck_playtime_at_review.isna(), "used_steam_deck_at_review"] = pd.NA

    df["recent_playtime_recorded"] = (
        playtime_last_two_weeks.fillna(0) > 0
    ).astype("boolean")
    df.loc[playtime_last_two_weeks.isna(), "recent_playtime_recorded"] = pd.NA

    return df


def add_date_interval_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Add interval variables derived from timestamps."""
    df["days_between_creation_and_update"] = (
        (df["review_updated_datetime_utc"] - df["review_created_datetime_utc"]).dt.total_seconds() / 86400
    ).round(3)

    df["days_between_review_and_last_played"] = (
        (df["last_played_datetime_utc"] - df["review_created_datetime_utc"]).dt.total_seconds() / 86400
    ).round(3)

    df["days_to_developer_response"] = (
        (df["developer_responded_datetime_utc"] - df["review_created_datetime_utc"]).dt.total_seconds() / 86400
    ).round(3)

    for column in [
        "days_between_creation_and_update",
        "days_between_review_and_last_played",
        "days_to_developer_response",
    ]:
        df[column] = df[column].astype("Float64")

    return df


def add_repository_context_columns(df: pd.DataFrame, config: GameConfig) -> pd.DataFrame:
    """Add stable repository-level identification columns."""
    df["app_id"] = config.app_id
    df["game_slug"] = config.game_slug
    df["game_title"] = config.game_title
    return df


# ============================================================================
# PREPARATION PIPELINE
# ============================================================================

def prepare_reviews(df: pd.DataFrame, config: GameConfig) -> pd.DataFrame:
    """Run the full preparation pipeline."""
    df = df.copy()

    df = ensure_expected_columns(df)

    df = normalise_string_columns(
        df,
        columns=[
            "recommendationid",
            "steamid",
            "language",
            "review",
            "weighted_vote_score",
            "developer_response",
        ],
    )

    df = normalise_numeric_columns(
        df,
        columns=[
            "num_games_owned",
            "num_reviews",
            "playtime_forever",
            "playtime_last_two_weeks",
            "playtime_at_review",
            "deck_playtime_at_review",
            "last_played",
            "timestamp_created",
            "timestamp_updated",
            "votes_up",
            "votes_funny",
            "comment_count",
            "timestamp_dev_responded",
        ],
    )

    df = normalise_boolean_columns(
        df,
        columns=[
            "voted_up",
            "steam_purchase",
            "received_for_free",
            "written_during_early_access",
            "primarily_steam_deck",
        ],
    )

    df = normalise_language_column(df)
    df = normalise_review_text(df)

    df = add_repository_context_columns(df, config)
    df = add_datetime_columns(df)
    df = add_text_length_variables(df)
    df = add_review_status_variables(df)
    df = add_playtime_variables(df)
    df = add_date_interval_variables(df)

    df = df.drop_duplicates(subset=["recommendationid"], keep="first").reset_index(drop=True)

    preferred_column_order = [
        "app_id",
        "game_slug",
        "game_title",
        "recommendationid",
        "steamid",
        "language",
        "review",
        "is_positive",
        "is_negative",
        "voted_up",
        "steam_purchase",
        "received_for_free",
        "written_during_early_access",
        "primarily_steam_deck",
        "is_steam_purchase",
        "is_free_copy",
        "is_early_access_review",
        "is_primarily_steam_deck",
        "has_text_review",
        "has_developer_response",
        "has_comments",
        "has_helpful_votes",
        "has_funny_votes",
        "num_games_owned",
        "num_reviews",
        "playtime_forever",
        "playtime_last_two_weeks",
        "playtime_at_review",
        "deck_playtime_at_review",
        "playtime_post_review",
        "played_after_review",
        "used_steam_deck_at_review",
        "recent_playtime_recorded",
        "last_played",
        "timestamp_created",
        "timestamp_updated",
        "timestamp_dev_responded",
        "review_created_datetime_utc",
        "review_updated_datetime_utc",
        "last_played_datetime_utc",
        "developer_responded_datetime_utc",
        "review_created_date",
        "review_updated_date",
        "last_played_date",
        "developer_responded_date",
        "review_created_year",
        "review_created_month",
        "review_created_year_month",
        "days_between_creation_and_update",
        "days_between_review_and_last_played",
        "days_to_developer_response",
        "review_updated_after_creation",
        "review_length_chars",
        "review_length_chars_no_spaces",
        "review_length_words",
        "review_length_lines",
        "votes_up",
        "votes_funny",
        "weighted_vote_score",
        "comment_count",
        "developer_response",
    ]

    remaining_columns = [col for col in df.columns if col not in preferred_column_order]
    df = df[preferred_column_order + remaining_columns]

    return df


# ============================================================================
# EXPORT
# ============================================================================

def export_cleaned_dataset(
    df: pd.DataFrame,
    cleaned_csv: Path,
    cleaned_json: Path,
    write_json: bool,
) -> None:
    """Export the cleaned dataset."""
    df.to_csv(cleaned_csv, index=False, encoding="utf-8-sig")
    logging.info("Cleaned CSV written to: %s", cleaned_csv)

    if write_json:
        export_df = df.copy()

        datetime_columns = export_df.select_dtypes(include=["datetimetz"]).columns.tolist()
        for column in datetime_columns:
            export_df[column] = export_df[column].astype("string")

        export_df = export_df.where(pd.notna(export_df), None)

        with cleaned_json.open("w", encoding="utf-8") as handle:
            json.dump(export_df.to_dict(orient="records"), handle, ensure_ascii=False, indent=2)

        logging.info("Cleaned JSON written to: %s", cleaned_json)


def write_preparation_metadata(
    df: pd.DataFrame,
    config: GameConfig,
    metadata_path: Path,
) -> None:
    """Write preparation metadata."""
    metadata = {
        "app_id": config.app_id,
        "game_slug": config.game_slug,
        "game_title": config.game_title,
        "rows_exported": int(len(df)),
        "columns_exported": int(len(df.columns)),
        "positive_reviews": int(df["is_positive"].fillna(False).sum()) if "is_positive" in df.columns else None,
        "negative_reviews": int(df["is_negative"].fillna(False).sum()) if "is_negative" in df.columns else None,
        "reviews_with_developer_response": int(df["has_developer_response"].fillna(False).sum())
        if "has_developer_response" in df.columns else None,
        "languages_detected": int(df["language"].dropna().nunique()) if "language" in df.columns else None,
        "prepared_at_utc": pd.Timestamp.utcnow().isoformat(),
    }

    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)

    logging.info("Preparation metadata written to: %s", metadata_path)


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    """Main entry point."""
    args = parse_arguments()

    config_path = Path(args.config).resolve()
    print(f"[INFO] Loading configuration: {config_path}")

    config = load_game_config(config_path)

    repository_root = get_repository_root()
    paths = build_paths(repository_root, config.game_slug)
    ensure_directories(paths)
    configure_logging(paths["preparation_log"])

    print(f"[INFO] Repository root: {repository_root}")
    print(f"[INFO] Game slug: {config.game_slug}")
    print(f"[INFO] Input CSV: {paths['input_csv']}")
    print(f"[INFO] Output CSV: {paths['cleaned_csv']}")

    logging.info("Starting review preparation.")
    logging.info("Configuration file: %s", config_path)
    logging.info("Game title: %s", config.game_title)
    logging.info("App ID: %s", config.app_id)
    logging.info("Game slug: %s", config.game_slug)

    raw_df = load_raw_reviews(paths["input_csv"])
    logging.info("Raw rows loaded: %s", len(raw_df))
    logging.info("Raw columns loaded: %s", len(raw_df.columns))

    cleaned_df = prepare_reviews(raw_df, config)

    logging.info("Cleaned rows prepared: %s", len(cleaned_df))
    logging.info("Cleaned columns prepared: %s", len(cleaned_df.columns))

    export_cleaned_dataset(
        df=cleaned_df,
        cleaned_csv=paths["cleaned_csv"],
        cleaned_json=paths["cleaned_json"],
        write_json=not args.no_cleaned_json,
    )

    write_preparation_metadata(
        df=cleaned_df,
        config=config,
        metadata_path=paths["preparation_metadata_json"],
    )

    logging.info("Preparation complete.")
    print("[INFO] Preparation complete.")


if __name__ == "__main__":
    main()