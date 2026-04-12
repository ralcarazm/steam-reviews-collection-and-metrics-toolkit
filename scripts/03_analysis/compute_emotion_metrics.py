#!/usr/bin/env python3
"""
compute_emotion_metrics.py

Generic Steam review emotion-metrics script for multiple games.

This script:
- reads a per-game JSON configuration file;
- loads the cleaned review dataset for one selected game;
- filters the corpus to one target language;
- applies the NRC Emotion Lexicon at word level;
- exports a review-level enriched CSV;
- exports aggregate emotion tables as CSV files;
- exports a JSON summary of the main outputs;
- writes an analysis log.

Usage example:

    python scripts/03_analysis/compute_emotion_metrics.py \
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
from typing import Any, Dict, List

import pandas as pd


# ============================================================================
# CONSTANTS
# ============================================================================

EMOTIONS = [
    "positive",
    "joy",
    "anticipation",
    "trust",
    "surprise",
    "negative",
    "fear",
    "sadness",
    "anger",
    "disgust",
]

TOKEN_PATTERN = re.compile(r"\b[\w'-]+\b", flags=re.UNICODE)

ENGLISH_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "to", "of", "in",
    "on", "at", "for", "from", "with", "without", "by", "is", "are", "was", "were",
    "be", "been", "being", "it", "its", "this", "that", "these", "those", "as",
    "i", "you", "he", "she", "we", "they", "them", "my", "your", "his", "her",
    "our", "their", "me", "him", "us", "do", "does", "did", "not", "no", "yes",
    "so", "very", "just", "can", "could", "would", "should", "will", "really",
    "game", "games"
}


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class GameConfig:
    """Configuration values for one emotion-analysis run."""
    app_id: int
    game_slug: str
    game_title: str
    lexicon_path: str
    target_language: str = "english"
    min_token_length: int = 2
    remove_stopwords: bool = True
    export_review_level_enriched_csv: bool = True
    top_n_emotion_terms: int = 100


# ============================================================================
# ARGUMENT PARSING
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compute emotion metrics for one prepared Steam review dataset."
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

    emotion_cfg = raw_config.get("emotion_metrics", {})
    lexicon_path = emotion_cfg.get(
        "lexicon_path",
        "resources/lexicons/nrc/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt",
    )

    return GameConfig(
        app_id=int(raw_config["app_id"]),
        game_slug=str(raw_config["game_slug"]).strip(),
        game_title=str(raw_config["game_title"]).strip(),
        lexicon_path=str(lexicon_path).strip(),
        target_language=str(emotion_cfg.get("target_language", "english")).strip().lower(),
        min_token_length=int(emotion_cfg.get("min_token_length", 2)),
        remove_stopwords=bool(emotion_cfg.get("remove_stopwords", True)),
        export_review_level_enriched_csv=bool(
            emotion_cfg.get("export_review_level_enriched_csv", True)
        ),
        top_n_emotion_terms=int(emotion_cfg.get("top_n_emotion_terms", 100)),
    )


# ============================================================================
# PATH MANAGEMENT
# ============================================================================

def get_repository_root() -> Path:
    """
    Resolve the repository root assuming this file lives at:
    scripts/03_analysis/compute_emotion_metrics.py
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
        "emotion_metrics_tables_dir": results_root / "tables" / "emotion_metrics",
    }

    paths["input_csv"] = paths["cleaned_dir"] / f"{config.game_slug}_reviews_cleaned.csv"
    paths["lexicon_path"] = repository_root / config.lexicon_path
    paths["summary_json"] = paths["metrics_dir"] / f"{config.game_slug}_emotion_metrics_summary.json"
    paths["analysis_log"] = paths["metrics_dir"] / f"{config.game_slug}_emotion_metrics.log"
    paths["review_level_enriched_csv"] = (
        paths["enriched_dir"] / f"{config.game_slug}_{config.target_language}_emotion_enriched.csv"
    )

    return paths


def ensure_directories(paths: Dict[str, Path]) -> None:
    """Create required output directories."""
    for key in ["enriched_dir", "metrics_dir", "tables_dir", "emotion_metrics_tables_dir"]:
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
# LEXICON LOADING
# ============================================================================

def load_nrc_lexicon(lexicon_path: Path) -> Dict[str, set[str]]:
    """Load the NRC lexicon as word -> set(emotions)."""
    if not lexicon_path.exists():
        raise FileNotFoundError(f"NRC lexicon not found: {lexicon_path}")

    lexicon: Dict[str, set[str]] = defaultdict(set)

    with lexicon_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.strip().split("\t")
            if len(parts) != 3:
                continue

            word, emotion, association = parts
            if emotion not in EMOTIONS:
                continue
            if association != "1":
                continue

            lexicon[word].add(emotion)

    if not lexicon:
        raise ValueError("The NRC lexicon was loaded but no valid emotion entries were found.")

    return dict(lexicon)


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


def prepare_emotion_subset(
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
    temp["token_count_for_emotion_analysis"] = temp["tokens"].map(len)
    temp = temp[temp["token_count_for_emotion_analysis"] > 0].copy()

    return temp.reset_index(drop=True)


# ============================================================================
# REVIEW-LEVEL ENRICHMENT
# ============================================================================

def enrich_reviews_with_emotions(
    df_text: pd.DataFrame,
    lexicon: Dict[str, set[str]],
) -> pd.DataFrame:
    """Add review-level emotion counts and rates."""
    temp = df_text.copy()
    review_rows = []

    for _, row in temp.iterrows():
        tokens: List[str] = row["tokens"]
        token_count = len(tokens)

        emotion_counts = {f"{emotion}_count": 0 for emotion in EMOTIONS}
        matched_emotion_token_count = 0

        for token in tokens:
            token_emotions = lexicon.get(token)
            if not token_emotions:
                continue

            matched_emotion_token_count += 1
            for emotion in token_emotions:
                emotion_counts[f"{emotion}_count"] += 1

        enriched_row = dict(row)
        enriched_row["emotion_token_count"] = matched_emotion_token_count

        for emotion in EMOTIONS:
            count_key = f"{emotion}_count"
            rate_key = f"{emotion}_per_100_tokens"
            enriched_row[count_key] = emotion_counts[count_key]
            enriched_row[rate_key] = (
                round((emotion_counts[count_key] / token_count) * 100, 6)
                if token_count > 0 else None
            )

        review_rows.append(enriched_row)

    return pd.DataFrame(review_rows)


# ============================================================================
# AGGREGATE TABLES
# ============================================================================

def create_emotion_corpus_overview(
    df_raw: pd.DataFrame,
    df_text: pd.DataFrame,
    df_enriched: pd.DataFrame,
    config: GameConfig,
) -> pd.DataFrame:
    """Create corpus overview for emotion analysis."""
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
        {"metric": "reviews_with_any_emotion_match", "value": int((df_enriched["emotion_token_count"] > 0).sum())},
        {"metric": "total_tokens_analysed", "value": int(df_enriched["token_count_for_emotion_analysis"].sum())},
        {"metric": "total_emotion_token_matches", "value": int(df_enriched["emotion_token_count"].sum())},
    ]

    for emotion in EMOTIONS:
        rows.append(
            {
                "metric": f"reviews_with_{emotion}_signal",
                "value": int((df_enriched[f"{emotion}_count"] > 0).sum()),
            }
        )

    return pd.DataFrame(rows)


def create_emotion_distribution_summary(df_enriched: pd.DataFrame) -> pd.DataFrame:
    """Create global emotion distribution summary."""
    total_tokens = df_enriched["token_count_for_emotion_analysis"].sum()
    total_reviews = len(df_enriched)

    rows = []
    for emotion in EMOTIONS:
        emotion_total = int(df_enriched[f"{emotion}_count"].sum())
        reviews_with_emotion = int((df_enriched[f"{emotion}_count"] > 0).sum())

        rows.append(
            {
                "emotion": emotion,
                "total_hits": emotion_total,
                "hits_per_1000_tokens": round((emotion_total / total_tokens) * 1000, 6) if total_tokens > 0 else None,
                "reviews_with_emotion": reviews_with_emotion,
                "review_share_with_emotion": round((reviews_with_emotion / total_reviews) * 100, 4) if total_reviews > 0 else None,
                "mean_count_per_review": round(float(df_enriched[f"{emotion}_count"].mean()), 6),
                "mean_per_100_tokens": round(float(df_enriched[f"{emotion}_per_100_tokens"].mean()), 6),
            }
        )

    return pd.DataFrame(rows)


def create_emotion_by_polarity(df_enriched: pd.DataFrame) -> pd.DataFrame:
    """Create emotion summary by polarity."""
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
            "total_tokens": int(subset["token_count_for_emotion_analysis"].sum()) if len(subset) > 0 else 0,
            "emotion_token_count": int(subset["emotion_token_count"].sum()) if len(subset) > 0 else 0,
        }

        for emotion in EMOTIONS:
            row[f"{emotion}_mean_count"] = round(float(subset[f"{emotion}_count"].mean()), 6) if len(subset) > 0 else None
            row[f"{emotion}_mean_per_100_tokens"] = round(float(subset[f"{emotion}_per_100_tokens"].mean()), 6) if len(subset) > 0 else None
            row[f"{emotion}_review_share"] = round(float((subset[f"{emotion}_count"] > 0).mean() * 100), 4) if len(subset) > 0 else None

        rows.append(row)

    return pd.DataFrame(rows)


def create_emotion_by_playtime_band(df_enriched: pd.DataFrame) -> pd.DataFrame:
    """Create emotion summary by playtime band."""
    if "playtime_at_review_band" not in df_enriched.columns:
        return pd.DataFrame(
            columns=["playtime_at_review_band", "review_count", "total_tokens", "emotion_token_count"]
            + [f"{emotion}_mean_count" for emotion in EMOTIONS]
            + [f"{emotion}_mean_per_100_tokens" for emotion in EMOTIONS]
            + [f"{emotion}_review_share" for emotion in EMOTIONS]
        )

    temp = df_enriched.dropna(subset=["playtime_at_review_band"]).copy()
    if temp.empty:
        return pd.DataFrame(
            columns=["playtime_at_review_band", "review_count", "total_tokens", "emotion_token_count"]
            + [f"{emotion}_mean_count" for emotion in EMOTIONS]
            + [f"{emotion}_mean_per_100_tokens" for emotion in EMOTIONS]
            + [f"{emotion}_review_share" for emotion in EMOTIONS]
        )

    rows = []
    for band, subset in temp.groupby("playtime_at_review_band", dropna=False):
        row = {
            "playtime_at_review_band": band,
            "review_count": int(len(subset)),
            "total_tokens": int(subset["token_count_for_emotion_analysis"].sum()),
            "emotion_token_count": int(subset["emotion_token_count"].sum()),
        }

        for emotion in EMOTIONS:
            row[f"{emotion}_mean_count"] = round(float(subset[f"{emotion}_count"].mean()), 6)
            row[f"{emotion}_mean_per_100_tokens"] = round(float(subset[f"{emotion}_per_100_tokens"].mean()), 6)
            row[f"{emotion}_review_share"] = round(float((subset[f"{emotion}_count"] > 0).mean() * 100), 4)

        rows.append(row)

    return pd.DataFrame(rows).sort_values("playtime_at_review_band").reset_index(drop=True)


def create_emotion_by_month(df_enriched: pd.DataFrame) -> pd.DataFrame:
    """Create monthly emotion summary."""
    if "review_created_year_month" not in df_enriched.columns:
        return pd.DataFrame()

    rows = []
    for month, subset in df_enriched.groupby("review_created_year_month", dropna=False):
        row = {
            "review_created_year_month": month,
            "review_count": int(len(subset)),
            "total_tokens": int(subset["token_count_for_emotion_analysis"].sum()),
            "emotion_token_count": int(subset["emotion_token_count"].sum()),
        }

        for emotion in EMOTIONS:
            row[f"{emotion}_mean_count"] = round(float(subset[f"{emotion}_count"].mean()), 6)
            row[f"{emotion}_mean_per_100_tokens"] = round(float(subset[f"{emotion}_per_100_tokens"].mean()), 6)
            row[f"{emotion}_review_share"] = round(float((subset[f"{emotion}_count"] > 0).mean() * 100), 4)

        rows.append(row)

    return pd.DataFrame(rows).sort_values("review_created_year_month").reset_index(drop=True)


def create_emotion_top_terms_by_emotion(
    df_enriched: pd.DataFrame,
    lexicon: Dict[str, set[str]],
    top_n: int,
) -> pd.DataFrame:
    """Create top term table for each emotion."""
    counters: Dict[str, Counter] = {emotion: Counter() for emotion in EMOTIONS}

    for tokens in df_enriched["tokens"]:
        for token in tokens:
            token_emotions = lexicon.get(token)
            if not token_emotions:
                continue
            for emotion in token_emotions:
                counters[emotion][token] += 1

    rows = []
    for emotion in EMOTIONS:
        total_emotion_hits = sum(counters[emotion].values())
        for rank, (token, frequency) in enumerate(counters[emotion].most_common(top_n), start=1):
            rows.append(
                {
                    "emotion": emotion,
                    "rank": rank,
                    "token": token,
                    "frequency": frequency,
                    "relative_frequency_per_1000_emotion_hits": round((frequency / total_emotion_hits) * 1000, 6)
                    if total_emotion_hits > 0 else None,
                }
            )

    return pd.DataFrame(rows).sort_values(["emotion", "rank"]).reset_index(drop=True)


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
    print(f"[INFO] NRC lexicon: {paths['lexicon_path']}")
    print(f"[INFO] Output tables: {paths['emotion_metrics_tables_dir']}")
    print(f"[INFO] Summary JSON: {paths['summary_json']}")

    logging.info("Starting emotion metrics computation.")
    logging.info("Configuration file: %s", config_path)
    logging.info("Game title: %s", config.game_title)
    logging.info("App ID: %s", config.app_id)
    logging.info("Game slug: %s", config.game_slug)
    logging.info("Target language: %s", config.target_language)

    raw_df = load_cleaned_reviews(paths["input_csv"])
    raw_df = normalise_loaded_dataframe(raw_df)

    lexicon = load_nrc_lexicon(paths["lexicon_path"])
    logging.info("NRC entries loaded: %s", len(lexicon))

    df_text = prepare_emotion_subset(raw_df, config)
    logging.info("Rows in target language with usable text: %s", len(df_text))

    if df_text.empty:
        raise ValueError(
            f"No usable reviews found for target language '{config.target_language}'."
        )

    df_enriched = enrich_reviews_with_emotions(df_text, lexicon)

    if config.export_review_level_enriched_csv:
        export_table(df_enriched, paths["review_level_enriched_csv"])
        logging.info("Review-level enriched CSV written to: %s", paths["review_level_enriched_csv"])

    emotion_corpus_overview = create_emotion_corpus_overview(raw_df, df_text, df_enriched, config)
    emotion_distribution_summary = create_emotion_distribution_summary(df_enriched)
    emotion_by_polarity = create_emotion_by_polarity(df_enriched)
    emotion_by_playtime_band = create_emotion_by_playtime_band(df_enriched)
    emotion_by_month = create_emotion_by_month(df_enriched)
    emotion_top_terms_by_emotion = create_emotion_top_terms_by_emotion(
        df_enriched=df_enriched,
        lexicon=lexicon,
        top_n=config.top_n_emotion_terms,
    )

    tables = {
        "emotion_corpus_overview": emotion_corpus_overview,
        "emotion_distribution_summary": emotion_distribution_summary,
        "emotion_by_polarity": emotion_by_polarity,
        "emotion_by_playtime_band": emotion_by_playtime_band,
        "emotion_by_month": emotion_by_month,
        "emotion_top_terms_by_emotion": emotion_top_terms_by_emotion,
    }

    for table_name, table_df in tables.items():
        output_path = paths["emotion_metrics_tables_dir"] / f"{config.game_slug}_{table_name}.csv"
        export_table(table_df, output_path)
        logging.info("Exported table: %s", output_path.name)

    summary_payload = {
        "app_id": config.app_id,
        "game_slug": config.game_slug,
        "game_title": config.game_title,
        "target_language": config.target_language,
        "generated_at_utc": pd.Timestamp.utcnow().isoformat(),
        "parameters": {
            "lexicon_path": config.lexicon_path,
            "min_token_length": config.min_token_length,
            "remove_stopwords": config.remove_stopwords,
            "export_review_level_enriched_csv": config.export_review_level_enriched_csv,
            "top_n_emotion_terms": config.top_n_emotion_terms,
        },
        "corpus_summary": {
            "rows_in_cleaned_dataset": int(len(raw_df)),
            "rows_with_usable_text_in_target_language": int(len(df_text)),
            "rows_with_any_emotion_match": int((df_enriched["emotion_token_count"] > 0).sum()),
            "total_tokens_analysed": int(df_enriched["token_count_for_emotion_analysis"].sum()),
            "total_emotion_token_matches": int(df_enriched["emotion_token_count"].sum()),
        },
        "tables": {
            table_name: dataframe_to_json_records(table_df)
            for table_name, table_df in tables.items()
        },
    }

    with paths["summary_json"].open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, ensure_ascii=False, indent=2)

    logging.info("Summary JSON written to: %s", paths["summary_json"])
    logging.info("Emotion metrics computation complete.")
    print("[INFO] Emotion metrics computation complete.")


if __name__ == "__main__":
    main()