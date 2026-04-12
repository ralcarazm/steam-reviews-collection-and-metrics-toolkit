#!/usr/bin/env python3
"""
compute_basic_metrics.py

Generic Steam review basic-metrics script for multiple games.

This script:
- reads a per-game JSON configuration file;
- loads the cleaned review dataset for one selected game;
- computes descriptive metrics and selected cross-tabulations;
- exports metrics tables as CSV files;
- exports a JSON summary of the main outputs;
- writes an analysis log.

Usage examples:

    python scripts/03_analysis/compute_basic_metrics.py \
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
        description="Compute basic descriptive metrics for one prepared Steam review dataset."
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
    scripts/03_analysis/compute_basic_metrics.py
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
        "basic_metrics_tables_dir": results_root / "tables" / "basic_metrics",
    }

    paths["input_csv"] = paths["cleaned_dir"] / f"{game_slug}_reviews_cleaned.csv"
    paths["summary_json"] = paths["metrics_dir"] / f"{game_slug}_basic_metrics_summary.json"
    paths["analysis_log"] = paths["metrics_dir"] / f"{game_slug}_basic_metrics.log"

    return paths


def ensure_directories(paths: Dict[str, Path]) -> None:
    """Create required output directories."""
    for key in ["metrics_dir", "tables_dir", "basic_metrics_tables_dir"]:
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

    df = restore_boolean_columns(df, boolean_columns)
    df = restore_numeric_columns(df, numeric_columns)

    for column in ["language", "game_slug", "game_title", "review_created_year_month"]:
        if column in df.columns:
            df[column] = df[column].astype("string")

    return df


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def safe_bool_sum(series: pd.Series) -> int:
    """Count True values in a nullable boolean series."""
    return int(series.fillna(False).sum())


def safe_rate(numerator: float, denominator: float) -> float | None:
    """Return a percentage safely."""
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 4)


def to_serialisable(value: Any) -> Any:
    """Convert pandas/numpy values to JSON-safe Python values."""
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
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


def compute_numeric_summary(df: pd.DataFrame, column: str) -> Dict[str, Any]:
    """Compute a rich summary for one numeric column."""
    if column not in df.columns:
        return {"variable": column}

    series = pd.to_numeric(df[column], errors="coerce")
    non_null = series.dropna()

    if non_null.empty:
        return {
            "variable": column,
            "count_non_null": 0,
            "count_null": int(series.isna().sum()),
            "count_zero": None,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "p10": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "max": None,
            "sum": None,
        }

    return {
        "variable": column,
        "count_non_null": int(non_null.count()),
        "count_null": int(series.isna().sum()),
        "count_zero": int((non_null == 0).sum()),
        "mean": round(float(non_null.mean()), 4),
        "median": round(float(non_null.median()), 4),
        "std": round(float(non_null.std()), 4) if non_null.count() > 1 else None,
        "min": round(float(non_null.min()), 4),
        "p10": round(float(non_null.quantile(0.10)), 4),
        "p25": round(float(non_null.quantile(0.25)), 4),
        "p50": round(float(non_null.quantile(0.50)), 4),
        "p75": round(float(non_null.quantile(0.75)), 4),
        "p90": round(float(non_null.quantile(0.90)), 4),
        "p95": round(float(non_null.quantile(0.95)), 4),
        "max": round(float(non_null.max()), 4),
        "sum": round(float(non_null.sum()), 4),
    }


def add_band_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add categorical bands useful for cross-tabulations."""
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


# ============================================================================
# METRICS TABLES
# ============================================================================

def create_dataset_overview(df: pd.DataFrame, config: GameConfig) -> pd.DataFrame:
    """Create general dataset overview metrics."""
    total_reviews = len(df)
    unique_review_ids = df["recommendationid"].nunique(dropna=True) if "recommendationid" in df.columns else None
    unique_reviewers = df["steamid"].nunique(dropna=True) if "steamid" in df.columns else None
    text_reviews = safe_bool_sum(df["has_text_review"]) if "has_text_review" in df.columns else None
    languages_detected = df["language"].dropna().nunique() if "language" in df.columns else None

    rows = [
        {"metric": "app_id", "value": config.app_id},
        {"metric": "game_slug", "value": config.game_slug},
        {"metric": "game_title", "value": config.game_title},
        {"metric": "total_reviews", "value": total_reviews},
        {"metric": "unique_recommendation_ids", "value": unique_review_ids},
        {"metric": "unique_reviewers", "value": unique_reviewers},
        {"metric": "reviews_with_text", "value": text_reviews},
        {"metric": "languages_detected", "value": languages_detected},
    ]

    return pd.DataFrame(rows)


def create_polarity_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Create review polarity summary."""
    total_reviews = len(df)
    positive_reviews = safe_bool_sum(df["is_positive"])
    negative_reviews = safe_bool_sum(df["is_negative"])

    rows = [
        {"metric": "total_reviews", "value": total_reviews},
        {"metric": "positive_reviews", "value": positive_reviews},
        {"metric": "negative_reviews", "value": negative_reviews},
        {"metric": "positive_percentage", "value": safe_rate(positive_reviews, total_reviews)},
        {"metric": "negative_percentage", "value": safe_rate(negative_reviews, total_reviews)},
        {
            "metric": "positive_negative_ratio",
            "value": round(positive_reviews / negative_reviews, 4) if negative_reviews not in (0, None) else None,
        },
    ]

    return pd.DataFrame(rows)


def create_language_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Create language distribution table."""
    total_reviews = len(df)
    language_counts = (
        df["language"]
        .fillna("unknown")
        .value_counts(dropna=False)
        .rename_axis("language")
        .reset_index(name="review_count")
    )
    language_counts["review_percentage"] = language_counts["review_count"].apply(
        lambda x: safe_rate(x, total_reviews)
    )
    return language_counts


def create_numeric_summary_table(df: pd.DataFrame, variables: List[str]) -> pd.DataFrame:
    """Create a stacked numeric summary table for multiple variables."""
    rows = [compute_numeric_summary(df, variable) for variable in variables]
    return pd.DataFrame(rows)


def create_purchase_and_access_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Create summary of purchase and access conditions."""
    total_reviews = len(df)

    rows = []
    for metric_name, column in [
        ("steam_purchase_true", "is_steam_purchase"),
        ("free_copy_true", "is_free_copy"),
        ("early_access_review_true", "is_early_access_review"),
        ("primarily_steam_deck_true", "is_primarily_steam_deck"),
        ("developer_response_true", "has_developer_response"),
        ("played_after_review_true", "played_after_review"),
        ("review_updated_after_creation_true", "review_updated_after_creation"),
        ("recent_playtime_recorded_true", "recent_playtime_recorded"),
        ("used_steam_deck_at_review_true", "used_steam_deck_at_review"),
    ]:
        if column in df.columns:
            count_true = safe_bool_sum(df[column])
            rows.append(
                {
                    "metric": metric_name,
                    "count_true": count_true,
                    "percentage_true": safe_rate(count_true, total_reviews),
                }
            )

    return pd.DataFrame(rows)


def create_missingness_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Create column-wise missingness summary."""
    rows = []
    total_rows = len(df)

    for column in df.columns:
        null_count = int(df[column].isna().sum())
        non_null_count = int(total_rows - null_count)
        rows.append(
            {
                "column": column,
                "row_count": total_rows,
                "non_null_count": non_null_count,
                "null_count": null_count,
                "null_percentage": safe_rate(null_count, total_rows),
            }
        )

    return pd.DataFrame(rows).sort_values(
        by=["null_count", "column"],
        ascending=[False, True],
    ).reset_index(drop=True)


def create_concentration_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Create simple concentration metrics for selected variables."""
    rows = []

    for column in ["votes_up", "votes_funny", "comment_count", "playtime_forever", "review_length_words"]:
        if column not in df.columns:
            continue

        series = pd.to_numeric(df[column], errors="coerce").dropna()
        if series.empty:
            continue

        sorted_desc = series.sort_values(ascending=False).reset_index(drop=True)
        total_sum = float(sorted_desc.sum())

        def share_of_top(fraction: float) -> float | None:
            if total_sum == 0 or len(sorted_desc) == 0:
                return None
            n = max(1, math.ceil(len(sorted_desc) * fraction))
            return round(float(sorted_desc.iloc[:n].sum() / total_sum * 100), 4)

        rows.append(
            {
                "variable": column,
                "sum_total": round(total_sum, 4),
                "share_top_1_percent": share_of_top(0.01),
                "share_top_5_percent": share_of_top(0.05),
                "share_top_10_percent": share_of_top(0.10),
            }
        )

    return pd.DataFrame(rows)


def create_cross_tab(
    df: pd.DataFrame,
    row_var: str,
    col_var: str,
    value_name: str = "count",
) -> pd.DataFrame:
    """Create a cross-tabulation as a flat table."""
    if row_var not in df.columns or col_var not in df.columns:
        return pd.DataFrame()

    cross = pd.crosstab(
        df[row_var].fillna("unknown"),
        df[col_var].fillna("unknown"),
        dropna=False,
    )

    flat = cross.reset_index()
    flat.columns.name = None

    total_count = int(cross.to_numpy().sum())
    if total_count > 0:
        for column in flat.columns[1:]:
            percentage_column = f"{column}_percentage_of_total"
            flat[percentage_column] = flat[column].apply(lambda x: safe_rate(x, total_count))

    return flat


def create_monthly_review_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly review volume and polarity table."""
    if "review_created_year_month" not in df.columns:
        return pd.DataFrame()

    monthly = (
        df.groupby("review_created_year_month", dropna=False)
        .agg(
            review_count=("recommendationid", "count"),
            positive_reviews=("is_positive", lambda s: int(s.fillna(False).sum())),
            negative_reviews=("is_negative", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
        .sort_values("review_created_year_month")
        .reset_index(drop=True)
    )

    monthly["positive_percentage"] = monthly.apply(
        lambda row: safe_rate(row["positive_reviews"], row["review_count"]),
        axis=1,
    )
    monthly["negative_percentage"] = monthly.apply(
        lambda row: safe_rate(row["negative_reviews"], row["review_count"]),
        axis=1,
    )

    return monthly


# ============================================================================
# SUMMARY JSON
# ============================================================================

def dataframe_to_json_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert a dataframe to JSON-safe records."""
    records = []
    for record in df.to_dict(orient="records"):
        records.append({key: to_serialisable(value) for key, value in record.items()})
    return records


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
    print(f"[INFO] Output tables: {paths['basic_metrics_tables_dir']}")
    print(f"[INFO] Output summary JSON: {paths['summary_json']}")

    logging.info("Starting basic metrics computation.")
    logging.info("Configuration file: %s", config_path)
    logging.info("Game title: %s", config.game_title)
    logging.info("App ID: %s", config.app_id)
    logging.info("Game slug: %s", config.game_slug)

    df = load_cleaned_reviews(paths["input_csv"])
    df = normalise_loaded_dataframe(df)
    df = add_band_columns(df)

    logging.info("Rows loaded: %s", len(df))
    logging.info("Columns loaded: %s", len(df.columns))

    dataset_overview = create_dataset_overview(df, config)
    polarity_summary = create_polarity_summary(df)
    language_distribution = create_language_distribution(df)

    reviewer_profile_summary = create_numeric_summary_table(
        df,
        variables=["num_games_owned", "num_reviews"],
    )

    playtime_summary = create_numeric_summary_table(
        df,
        variables=[
            "playtime_forever",
            "playtime_last_two_weeks",
            "playtime_at_review",
            "deck_playtime_at_review",
            "playtime_post_review",
        ],
    )

    interaction_summary = create_numeric_summary_table(
        df,
        variables=["votes_up", "votes_funny", "comment_count"],
    )

    text_summary = create_numeric_summary_table(
        df,
        variables=[
            "review_length_chars",
            "review_length_chars_no_spaces",
            "review_length_words",
            "review_length_lines",
        ],
    )

    temporal_interval_summary = create_numeric_summary_table(
        df,
        variables=[
            "days_between_creation_and_update",
            "days_between_review_and_last_played",
            "days_to_developer_response",
        ],
    )

    purchase_and_access_summary = create_purchase_and_access_summary(df)
    missingness_summary = create_missingness_summary(df)
    concentration_summary = create_concentration_summary(df)

    cross_tab_polarity_by_language = create_cross_tab(df, "language", "is_positive")
    cross_tab_polarity_by_playtime_band = create_cross_tab(df, "playtime_at_review_band", "is_positive")
    cross_tab_polarity_by_reviewer_activity_band = create_cross_tab(df, "num_reviews_band", "is_positive")
    cross_tab_polarity_by_library_size_band = create_cross_tab(df, "num_games_owned_band", "is_positive")

    monthly_review_volume = create_monthly_review_volume(df)

    tables = {
        "dataset_overview": dataset_overview,
        "polarity_summary": polarity_summary,
        "language_distribution": language_distribution,
        "reviewer_profile_summary": reviewer_profile_summary,
        "playtime_summary": playtime_summary,
        "interaction_summary": interaction_summary,
        "text_summary": text_summary,
        "temporal_interval_summary": temporal_interval_summary,
        "purchase_and_access_summary": purchase_and_access_summary,
        "missingness_summary": missingness_summary,
        "concentration_summary": concentration_summary,
        "cross_tab_polarity_by_language": cross_tab_polarity_by_language,
        "cross_tab_polarity_by_playtime_band": cross_tab_polarity_by_playtime_band,
        "cross_tab_polarity_by_reviewer_activity_band": cross_tab_polarity_by_reviewer_activity_band,
        "cross_tab_polarity_by_library_size_band": cross_tab_polarity_by_library_size_band,
        "monthly_review_volume": monthly_review_volume,
    }

    for table_name, table_df in tables.items():
        output_path = paths["basic_metrics_tables_dir"] / f"{config.game_slug}_{table_name}.csv"
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
    logging.info("Basic metrics computation complete.")
    print("[INFO] Basic metrics computation complete.")


if __name__ == "__main__":
    main()