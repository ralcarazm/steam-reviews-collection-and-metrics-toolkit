#!/usr/bin/env python3
"""
compute_temporal_metrics.py

Generic Steam review temporal-metrics script for multiple games.

This script:
- reads a per-game JSON configuration file;
- loads the cleaned review dataset for one selected game;
- computes temporal descriptive metrics and cross-tabulations;
- exports temporal metrics tables as CSV files;
- exports a JSON summary of the main outputs;
- writes an analysis log.

Usage examples:

    python scripts/03_analysis/compute_temporal_metrics.py \
        --config config/games/example_game.json

Author:
    Rubén Alcaraz Martínez

Licence:
    GNU General Public License v3.0
"""

from __future__ import annotations

import argparse
import json
import logging
import math
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
    """Configuration values for a single game analysis run."""
    app_id: int
    game_slug: str
    game_title: str


# ============================================================================
# ARGUMENT PARSING
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compute temporal descriptive metrics for one prepared Steam review dataset."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the JSON configuration file for the target game.",
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
    scripts/03_analysis/compute_temporal_metrics.py
    """
    return Path(__file__).resolve().parents[2]


def build_paths(repository_root: Path, game_slug: str) -> Dict[str, Path]:
    """Build all required input and output paths."""
    processed_root = repository_root / "data" / "processed" / "steam_reviews" / game_slug
    results_root = repository_root / "results" / game_slug

    paths = {
        "processed_root": processed_root,
        "cleaned_dir": processed_root / "cleaned",
        "metrics_dir": processed_root / "metrics",
        "results_root": results_root,
        "tables_dir": results_root / "tables",
        "temporal_metrics_tables_dir": results_root / "tables" / "temporal_metrics",
    }

    paths["input_csv"] = paths["cleaned_dir"] / f"{game_slug}_reviews_cleaned.csv"
    paths["summary_json"] = paths["metrics_dir"] / f"{game_slug}_temporal_metrics_summary.json"
    paths["analysis_log"] = paths["metrics_dir"] / f"{game_slug}_temporal_metrics.log"

    return paths


def ensure_directories(paths: Dict[str, Path]) -> None:
    """Create required output directories."""
    for key in ["metrics_dir", "tables_dir", "temporal_metrics_tables_dir"]:
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

def load_cleaned_reviews(input_csv: Path) -> pd.DataFrame:
    """Load the cleaned CSV dataset."""
    if not input_csv.exists():
        raise FileNotFoundError(f"Input cleaned CSV not found: {input_csv}")

    df = pd.read_csv(input_csv, encoding="utf-8-sig", low_memory=False)
    if df.empty:
        raise ValueError("The cleaned CSV exists but contains no rows.")

    return df


# ============================================================================
# NORMALISATION
# ============================================================================

def restore_boolean_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Restore boolean columns after CSV import."""
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

    for column in columns:
        if column not in df.columns:
            continue

        def convert(value: Any) -> Any:
            if pd.isna(value):
                return pd.NA
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in mapping:
                return mapping[text]
            return pd.NA

        df[column] = df[column].map(convert).astype("boolean")

    return df


def restore_numeric_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Restore numeric columns after CSV import."""
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def normalise_loaded_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Restore expected types from the cleaned CSV."""
    boolean_columns = [
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
        "played_after_review",
        "used_steam_deck_at_review",
        "recent_playtime_recorded",
        "review_updated_after_creation",
    ]

    numeric_columns = [
        "app_id",
        "num_games_owned",
        "num_reviews",
        "playtime_forever",
        "playtime_last_two_weeks",
        "playtime_at_review",
        "deck_playtime_at_review",
        "playtime_post_review",
        "last_played",
        "timestamp_created",
        "timestamp_updated",
        "timestamp_dev_responded",
        "review_created_year",
        "review_created_month",
        "days_between_creation_and_update",
        "days_between_review_and_last_played",
        "days_to_developer_response",
        "review_length_chars",
        "review_length_chars_no_spaces",
        "review_length_words",
        "review_length_lines",
        "votes_up",
        "votes_funny",
        "comment_count",
    ]

    datetime_string_columns = [
        "review_created_datetime_utc",
        "review_updated_datetime_utc",
        "last_played_datetime_utc",
        "developer_responded_datetime_utc",
    ]

    df = restore_boolean_columns(df, boolean_columns)
    df = restore_numeric_columns(df, numeric_columns)

    for column in ["language", "game_slug", "game_title", "review_created_year_month"]:
        if column in df.columns:
            df[column] = df[column].astype("string")

    for column in datetime_string_columns:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], utc=True, errors="coerce")

    return df


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def safe_rate(numerator: float, denominator: float) -> float | None:
    """Return a percentage safely."""
    if denominator == 0 or pd.isna(denominator):
        return None
    return round((numerator / denominator) * 100, 4)


def to_serialisable(value: Any) -> Any:
    """Convert pandas/numpy values to JSON-safe Python values."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (int, float, str, bool)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def export_table(df: pd.DataFrame, output_path: Path) -> None:
    """Export one metrics table to CSV."""
    df.to_csv(output_path, index=False, encoding="utf-8-sig")


def dataframe_to_json_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert a dataframe to JSON-safe records."""
    records = []
    for record in df.to_dict(orient="records"):
        records.append({key: to_serialisable(value) for key, value in record.items()})
    return records


def add_time_group_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add date grouping columns used in temporal analysis."""
    df = df.copy()

    if "review_created_datetime_utc" in df.columns:
        dt = df["review_created_datetime_utc"]
        df["review_created_date_day"] = dt.dt.strftime("%Y-%m-%d").astype("string")
        df["review_created_date_week"] = dt.dt.to_period("W-MON").astype("string")
        df["review_created_date_month"] = dt.dt.strftime("%Y-%m").astype("string")

    if "review_updated_datetime_utc" in df.columns:
        dt = df["review_updated_datetime_utc"]
        df["review_updated_date_month"] = dt.dt.strftime("%Y-%m").astype("string")

    if "developer_responded_datetime_utc" in df.columns:
        dt = df["developer_responded_datetime_utc"]
        df["developer_responded_date_month"] = dt.dt.strftime("%Y-%m").astype("string")

    return df


def add_band_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add categorical bands useful for temporal tables."""
    df = df.copy()

    if "playtime_at_review" in df.columns:
        playtime_bins = [-float("inf"), 29, 119, 599, 1499, 2999, 5999, float("inf")]
        playtime_labels = [
            "<30m",
            "30m-1h59m",
            "2h-9h59m",
            "10h-24h59m",
            "25h-49h59m",
            "50h-99h59m",
            "100h+",
        ]
        df["playtime_at_review_band"] = pd.cut(
            df["playtime_at_review"],
            bins=playtime_bins,
            labels=playtime_labels,
        ).astype("string")

    if "num_reviews" in df.columns:
        reviewer_bins = [-float("inf"), 0, 1, 4, 9, float("inf")]
        reviewer_labels = ["0", "1", "2-4", "5-9", "10+"]
        df["num_reviews_band"] = pd.cut(
            df["num_reviews"],
            bins=reviewer_bins,
            labels=reviewer_labels,
        ).astype("string")

    if "num_games_owned" in df.columns:
        library_bins = [-float("inf"), 9, 49, 99, 499, float("inf")]
        library_labels = ["0-9", "10-49", "50-99", "100-499", "500+"]
        df["num_games_owned_band"] = pd.cut(
            df["num_games_owned"],
            bins=library_bins,
            labels=library_labels,
        ).astype("string")

    if "review_length_words" in df.columns:
        review_length_bins = [-float("inf"), 9, 49, 99, 249, float("inf")]
        review_length_labels = ["0-9", "10-49", "50-99", "100-249", "250+"]
        df["review_length_words_band"] = pd.cut(
            df["review_length_words"],
            bins=review_length_bins,
            labels=review_length_labels,
        ).astype("string")

    return df


def compute_numeric_agg_by_period(
    df: pd.DataFrame,
    period_col: str,
    value_col: str,
    prefix: str,
) -> pd.DataFrame:
    """Compute temporal summary stats for one numeric variable."""
    if period_col not in df.columns or value_col not in df.columns:
        return pd.DataFrame()

    temp = df[[period_col, value_col]].copy()
    temp[value_col] = pd.to_numeric(temp[value_col], errors="coerce")
    temp = temp.dropna(subset=[period_col])

    grouped = (
        temp.groupby(period_col, dropna=False)[value_col]
        .agg(
            count_non_null="count",
            mean="mean",
            median="median",
            std="std",
            min="min",
            p25=lambda s: s.quantile(0.25),
            p75=lambda s: s.quantile(0.75),
            p90=lambda s: s.quantile(0.90),
            max="max",
        )
        .reset_index()
        .sort_values(period_col)
        .reset_index(drop=True)
    )

    rename_map = {col: f"{prefix}_{col}" for col in grouped.columns if col != period_col}
    grouped = grouped.rename(columns=rename_map)

    for column in grouped.columns:
        if column != period_col:
            grouped[column] = pd.to_numeric(grouped[column], errors="coerce").round(4)

    return grouped


def compute_boolean_rate_by_period(
    df: pd.DataFrame,
    period_col: str,
    bool_col: str,
    prefix: str,
) -> pd.DataFrame:
    """Compute count and percentage of true values by period."""
    if period_col not in df.columns or bool_col not in df.columns:
        return pd.DataFrame()

    temp = df[[period_col, bool_col]].copy()
    temp = temp.dropna(subset=[period_col])

    grouped = (
        temp.groupby(period_col, dropna=False)
        .agg(
            review_count=(bool_col, "size"),
            true_count=(bool_col, lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
        .sort_values(period_col)
        .reset_index(drop=True)
    )
    grouped[f"{prefix}_percentage"] = grouped.apply(
        lambda row: safe_rate(row["true_count"], row["review_count"]),
        axis=1,
    )
    grouped = grouped.rename(
        columns={
            "review_count": f"{prefix}_review_count",
            "true_count": f"{prefix}_true_count",
        }
    )
    return grouped


def create_flat_crosstab(df: pd.DataFrame, row_col: str, col_col: str) -> pd.DataFrame:
    """Create a flat crosstab for export."""
    if row_col not in df.columns or col_col not in df.columns:
        return pd.DataFrame()

    cross = pd.crosstab(
        df[row_col].fillna("unknown"),
        df[col_col].fillna("unknown"),
        dropna=False,
    )
    flat = cross.reset_index()
    flat.columns.name = None
    return flat.sort_values(row_col).reset_index(drop=True)


# ============================================================================
# TEMPORAL TABLES
# ============================================================================

def create_temporal_coverage(df: pd.DataFrame, config: GameConfig) -> pd.DataFrame:
    """Create temporal coverage metadata."""
    start = df["review_created_datetime_utc"].min() if "review_created_datetime_utc" in df.columns else pd.NaT
    end = df["review_created_datetime_utc"].max() if "review_created_datetime_utc" in df.columns else pd.NaT

    days_covered = None
    if pd.notna(start) and pd.notna(end):
        days_covered = int((end - start).days) + 1

    rows = [
        {"metric": "app_id", "value": config.app_id},
        {"metric": "game_slug", "value": config.game_slug},
        {"metric": "game_title", "value": config.game_title},
        {"metric": "first_review_datetime_utc", "value": start},
        {"metric": "last_review_datetime_utc", "value": end},
        {"metric": "days_covered", "value": days_covered},
        {
            "metric": "months_covered",
            "value": int(df["review_created_date_month"].dropna().nunique())
            if "review_created_date_month" in df.columns else None,
        },
    ]
    return pd.DataFrame(rows)


def create_daily_review_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Create daily review volume table."""
    period_col = "review_created_date_day"
    grouped = (
        df.groupby(period_col, dropna=False)
        .agg(
            review_count=("recommendationid", "count"),
            positive_reviews=("is_positive", lambda s: int(s.fillna(False).sum())),
            negative_reviews=("is_negative", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
        .sort_values(period_col)
        .reset_index(drop=True)
    )
    grouped["positive_percentage"] = grouped.apply(
        lambda row: safe_rate(row["positive_reviews"], row["review_count"]), axis=1
    )
    grouped["negative_percentage"] = grouped.apply(
        lambda row: safe_rate(row["negative_reviews"], row["review_count"]), axis=1
    )
    grouped["cumulative_reviews"] = grouped["review_count"].cumsum()
    grouped["review_count_change_vs_previous_day"] = grouped["review_count"].diff()
    grouped["positive_percentage_change_vs_previous_day"] = grouped["positive_percentage"].diff()
    return grouped


def create_weekly_review_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Create weekly review volume table."""
    period_col = "review_created_date_week"
    grouped = (
        df.groupby(period_col, dropna=False)
        .agg(
            review_count=("recommendationid", "count"),
            positive_reviews=("is_positive", lambda s: int(s.fillna(False).sum())),
            negative_reviews=("is_negative", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
        .sort_values(period_col)
        .reset_index(drop=True)
    )
    grouped["positive_percentage"] = grouped.apply(
        lambda row: safe_rate(row["positive_reviews"], row["review_count"]), axis=1
    )
    grouped["negative_percentage"] = grouped.apply(
        lambda row: safe_rate(row["negative_reviews"], row["review_count"]), axis=1
    )
    grouped["cumulative_reviews"] = grouped["review_count"].cumsum()
    grouped["review_count_change_vs_previous_week"] = grouped["review_count"].diff()
    grouped["positive_percentage_change_vs_previous_week"] = grouped["positive_percentage"].diff()
    return grouped


def create_monthly_review_volume_extended(df: pd.DataFrame) -> pd.DataFrame:
    """Create extended monthly review volume table."""
    period_col = "review_created_date_month"
    grouped = (
        df.groupby(period_col, dropna=False)
        .agg(
            review_count=("recommendationid", "count"),
            positive_reviews=("is_positive", lambda s: int(s.fillna(False).sum())),
            negative_reviews=("is_negative", lambda s: int(s.fillna(False).sum())),
            unique_reviewers=("steamid", lambda s: int(s.dropna().nunique())),
        )
        .reset_index()
        .sort_values(period_col)
        .reset_index(drop=True)
    )
    grouped["positive_percentage"] = grouped.apply(
        lambda row: safe_rate(row["positive_reviews"], row["review_count"]), axis=1
    )
    grouped["negative_percentage"] = grouped.apply(
        lambda row: safe_rate(row["negative_reviews"], row["review_count"]), axis=1
    )
    grouped["cumulative_reviews"] = grouped["review_count"].cumsum()
    grouped["review_count_change_vs_previous_month"] = grouped["review_count"].diff()
    grouped["positive_percentage_change_vs_previous_month"] = grouped["positive_percentage"].diff()
    grouped["review_count_rolling_mean_3m"] = grouped["review_count"].rolling(3, min_periods=1).mean().round(4)
    grouped["positive_percentage_rolling_mean_3m"] = grouped["positive_percentage"].rolling(3, min_periods=1).mean().round(4)
    return grouped


def create_monthly_polarity_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly polarity trend table."""
    period_col = "review_created_date_month"
    grouped = (
        df.groupby(period_col, dropna=False)
        .agg(
            review_count=("recommendationid", "count"),
            positive_reviews=("is_positive", lambda s: int(s.fillna(False).sum())),
            negative_reviews=("is_negative", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
        .sort_values(period_col)
        .reset_index(drop=True)
    )
    grouped["positive_percentage"] = grouped.apply(
        lambda row: safe_rate(row["positive_reviews"], row["review_count"]), axis=1
    )
    grouped["negative_percentage"] = grouped.apply(
        lambda row: safe_rate(row["negative_reviews"], row["review_count"]), axis=1
    )
    grouped["positive_negative_ratio"] = grouped.apply(
        lambda row: round(row["positive_reviews"] / row["negative_reviews"], 4)
        if row["negative_reviews"] not in (0, None) else None,
        axis=1,
    )
    grouped["positive_percentage_change_vs_previous_month"] = grouped["positive_percentage"].diff()
    return grouped


def create_monthly_language_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly language trend table."""
    period_col = "review_created_date_month"
    temp = df[[period_col, "language", "is_positive"]].copy()
    temp["language"] = temp["language"].fillna("unknown")

    grouped = (
        temp.groupby([period_col, "language"], dropna=False)
        .agg(
            review_count=("language", "size"),
            positive_reviews=("is_positive", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
        .sort_values([period_col, "review_count", "language"], ascending=[True, False, True])
        .reset_index(drop=True)
    )

    monthly_totals = (
        grouped.groupby(period_col)["review_count"]
        .sum()
        .reset_index(name="month_total_reviews")
    )
    grouped = grouped.merge(monthly_totals, on=period_col, how="left")
    grouped["review_percentage_within_month"] = grouped.apply(
        lambda row: safe_rate(row["review_count"], row["month_total_reviews"]),
        axis=1,
    )
    grouped["positive_percentage_within_language_month"] = grouped.apply(
        lambda row: safe_rate(row["positive_reviews"], row["review_count"]),
        axis=1,
    )

    return grouped


def create_monthly_text_length_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly text-length trends."""
    period_col = "review_created_date_month"

    words = compute_numeric_agg_by_period(df, period_col, "review_length_words", "review_length_words")
    chars = compute_numeric_agg_by_period(df, period_col, "review_length_chars", "review_length_chars")
    lines = compute_numeric_agg_by_period(df, period_col, "review_length_lines", "review_length_lines")

    merged = words
    for other in [chars, lines]:
        if merged.empty:
            merged = other
        elif not other.empty:
            merged = merged.merge(other, on=period_col, how="outer")

    if merged.empty:
        return merged

    bands = (
        df.groupby([period_col, "review_length_words_band"], dropna=False)
        .size()
        .reset_index(name="band_count")
    )
    total_per_month = bands.groupby(period_col)["band_count"].sum().reset_index(name="month_total")
    bands = bands.merge(total_per_month, on=period_col, how="left")
    bands["band_percentage_within_month"] = bands.apply(
        lambda row: safe_rate(row["band_count"], row["month_total"]),
        axis=1,
    )

    pivot = bands.pivot_table(
        index=period_col,
        columns="review_length_words_band",
        values="band_percentage_within_month",
        aggfunc="first",
    ).reset_index()
    pivot.columns = [period_col] + [f"review_length_words_band_{col}_percentage" for col in pivot.columns[1:]]

    merged = merged.merge(pivot, on=period_col, how="left")
    return merged.sort_values(period_col).reset_index(drop=True)


def create_monthly_playtime_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly playtime trends."""
    period_col = "review_created_date_month"

    at_review = compute_numeric_agg_by_period(df, period_col, "playtime_at_review", "playtime_at_review")
    forever = compute_numeric_agg_by_period(df, period_col, "playtime_forever", "playtime_forever")
    post_review = compute_numeric_agg_by_period(df, period_col, "playtime_post_review", "playtime_post_review")

    played_after = compute_boolean_rate_by_period(df, period_col, "played_after_review", "played_after_review")
    recent_play = compute_boolean_rate_by_period(df, period_col, "recent_playtime_recorded", "recent_playtime_recorded")
    deck_use = compute_boolean_rate_by_period(df, period_col, "used_steam_deck_at_review", "used_steam_deck_at_review")

    merged = at_review
    for other in [forever, post_review, played_after, recent_play, deck_use]:
        if merged.empty:
            merged = other
        elif not other.empty:
            merged = merged.merge(other, on=period_col, how="outer")

    bands = create_flat_crosstab(df, period_col, "playtime_at_review_band")
    if not bands.empty:
        rename_map = {col: f"playtime_at_review_band_{col}" for col in bands.columns if col != period_col}
        bands = bands.rename(columns=rename_map)
        merged = merged.merge(bands, on=period_col, how="left")

    return merged.sort_values(period_col).reset_index(drop=True)


def create_monthly_reviewer_profile_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly reviewer-profile trends."""
    period_col = "review_created_date_month"

    num_reviews = compute_numeric_agg_by_period(df, period_col, "num_reviews", "num_reviews")
    num_games_owned = compute_numeric_agg_by_period(df, period_col, "num_games_owned", "num_games_owned")

    merged = num_reviews
    if not num_games_owned.empty:
        merged = merged.merge(num_games_owned, on=period_col, how="outer")

    reviews_band = create_flat_crosstab(df, period_col, "num_reviews_band")
    if not reviews_band.empty:
        rename_map = {col: f"num_reviews_band_{col}" for col in reviews_band.columns if col != period_col}
        reviews_band = reviews_band.rename(columns=rename_map)
        merged = merged.merge(reviews_band, on=period_col, how="left")

    library_band = create_flat_crosstab(df, period_col, "num_games_owned_band")
    if not library_band.empty:
        rename_map = {col: f"num_games_owned_band_{col}" for col in library_band.columns if col != period_col}
        library_band = library_band.rename(columns=rename_map)
        merged = merged.merge(library_band, on=period_col, how="left")

    return merged.sort_values(period_col).reset_index(drop=True)


def create_monthly_interaction_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly interaction trends."""
    period_col = "review_created_date_month"

    votes_up = compute_numeric_agg_by_period(df, period_col, "votes_up", "votes_up")
    votes_funny = compute_numeric_agg_by_period(df, period_col, "votes_funny", "votes_funny")
    comments = compute_numeric_agg_by_period(df, period_col, "comment_count", "comment_count")

    helpful_flag = compute_boolean_rate_by_period(df, period_col, "has_helpful_votes", "has_helpful_votes")
    funny_flag = compute_boolean_rate_by_period(df, period_col, "has_funny_votes", "has_funny_votes")
    comments_flag = compute_boolean_rate_by_period(df, period_col, "has_comments", "has_comments")

    merged = votes_up
    for other in [votes_funny, comments, helpful_flag, funny_flag, comments_flag]:
        if merged.empty:
            merged = other
        elif not other.empty:
            merged = merged.merge(other, on=period_col, how="outer")

    return merged.sort_values(period_col).reset_index(drop=True)


def create_review_update_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly review update metrics based on review creation month."""
    period_col = "review_created_date_month"

    updates = (
        df.groupby(period_col, dropna=False)
        .agg(
            review_count=("recommendationid", "count"),
            updated_reviews=("review_updated_after_creation", lambda s: int(s.fillna(False).sum())),
            mean_days_between_creation_and_update=("days_between_creation_and_update", "mean"),
            median_days_between_creation_and_update=("days_between_creation_and_update", "median"),
        )
        .reset_index()
        .sort_values(period_col)
        .reset_index(drop=True)
    )
    updates["updated_reviews_percentage"] = updates.apply(
        lambda row: safe_rate(row["updated_reviews"], row["review_count"]),
        axis=1,
    )
    updates["mean_days_between_creation_and_update"] = pd.to_numeric(
        updates["mean_days_between_creation_and_update"], errors="coerce"
    ).round(4)
    updates["median_days_between_creation_and_update"] = pd.to_numeric(
        updates["median_days_between_creation_and_update"], errors="coerce"
    ).round(4)

    return updates


def create_developer_response_timeline(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly developer response timeline without duplicated columns."""
    review_month_col = "review_created_date_month"
    response_month_col = "developer_responded_date_month"

    base = (
        df.groupby(review_month_col, dropna=False)
        .agg(
            review_count=("recommendationid", "count"),
            reviews_with_developer_response=("has_developer_response", lambda s: int(s.fillna(False).sum())),
            mean_days_to_developer_response=("days_to_developer_response", "mean"),
            median_days_to_developer_response=("days_to_developer_response", "median"),
        )
        .reset_index()
        .sort_values(review_month_col)
        .reset_index(drop=True)
    )

    base["developer_response_percentage"] = base.apply(
        lambda row: safe_rate(row["reviews_with_developer_response"], row["review_count"]),
        axis=1,
    )
    base["mean_days_to_developer_response"] = pd.to_numeric(
        base["mean_days_to_developer_response"], errors="coerce"
    ).round(4)
    base["median_days_to_developer_response"] = pd.to_numeric(
        base["median_days_to_developer_response"], errors="coerce"
    ).round(4)

    response_event_counts = (
        df[df["has_developer_response"].fillna(False)]
        .groupby(response_month_col, dropna=False)
        .size()
        .reset_index(name="developer_responses_created_in_month")
        .sort_values(response_month_col)
        .reset_index(drop=True)
    )

    if not response_event_counts.empty:
        response_event_counts = response_event_counts.rename(
            columns={response_month_col: review_month_col}
        )
        base = base.merge(response_event_counts, on=review_month_col, how="left")

    negative_subset = df[df["is_negative"].fillna(False)]
    negative_response = (
        negative_subset.groupby(review_month_col, dropna=False)
        .agg(
            negative_reviews=("recommendationid", "count"),
            negative_reviews_with_response=("has_developer_response", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
    )
    negative_response["negative_response_percentage"] = negative_response.apply(
        lambda row: safe_rate(row["negative_reviews_with_response"], row["negative_reviews"]),
        axis=1,
    )

    positive_subset = df[df["is_positive"].fillna(False)]
    positive_response = (
        positive_subset.groupby(review_month_col, dropna=False)
        .agg(
            positive_reviews=("recommendationid", "count"),
            positive_reviews_with_response=("has_developer_response", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
    )
    positive_response["positive_response_percentage"] = positive_response.apply(
        lambda row: safe_rate(row["positive_reviews_with_response"], row["positive_reviews"]),
        axis=1,
    )

    merged = base.merge(negative_response, on=review_month_col, how="left")
    merged = merged.merge(positive_response, on=review_month_col, how="left")

    return merged.sort_values(review_month_col).reset_index(drop=True)


def create_monthly_polarity_by_language(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly polarity by language table."""
    period_col = "review_created_date_month"
    temp = df[[period_col, "language", "is_positive", "is_negative"]].copy()
    temp["language"] = temp["language"].fillna("unknown")

    grouped = (
        temp.groupby([period_col, "language"], dropna=False)
        .agg(
            review_count=("language", "size"),
            positive_reviews=("is_positive", lambda s: int(s.fillna(False).sum())),
            negative_reviews=("is_negative", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
        .sort_values([period_col, "review_count", "language"], ascending=[True, False, True])
        .reset_index(drop=True)
    )
    grouped["positive_percentage"] = grouped.apply(
        lambda row: safe_rate(row["positive_reviews"], row["review_count"]),
        axis=1,
    )
    grouped["negative_percentage"] = grouped.apply(
        lambda row: safe_rate(row["negative_reviews"], row["review_count"]),
        axis=1,
    )

    return grouped


def create_monthly_polarity_by_playtime_band(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly polarity by playtime band table."""
    period_col = "review_created_date_month"
    band_col = "playtime_at_review_band"

    temp = df[[period_col, band_col, "is_positive", "is_negative"]].copy()
    grouped = (
        temp.groupby([period_col, band_col], dropna=False)
        .agg(
            review_count=(band_col, "size"),
            positive_reviews=("is_positive", lambda s: int(s.fillna(False).sum())),
            negative_reviews=("is_negative", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
        .sort_values([period_col, band_col], ascending=[True, True])
        .reset_index(drop=True)
    )
    grouped["positive_percentage"] = grouped.apply(
        lambda row: safe_rate(row["positive_reviews"], row["review_count"]),
        axis=1,
    )
    grouped["negative_percentage"] = grouped.apply(
        lambda row: safe_rate(row["negative_reviews"], row["review_count"]),
        axis=1,
    )
    return grouped


def create_peak_activity_summary(
    daily: pd.DataFrame,
    weekly: pd.DataFrame,
    monthly: pd.DataFrame,
) -> pd.DataFrame:
    """Create peak activity summary table."""
    rows: List[Dict[str, Any]] = []

    def add_peak(table: pd.DataFrame, period_col: str, label: str) -> None:
        if table.empty or "review_count" not in table.columns:
            return
        idx = table["review_count"].idxmax()
        peak_row = table.loc[idx]
        rows.append({"metric": f"peak_{label}_period", "value": peak_row[period_col]})
        rows.append({"metric": f"peak_{label}_review_count", "value": peak_row["review_count"]})

    add_peak(daily, "review_created_date_day", "day")
    add_peak(weekly, "review_created_date_week", "week")
    add_peak(monthly, "review_created_date_month", "month")

    return pd.DataFrame(rows)


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
    configure_logging(paths["analysis_log"])

    print(f"[INFO] Repository root: {repository_root}")
    print(f"[INFO] Game slug: {config.game_slug}")
    print(f"[INFO] Input CSV: {paths['input_csv']}")
    print(f"[INFO] Output tables: {paths['temporal_metrics_tables_dir']}")
    print(f"[INFO] Output summary JSON: {paths['summary_json']}")

    logging.info("Starting temporal metrics computation.")
    logging.info("Configuration file: %s", config_path)
    logging.info("Game title: %s", config.game_title)
    logging.info("App ID: %s", config.app_id)
    logging.info("Game slug: %s", config.game_slug)

    df = load_cleaned_reviews(paths["input_csv"])
    df = normalise_loaded_dataframe(df)
    df = add_time_group_columns(df)
    df = add_band_columns(df)

    logging.info("Rows loaded: %s", len(df))
    logging.info("Columns loaded: %s", len(df.columns))

    temporal_coverage = create_temporal_coverage(df, config)
    daily_review_volume = create_daily_review_volume(df)
    weekly_review_volume = create_weekly_review_volume(df)
    monthly_review_volume_extended = create_monthly_review_volume_extended(df)
    monthly_polarity_trends = create_monthly_polarity_trends(df)
    monthly_language_trends = create_monthly_language_trends(df)
    monthly_text_length_trends = create_monthly_text_length_trends(df)
    monthly_playtime_trends = create_monthly_playtime_trends(df)
    monthly_reviewer_profile_trends = create_monthly_reviewer_profile_trends(df)
    monthly_interaction_trends = create_monthly_interaction_trends(df)
    review_update_metrics = create_review_update_metrics(df)
    developer_response_timeline = create_developer_response_timeline(df)
    monthly_polarity_by_language = create_monthly_polarity_by_language(df)
    monthly_polarity_by_playtime_band = create_monthly_polarity_by_playtime_band(df)
    peak_activity_summary = create_peak_activity_summary(
        daily_review_volume,
        weekly_review_volume,
        monthly_review_volume_extended,
    )

    tables = {
        "temporal_coverage": temporal_coverage,
        "daily_review_volume": daily_review_volume,
        "weekly_review_volume": weekly_review_volume,
        "monthly_review_volume_extended": monthly_review_volume_extended,
        "monthly_polarity_trends": monthly_polarity_trends,
        "monthly_language_trends": monthly_language_trends,
        "monthly_text_length_trends": monthly_text_length_trends,
        "monthly_playtime_trends": monthly_playtime_trends,
        "monthly_reviewer_profile_trends": monthly_reviewer_profile_trends,
        "monthly_interaction_trends": monthly_interaction_trends,
        "review_update_metrics": review_update_metrics,
        "developer_response_timeline": developer_response_timeline,
        "monthly_polarity_by_language": monthly_polarity_by_language,
        "monthly_polarity_by_playtime_band": monthly_polarity_by_playtime_band,
        "peak_activity_summary": peak_activity_summary,
    }

    for table_name, table_df in tables.items():
        output_path = paths["temporal_metrics_tables_dir"] / f"{config.game_slug}_{table_name}.csv"
        export_table(table_df, output_path)
        logging.info("Exported table: %s", output_path.name)

    summary_payload = {
        "app_id": config.app_id,
        "game_slug": config.game_slug,
        "game_title": config.game_title,
        "generated_at_utc": pd.Timestamp.utcnow().isoformat(),
        "tables": {
            table_name: dataframe_to_json_records(table_df)
            for table_name, table_df in tables.items()
        },
    }

    with paths["summary_json"].open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, ensure_ascii=False, indent=2)

    logging.info("Summary JSON written to: %s", paths["summary_json"])
    logging.info("Temporal metrics computation complete.")
    print("[INFO] Temporal metrics computation complete.")


if __name__ == "__main__":
    main()