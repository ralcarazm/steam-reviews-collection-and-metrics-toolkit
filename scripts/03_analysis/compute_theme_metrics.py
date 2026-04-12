#!/usr/bin/env python3
"""
compute_theme_metrics.py

Generic Steam review theme-metrics script for multiple games.

This script:
- reads a per-game JSON configuration file;
- loads the cleaned review dataset for one selected game;
- filters the corpus to one target language;
- applies a dictionary-based thematic matching approach;
- exports a review-level enriched CSV;
- exports aggregate theme tables as CSV files;
- exports a JSON summary of the main outputs;
- writes an analysis log.

Usage example:

    python scripts/03_analysis/compute_theme_metrics.py \
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
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set

import pandas as pd


# ============================================================================
# CONSTANTS
# ============================================================================

TOKEN_PATTERN = re.compile(r"\b[\w'-]+\b", flags=re.UNICODE)

ENGLISH_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "to", "of", "in",
    "on", "at", "for", "from", "with", "without", "by", "is", "are", "was", "were",
    "be", "been", "being", "it", "its", "this", "that", "these", "those", "as",
    "i", "you", "he", "she", "we", "they", "them", "my", "your", "his", "her",
    "our", "their", "me", "him", "us", "do", "does", "did", "not", "no", "yes",
    "so", "very", "just", "can", "could", "would", "should", "will", "really"
}


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class GameConfig:
    """Configuration values for one theme-analysis run."""
    app_id: int
    game_slug: str
    game_title: str
    dictionary_path: str
    target_language: str = "english"
    min_token_length: int = 2
    remove_stopwords: bool = True
    export_review_level_enriched_csv: bool = True
    count_multiple_hits_per_theme: bool = True


# ============================================================================
# ARGUMENT PARSING
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compute theme metrics for one prepared Steam review dataset."
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

    theme_cfg = raw_config.get("theme_metrics", {})
    dictionary_path = theme_cfg.get(
        "dictionary_path",
        "resources/dictionaries/themes/general_game_themes.json",
    )

    return GameConfig(
        app_id=int(raw_config["app_id"]),
        game_slug=str(raw_config["game_slug"]).strip(),
        game_title=str(raw_config["game_title"]).strip(),
        dictionary_path=str(dictionary_path).strip(),
        target_language=str(theme_cfg.get("target_language", "english")).strip().lower(),
        min_token_length=int(theme_cfg.get("min_token_length", 2)),
        remove_stopwords=bool(theme_cfg.get("remove_stopwords", True)),
        export_review_level_enriched_csv=bool(
            theme_cfg.get("export_review_level_enriched_csv", True)
        ),
        count_multiple_hits_per_theme=bool(
            theme_cfg.get("count_multiple_hits_per_theme", True)
        ),
    )


# ============================================================================
# PATH MANAGEMENT
# ============================================================================

def get_repository_root() -> Path:
    """
    Resolve the repository root assuming this file lives at:
    scripts/03_analysis/compute_theme_metrics.py
    """
    return Path(__file__).resolve().parents[2]


def build_paths(repository_root: Path, config: GameConfig) -> Dict[str, Path]:
    """Build all required input and output paths."""
    processed_root = repository_root / "data" / "processed" / "steam_reviews" / config.game_slug
    results_root = repository_root / "results" / config.game_slug

    paths = {
        "processed_root": processed_root,
        "cleaned_dir": processed_root / "cleaned",
        "enriched_dir": processed_root / "enriched",
        "metrics_dir": processed_root / "metrics",
        "results_root": results_root,
        "tables_dir": results_root / "tables",
        "theme_metrics_tables_dir": results_root / "tables" / "theme_metrics",
    }

    paths["input_csv"] = paths["cleaned_dir"] / f"{config.game_slug}_reviews_cleaned.csv"
    paths["dictionary_path"] = repository_root / config.dictionary_path
    paths["summary_json"] = paths["metrics_dir"] / f"{config.game_slug}_theme_metrics_summary.json"
    paths["analysis_log"] = paths["metrics_dir"] / f"{config.game_slug}_theme_metrics.log"
    paths["review_level_enriched_csv"] = (
        paths["enriched_dir"] / f"{config.game_slug}_{config.target_language}_theme_enriched.csv"
    )

    return paths


def ensure_directories(paths: Dict[str, Path]) -> None:
    """Create required output directories."""
    for key in ["enriched_dir", "metrics_dir", "tables_dir", "theme_metrics_tables_dir"]:
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


def add_playtime_band_column(df: pd.DataFrame) -> pd.DataFrame:
    """Recreate playtime_at_review_band if missing."""
    df = df.copy()

    if "playtime_at_review_band" not in df.columns and "playtime_at_review" in df.columns:
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

    return df


def normalise_loaded_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Restore expected types from the cleaned CSV."""
    boolean_columns = ["is_positive", "is_negative", "has_text_review"]
    numeric_columns = ["review_length_words", "review_length_chars", "playtime_at_review"]

    df = restore_boolean_columns(df, boolean_columns)
    df = restore_numeric_columns(df, numeric_columns)
    df = add_playtime_band_column(df)

    for column in ["language", "review", "playtime_at_review_band", "review_created_year_month"]:
        if column in df.columns:
            df[column] = df[column].astype("string")

    return df


# ============================================================================
# DICTIONARY LOADING
# ============================================================================

def load_theme_dictionary(dictionary_path: Path) -> Dict[str, Set[str]]:
    """Load the theme dictionary as theme -> set(terms)."""
    if not dictionary_path.exists():
        raise FileNotFoundError(f"Theme dictionary not found: {dictionary_path}")

    with dictionary_path.open("r", encoding="utf-8") as handle:
        raw_dictionary = json.load(handle)

    if not isinstance(raw_dictionary, dict) or not raw_dictionary:
        raise ValueError("Theme dictionary must be a non-empty JSON object.")

    dictionary: Dict[str, Set[str]] = {}
    for theme, terms in raw_dictionary.items():
        if not isinstance(theme, str) or not theme.strip():
            continue
        if not isinstance(terms, list):
            continue

        cleaned_terms = {str(term).strip().lower() for term in terms if str(term).strip()}
        if cleaned_terms:
            dictionary[theme.strip().lower()] = cleaned_terms

    if not dictionary:
        raise ValueError("No valid themes were found in the dictionary file.")

    return dictionary


# ============================================================================
# TEXT PROCESSING
# ============================================================================

def tokenise_text(
    text: str,
    min_token_length: int,
    remove_stopwords: bool,
) -> List[str]:
    """Tokenise text into a cleaned token list."""
    tokens = TOKEN_PATTERN.findall(text.lower())
    cleaned_tokens: List[str] = []

    for token in tokens:
        if token.isdigit():
            continue
        if len(token) < min_token_length:
            continue
        if remove_stopwords and token in ENGLISH_STOPWORDS:
            continue
        cleaned_tokens.append(token)

    return cleaned_tokens


def prepare_theme_subset(
    df: pd.DataFrame,
    config: GameConfig,
) -> pd.DataFrame:
    """Filter to target language and create token lists."""
    temp = df.copy()

    temp["language"] = temp["language"].fillna("unknown").astype("string").str.lower()
    temp["review"] = temp["review"].fillna(pd.NA).astype("string")

    temp = temp[temp["language"] == config.target_language].copy()
    temp = temp[temp["review"].notna()].copy()
    temp["review"] = temp["review"].str.strip()
    temp = temp[temp["review"] != ""].copy()

    temp["tokens"] = temp["review"].map(
        lambda text: tokenise_text(
            text=str(text),
            min_token_length=config.min_token_length,
            remove_stopwords=config.remove_stopwords,
        )
    )
    temp["token_count_for_theme_analysis"] = temp["tokens"].map(len)
    temp = temp[temp["token_count_for_theme_analysis"] > 0].copy()

    return temp.reset_index(drop=True)


# ============================================================================
# THEME MATCHING
# ============================================================================

def match_theme_terms_in_tokens(
    tokens: List[str],
    theme_dictionary: Dict[str, Set[str]],
    count_multiple_hits_per_theme: bool,
) -> Dict[str, Any]:
    """Match theme terms in one token list."""
    token_counter = Counter(tokens)
    token_set = set(tokens)

    result: Dict[str, Any] = {}
    total_matches = 0

    for theme, terms in theme_dictionary.items():
        single_word_terms = {term for term in terms if " " not in term}
        multi_word_terms = {term for term in terms if " " in term}

        theme_count = 0
        matched_terms: List[str] = []

        for term in single_word_terms:
            if term in token_set:
                matched_terms.append(term)
                if count_multiple_hits_per_theme:
                    theme_count += token_counter[term]
                else:
                    theme_count += 1

        token_string = " ".join(tokens)
        for term in multi_word_terms:
            occurrences = token_string.count(term)
            if occurrences > 0:
                matched_terms.append(term)
                if count_multiple_hits_per_theme:
                    theme_count += occurrences
                else:
                    theme_count += 1

        result[f"{theme}_count"] = theme_count
        result[f"{theme}_present"] = theme_count > 0
        result[f"{theme}_matched_terms"] = "; ".join(sorted(set(matched_terms))) if matched_terms else ""

        total_matches += theme_count

    result["theme_match_count_total"] = total_matches
    result["themes_present_count"] = sum(
        1 for theme in theme_dictionary if result[f"{theme}_present"]
    )

    return result


def enrich_reviews_with_themes(
    df_text: pd.DataFrame,
    theme_dictionary: Dict[str, Set[str]],
    count_multiple_hits_per_theme: bool,
) -> pd.DataFrame:
    """Add review-level theme counts and presence flags."""
    rows = []

    for _, row in df_text.iterrows():
        tokens = row["tokens"]
        match_result = match_theme_terms_in_tokens(
            tokens=tokens,
            theme_dictionary=theme_dictionary,
            count_multiple_hits_per_theme=count_multiple_hits_per_theme,
        )

        enriched_row = dict(row)
        enriched_row.update(match_result)

        for theme in theme_dictionary:
            enriched_row[f"{theme}_per_100_tokens"] = (
                round((match_result[f"{theme}_count"] / len(tokens)) * 100, 6)
                if len(tokens) > 0 else None
            )

        rows.append(enriched_row)

    return pd.DataFrame(rows)


# ============================================================================
# AGGREGATE TABLES
# ============================================================================

def create_theme_corpus_overview(
    df_raw: pd.DataFrame,
    df_text: pd.DataFrame,
    df_enriched: pd.DataFrame,
    config: GameConfig,
    theme_dictionary: Dict[str, Set[str]],
) -> pd.DataFrame:
    """Create corpus overview for theme analysis."""
    rows = [
        {"metric": "app_id", "value": config.app_id},
        {"metric": "game_slug", "value": config.game_slug},
        {"metric": "game_title", "value": config.game_title},
        {"metric": "target_language", "value": config.target_language},
        {"metric": "rows_in_cleaned_dataset", "value": int(len(df_raw))},
        {
            "metric": "rows_in_target_language",
            "value": int(
                len(
                    df_raw[
                        df_raw["language"].fillna("unknown").astype("string").str.lower()
                        == config.target_language
                    ]
                )
            ),
        },
        {"metric": "reviews_with_usable_text", "value": int(len(df_text))},
        {"metric": "reviews_with_any_theme_match", "value": int((df_enriched["theme_match_count_total"] > 0).sum())},
        {"metric": "total_tokens_analysed", "value": int(df_enriched["token_count_for_theme_analysis"].sum())},
        {"metric": "total_theme_matches", "value": int(df_enriched["theme_match_count_total"].sum())},
    ]

    for theme in theme_dictionary:
        rows.append(
            {
                "metric": f"reviews_with_{theme}_signal",
                "value": int(df_enriched[f"{theme}_present"].sum()),
            }
        )

    return pd.DataFrame(rows)


def create_theme_distribution_summary(
    df_enriched: pd.DataFrame,
    theme_dictionary: Dict[str, Set[str]],
) -> pd.DataFrame:
    """Create global theme distribution summary."""
    total_tokens = df_enriched["token_count_for_theme_analysis"].sum()
    total_reviews = len(df_enriched)

    rows = []
    for theme in theme_dictionary:
        total_hits = int(df_enriched[f"{theme}_count"].sum())
        reviews_with_theme = int(df_enriched[f"{theme}_present"].sum())

        rows.append(
            {
                "theme": theme,
                "total_hits": total_hits,
                "hits_per_1000_tokens": round((total_hits / total_tokens) * 1000, 6) if total_tokens > 0 else None,
                "reviews_with_theme": reviews_with_theme,
                "review_share_with_theme": round((reviews_with_theme / total_reviews) * 100, 4) if total_reviews > 0 else None,
                "mean_count_per_review": round(float(df_enriched[f"{theme}_count"].mean()), 6),
                "mean_per_100_tokens": round(float(df_enriched[f"{theme}_per_100_tokens"].mean()), 6),
            }
        )

    return pd.DataFrame(rows)


def create_theme_by_polarity(
    df_enriched: pd.DataFrame,
    theme_dictionary: Dict[str, Set[str]],
) -> pd.DataFrame:
    """Create theme summary by polarity."""
    segments = [("overall", df_enriched)]

    if "is_positive" in df_enriched.columns:
        segments.append(("positive", df_enriched[df_enriched["is_positive"].fillna(False)]))
    if "is_negative" in df_enriched.columns:
        segments.append(("negative", df_enriched[df_enriched["is_negative"].fillna(False)]))

    rows = []
    for segment_name, subset in segments:
        row = {
            "segment": segment_name,
            "review_count": int(len(subset)),
            "total_tokens": int(subset["token_count_for_theme_analysis"].sum()) if len(subset) > 0 else 0,
            "theme_match_count_total": int(subset["theme_match_count_total"].sum()) if len(subset) > 0 else 0,
        }

        for theme in theme_dictionary:
            row[f"{theme}_mean_count"] = round(float(subset[f"{theme}_count"].mean()), 6) if len(subset) > 0 else None
            row[f"{theme}_mean_per_100_tokens"] = round(float(subset[f"{theme}_per_100_tokens"].mean()), 6) if len(subset) > 0 else None
            row[f"{theme}_review_share"] = round(float(subset[f"{theme}_present"].mean() * 100), 4) if len(subset) > 0 else None

        rows.append(row)

    return pd.DataFrame(rows)


def create_theme_by_playtime_band(
    df_enriched: pd.DataFrame,
    theme_dictionary: Dict[str, Set[str]],
) -> pd.DataFrame:
    """Create theme summary by playtime band."""
    if "playtime_at_review_band" not in df_enriched.columns:
        return pd.DataFrame()

    temp = df_enriched.dropna(subset=["playtime_at_review_band"]).copy()
    if temp.empty:
        return pd.DataFrame()

    rows = []
    for band, subset in temp.groupby("playtime_at_review_band", dropna=False):
        row = {
            "playtime_at_review_band": band,
            "review_count": int(len(subset)),
            "total_tokens": int(subset["token_count_for_theme_analysis"].sum()),
            "theme_match_count_total": int(subset["theme_match_count_total"].sum()),
        }

        for theme in theme_dictionary:
            row[f"{theme}_mean_count"] = round(float(subset[f"{theme}_count"].mean()), 6)
            row[f"{theme}_mean_per_100_tokens"] = round(float(subset[f"{theme}_per_100_tokens"].mean()), 6)
            row[f"{theme}_review_share"] = round(float(subset[f"{theme}_present"].mean() * 100), 4)

        rows.append(row)

    return pd.DataFrame(rows).sort_values("playtime_at_review_band").reset_index(drop=True)


def create_theme_by_month(
    df_enriched: pd.DataFrame,
    theme_dictionary: Dict[str, Set[str]],
) -> pd.DataFrame:
    """Create monthly theme summary."""
    if "review_created_year_month" not in df_enriched.columns:
        return pd.DataFrame()

    rows = []
    for month, subset in df_enriched.groupby("review_created_year_month", dropna=False):
        row = {
            "review_created_year_month": month,
            "review_count": int(len(subset)),
            "total_tokens": int(subset["token_count_for_theme_analysis"].sum()),
            "theme_match_count_total": int(subset["theme_match_count_total"].sum()),
        }

        for theme in theme_dictionary:
            row[f"{theme}_mean_count"] = round(float(subset[f"{theme}_count"].mean()), 6)
            row[f"{theme}_mean_per_100_tokens"] = round(float(subset[f"{theme}_per_100_tokens"].mean()), 6)
            row[f"{theme}_review_share"] = round(float(subset[f"{theme}_present"].mean() * 100), 4)

        rows.append(row)

    return pd.DataFrame(rows).sort_values("review_created_year_month").reset_index(drop=True)


def create_theme_top_terms_by_theme(
    df_enriched: pd.DataFrame,
    theme_dictionary: Dict[str, Set[str]],
) -> pd.DataFrame:
    """Create top term table for each theme."""
    counters: Dict[str, Counter] = {theme: Counter() for theme in theme_dictionary}

    for _, row in df_enriched.iterrows():
        for theme in theme_dictionary:
            matched_terms_text = row.get(f"{theme}_matched_terms", "")
            if not matched_terms_text:
                continue
            for term in [term.strip() for term in matched_terms_text.split(";") if term.strip()]:
                counters[theme][term] += 1

    rows = []
    for theme in theme_dictionary:
        total_hits = sum(counters[theme].values())
        for rank, (term, frequency) in enumerate(counters[theme].most_common(), start=1):
            rows.append(
                {
                    "theme": theme,
                    "rank": rank,
                    "term": term,
                    "frequency": frequency,
                    "relative_frequency_per_1000_theme_hits": round((frequency / total_hits) * 1000, 6)
                    if total_hits > 0 else None,
                }
            )

    return pd.DataFrame(rows).sort_values(["theme", "rank"]).reset_index(drop=True)


# ============================================================================
# JSON HELPERS
# ============================================================================

def to_serialisable(value: Any) -> Any:
    """Convert pandas values to JSON-safe Python values."""
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


def dataframe_to_json_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert dataframe to JSON-safe records."""
    records = []
    for record in df.to_dict(orient="records"):
        records.append({key: to_serialisable(value) for key, value in record.items()})
    return records


def export_table(df: pd.DataFrame, output_path: Path) -> None:
    """Export one dataframe to CSV."""
    df.to_csv(output_path, index=False, encoding="utf-8-sig")


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    """Main entry point."""
    args = parse_arguments()

    config_path = Path(args.config).resolve()
    config = load_game_config(config_path)

    repository_root = get_repository_root()
    paths = build_paths(repository_root, config)
    ensure_directories(paths)
    configure_logging(paths["analysis_log"])

    print(f"[INFO] Loading configuration: {config_path}")
    print(f"[INFO] Repository root: {repository_root}")
    print(f"[INFO] Game slug: {config.game_slug}")
    print(f"[INFO] Input CSV: {paths['input_csv']}")
    print(f"[INFO] Theme dictionary: {paths['dictionary_path']}")
    print(f"[INFO] Output tables: {paths['theme_metrics_tables_dir']}")
    print(f"[INFO] Summary JSON: {paths['summary_json']}")

    logging.info("Starting theme metrics computation.")
    logging.info("Configuration file: %s", config_path)
    logging.info("Game title: %s", config.game_title)
    logging.info("App ID: %s", config.app_id)
    logging.info("Game slug: %s", config.game_slug)
    logging.info("Target language: %s", config.target_language)

    raw_df = load_cleaned_reviews(paths["input_csv"])
    raw_df = normalise_loaded_dataframe(raw_df)

    theme_dictionary = load_theme_dictionary(paths["dictionary_path"])
    logging.info("Themes loaded: %s", len(theme_dictionary))

    df_text = prepare_theme_subset(raw_df, config)
    logging.info("Rows in target language with usable text: %s", len(df_text))

    if df_text.empty:
        raise ValueError(
            f"No usable reviews found for target language '{config.target_language}'."
        )

    df_enriched = enrich_reviews_with_themes(
        df_text=df_text,
        theme_dictionary=theme_dictionary,
        count_multiple_hits_per_theme=config.count_multiple_hits_per_theme,
    )

    if config.export_review_level_enriched_csv:
        export_table(df_enriched, paths["review_level_enriched_csv"])
        logging.info("Review-level enriched CSV written to: %s", paths["review_level_enriched_csv"])

    theme_corpus_overview = create_theme_corpus_overview(
        df_raw=raw_df,
        df_text=df_text,
        df_enriched=df_enriched,
        config=config,
        theme_dictionary=theme_dictionary,
    )
    theme_distribution_summary = create_theme_distribution_summary(df_enriched, theme_dictionary)
    theme_by_polarity = create_theme_by_polarity(df_enriched, theme_dictionary)
    theme_by_playtime_band = create_theme_by_playtime_band(df_enriched, theme_dictionary)
    theme_by_month = create_theme_by_month(df_enriched, theme_dictionary)
    theme_top_terms_by_theme = create_theme_top_terms_by_theme(df_enriched, theme_dictionary)

    tables = {
        "theme_corpus_overview": theme_corpus_overview,
        "theme_distribution_summary": theme_distribution_summary,
        "theme_by_polarity": theme_by_polarity,
        "theme_by_playtime_band": theme_by_playtime_band,
        "theme_by_month": theme_by_month,
        "theme_top_terms_by_theme": theme_top_terms_by_theme,
    }

    for table_name, table_df in tables.items():
        output_path = paths["theme_metrics_tables_dir"] / f"{config.game_slug}_{table_name}.csv"
        export_table(table_df, output_path)
        logging.info("Exported table: %s", output_path.name)

    summary_payload = {
        "app_id": config.app_id,
        "game_slug": config.game_slug,
        "game_title": config.game_title,
        "target_language": config.target_language,
        "generated_at_utc": pd.Timestamp.utcnow().isoformat(),
        "parameters": {
            "dictionary_path": config.dictionary_path,
            "min_token_length": config.min_token_length,
            "remove_stopwords": config.remove_stopwords,
            "export_review_level_enriched_csv": config.export_review_level_enriched_csv,
            "count_multiple_hits_per_theme": config.count_multiple_hits_per_theme,
        },
        "themes": list(theme_dictionary.keys()),
        "corpus_summary": {
            "rows_in_cleaned_dataset": int(len(raw_df)),
            "rows_with_usable_text_in_target_language": int(len(df_text)),
            "rows_with_any_theme_match": int((df_enriched["theme_match_count_total"] > 0).sum()),
            "total_tokens_analysed": int(df_enriched["token_count_for_theme_analysis"].sum()),
            "total_theme_matches": int(df_enriched["theme_match_count_total"].sum()),
        },
        "tables": {
            table_name: dataframe_to_json_records(table_df)
            for table_name, table_df in tables.items()
        },
    }

    with paths["summary_json"].open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, ensure_ascii=False, indent=2)

    logging.info("Summary JSON written to: %s", paths["summary_json"])
    logging.info("Theme metrics computation complete.")
    print("[INFO] Theme metrics computation complete.")


if __name__ == "__main__":
    main()