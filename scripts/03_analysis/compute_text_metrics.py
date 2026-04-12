#!/usr/bin/env python3
"""
compute_text_metrics.py

Generic Steam review text-metrics script for multiple games.

This script:
- reads a per-game JSON configuration file;
- loads the cleaned review dataset for one selected game;
- computes global textual metrics;
- computes per-language textual metrics for languages above a configurable threshold;
- exports text metrics tables as CSV files;
- exports a JSON summary of the main outputs;
- writes an analysis log.

Usage examples:

    python scripts/03_analysis/compute_text_metrics.py \
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
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pandas as pd


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class GameConfig:
    """Configuration values for a single game text-analysis run."""
    app_id: int
    game_slug: str
    game_title: str
    min_reviews_per_language: int = 100
    min_share_per_language: float = 1.0
    top_n_unigrams: int = 200
    top_n_bigrams: int = 100
    top_n_trigrams: int = 50
    min_token_length: int = 2
    remove_stopwords: bool = True
    use_lemmatisation: bool = False
    export_per_language: bool = True


# ============================================================================
# ARGUMENT PARSING
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compute textual metrics for one prepared Steam review dataset."
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

    text_metrics_cfg = raw_config.get("text_metrics", {})

    return GameConfig(
        app_id=int(raw_config["app_id"]),
        game_slug=str(raw_config["game_slug"]).strip(),
        game_title=str(raw_config["game_title"]).strip(),
        min_reviews_per_language=int(text_metrics_cfg.get("min_reviews_per_language", 100)),
        min_share_per_language=float(text_metrics_cfg.get("min_share_per_language", 1.0)),
        top_n_unigrams=int(text_metrics_cfg.get("top_n_unigrams", 200)),
        top_n_bigrams=int(text_metrics_cfg.get("top_n_bigrams", 100)),
        top_n_trigrams=int(text_metrics_cfg.get("top_n_trigrams", 50)),
        min_token_length=int(text_metrics_cfg.get("min_token_length", 2)),
        remove_stopwords=bool(text_metrics_cfg.get("remove_stopwords", True)),
        use_lemmatisation=bool(text_metrics_cfg.get("use_lemmatisation", False)),
        export_per_language=bool(text_metrics_cfg.get("export_per_language", True)),
    )


# ============================================================================
# PATH MANAGEMENT
# ============================================================================

def get_repository_root() -> Path:
    """
    Resolve the repository root assuming this file lives at:
    scripts/03_analysis/compute_text_metrics.py
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
        "text_metrics_dir": results_root / "tables" / "text_metrics",
        "text_metrics_global_dir": results_root / "tables" / "text_metrics" / "global",
        "text_metrics_by_language_dir": results_root / "tables" / "text_metrics" / "by_language",
    }

    paths["input_csv"] = paths["cleaned_dir"] / f"{game_slug}_reviews_cleaned.csv"
    paths["summary_json"] = paths["metrics_dir"] / f"{game_slug}_text_metrics_summary.json"
    paths["analysis_log"] = paths["metrics_dir"] / f"{game_slug}_text_metrics.log"

    return paths


def ensure_directories(paths: Dict[str, Path]) -> None:
    """Create required output directories."""
    for key in [
        "metrics_dir",
        "tables_dir",
        "text_metrics_dir",
        "text_metrics_global_dir",
        "text_metrics_by_language_dir",
    ]:
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
        "has_text_review",
    ]

    numeric_columns = [
        "review_length_words",
        "review_length_chars",
        "playtime_at_review",
    ]

    df = restore_boolean_columns(df, boolean_columns)
    df = restore_numeric_columns(df, numeric_columns)

    for column in ["language", "review", "playtime_at_review_band"]:
        if column in df.columns:
            df[column] = df[column].astype("string")

    return df


# ============================================================================
# STOPWORDS
# ============================================================================

STOPWORDS_BY_LANGUAGE: Dict[str, set[str]] = {
    "english": {
        "the", "a", "an", "and", "or", "but", "if", "then", "than", "to", "of", "in",
        "on", "at", "for", "from", "with", "without", "by", "is", "are", "was", "were",
        "be", "been", "being", "it", "its", "this", "that", "these", "those", "as",
        "i", "you", "he", "she", "we", "they", "them", "my", "your", "his", "her",
        "our", "their", "me", "him", "us", "do", "does", "did", "not", "no", "yes",
        "so", "very", "just", "can", "could", "would", "should", "will", "really",
        "game", "games"
    },
    "spanish": {
        "el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "pero", "si",
        "de", "del", "al", "en", "por", "para", "con", "sin", "es", "son", "fue",
        "eran", "ser", "ha", "han", "que", "como", "muy", "más", "menos", "yo", "tú",
        "tu", "él", "ella", "nos", "nosotros", "ellos", "ellas", "mi", "mis", "su",
        "sus", "me", "te", "se", "lo", "le", "les", "ya", "no", "sí", "si", "juego",
        "juegos"
    },
    "russian": {
        "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
        "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
        "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "еще", "нет",
        "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли", "если",
        "или", "ни", "быть", "был", "него", "до", "вас", "игра", "игры"
    },
    "german": {
        "der", "die", "das", "ein", "eine", "und", "oder", "aber", "wenn", "dann",
        "zu", "von", "in", "im", "am", "für", "mit", "ohne", "ist", "sind", "war",
        "waren", "sein", "ich", "du", "er", "sie", "wir", "ihr", "sie", "mein",
        "dein", "sein", "ihr", "unser", "nicht", "ja", "so", "sehr", "nur", "spiel",
        "spiele"
    },
    "french": {
        "le", "la", "les", "un", "une", "des", "et", "ou", "mais", "si", "de", "du",
        "dans", "sur", "à", "au", "aux", "pour", "avec", "sans", "est", "sont",
        "était", "être", "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
        "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses", "pas", "oui",
        "très", "plus", "jeu", "jeux"
    },
    "portuguese": {
        "o", "a", "os", "as", "um", "uma", "uns", "umas", "e", "ou", "mas", "se",
        "de", "do", "da", "dos", "das", "em", "no", "na", "por", "para", "com", "sem",
        "é", "são", "foi", "ser", "eu", "tu", "ele", "ela", "nós", "vocês", "eles",
        "elas", "meu", "minha", "seu", "sua", "não", "sim", "muito", "mais", "jogo",
        "jogos"
    },
    "brazilian": {
        "o", "a", "os", "as", "um", "uma", "uns", "umas", "e", "ou", "mas", "se",
        "de", "do", "da", "dos", "das", "em", "no", "na", "por", "para", "com", "sem",
        "é", "são", "foi", "ser", "eu", "tu", "ele", "ela", "nós", "vocês", "eles",
        "elas", "meu", "minha", "seu", "sua", "não", "sim", "muito", "mais", "jogo",
        "jogos"
    },
    "italian": {
        "il", "lo", "la", "i", "gli", "le", "un", "una", "e", "o", "ma", "se", "di",
        "del", "della", "in", "nel", "sul", "per", "con", "senza", "è", "sono", "era",
        "essere", "io", "tu", "lui", "lei", "noi", "voi", "loro", "mio", "mia", "tuo",
        "tua", "suo", "sua", "non", "sì", "molto", "più", "gioco", "giochi"
    },
}


# ============================================================================
# TOKENISATION AND TEXT PREPARATION
# ============================================================================

TOKEN_PATTERN = re.compile(r"\b[\w'-]+\b", flags=re.UNICODE)


def slugify_language(language: str) -> str:
    """Convert a language label into a filesystem-friendly slug."""
    text = language.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def get_language_stopwords(language: str) -> set[str]:
    """Return stopwords for a given language label."""
    language_key = str(language).strip().lower()
    return STOPWORDS_BY_LANGUAGE.get(language_key, set())


def tokenise_text(
    text: str,
    language: str,
    min_token_length: int,
    remove_stopwords: bool,
) -> List[str]:
    """Tokenise one text into a cleaned token list."""
    lowered = text.lower()
    tokens = TOKEN_PATTERN.findall(lowered)

    cleaned_tokens: List[str] = []
    stopwords = get_language_stopwords(language) if remove_stopwords else set()

    for token in tokens:
        if token.isdigit():
            continue
        if len(token) < min_token_length:
            continue
        if remove_stopwords and token in stopwords:
            continue
        cleaned_tokens.append(token)

    return cleaned_tokens


def build_ngrams(tokens: Sequence[str], n: int) -> List[str]:
    """Build n-grams from a token list."""
    if n <= 0 or len(tokens) < n:
        return []
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def prepare_text_dataframe(
    df: pd.DataFrame,
    min_token_length: int,
    remove_stopwords: bool,
) -> pd.DataFrame:
    """Prepare dataframe with tokenised text."""
    temp = df.copy()

    if "language" not in temp.columns:
        temp["language"] = "unknown"

    temp["language"] = temp["language"].fillna("unknown").astype("string")
    temp["review"] = temp["review"].fillna(pd.NA).astype("string")
    temp = temp[temp["review"].notna()].copy()
    temp["review"] = temp["review"].str.strip()
    temp = temp[temp["review"] != ""].copy()

    temp["tokens"] = temp.apply(
        lambda row: tokenise_text(
            text=str(row["review"]),
            language=str(row["language"]),
            min_token_length=min_token_length,
            remove_stopwords=remove_stopwords,
        ),
        axis=1,
    )

    temp["token_count"] = temp["tokens"].map(len)
    temp = temp[temp["token_count"] > 0].copy()

    return temp.reset_index(drop=True)


# ============================================================================
# GENERIC HELPERS
# ============================================================================

def safe_rate(numerator: float, denominator: float) -> float | None:
    """Return a percentage safely."""
    if denominator == 0 or pd.isna(denominator):
        return None
    return round((numerator / denominator) * 100, 4)


def safe_per_thousand(count: float, total: float) -> float | None:
    """Return frequency per 1000 safely."""
    if total == 0 or pd.isna(total):
        return None
    return round((count / total) * 1000, 6)


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


def dataframe_to_json_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert a dataframe to JSON-safe records."""
    records = []
    for record in df.to_dict(orient="records"):
        records.append({key: to_serialisable(value) for key, value in record.items()})
    return records


def export_table(df: pd.DataFrame, output_path: Path) -> None:
    """Export one dataframe to CSV."""
    df.to_csv(output_path, index=False, encoding="utf-8-sig")


# ============================================================================
# BAND HELPERS
# ============================================================================

def add_band_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add playtime bands if needed."""
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


# ============================================================================
# CORE TEXT METRICS
# ============================================================================

def get_total_tokens(token_lists: Iterable[List[str]]) -> int:
    """Count total tokens in nested token lists."""
    return sum(len(tokens) for tokens in token_lists)


def get_vocabulary_counter(token_lists: Iterable[List[str]]) -> Counter:
    """Build token counter from nested token lists."""
    counter: Counter = Counter()
    for tokens in token_lists:
        counter.update(tokens)
    return counter


def build_frequency_table(
    counter: Counter,
    top_n: int,
    label_name: str,
    relative_label: str,
) -> pd.DataFrame:
    """Build ranked frequency table from a Counter."""
    total = sum(counter.values())
    rows = []
    for rank, (token, frequency) in enumerate(counter.most_common(top_n), start=1):
        rows.append(
            {
                "rank": rank,
                label_name: token,
                "frequency": frequency,
                relative_label: safe_per_thousand(frequency, total),
            }
        )
    return pd.DataFrame(rows)


def build_ngram_counter(token_lists: Iterable[List[str]], n: int) -> Counter:
    """Build n-gram counter from nested token lists."""
    counter: Counter = Counter()
    for tokens in token_lists:
        counter.update(build_ngrams(tokens, n))
    return counter


def compute_type_token_ratio(counter: Counter) -> float | None:
    """Compute type-token ratio."""
    total_tokens = sum(counter.values())
    if total_tokens == 0:
        return None
    return round(len(counter) / total_tokens, 6)


def create_text_corpus_overview(
    df_text: pd.DataFrame,
    config: GameConfig,
    selected_languages: List[str],
    scope_label: str,
    language_label: str | None = None,
) -> pd.DataFrame:
    """Create corpus overview table."""
    token_counter = get_vocabulary_counter(df_text["tokens"])
    total_tokens = sum(token_counter.values())
    unique_tokens = len(token_counter)

    rows = [
        {"metric": "scope", "value": scope_label},
        {"metric": "app_id", "value": config.app_id},
        {"metric": "game_slug", "value": config.game_slug},
        {"metric": "game_title", "value": config.game_title},
    ]

    if language_label is not None:
        rows.append({"metric": "language", "value": language_label})

    rows.extend(
        [
            {"metric": "reviews_with_text", "value": int(len(df_text))},
            {"metric": "positive_review_count", "value": int(df_text["is_positive"].fillna(False).sum()) if "is_positive" in df_text.columns else None},
            {"metric": "negative_review_count", "value": int(df_text["is_negative"].fillna(False).sum()) if "is_negative" in df_text.columns else None},
            {"metric": "total_tokens", "value": total_tokens},
            {"metric": "total_unique_tokens", "value": unique_tokens},
            {"metric": "type_token_ratio", "value": compute_type_token_ratio(token_counter)},
            {"metric": "average_review_length_words", "value": round(float(df_text["review_length_words"].mean()), 4) if "review_length_words" in df_text.columns else None},
            {"metric": "median_review_length_words", "value": round(float(df_text["review_length_words"].median()), 4) if "review_length_words" in df_text.columns else None},
            {"metric": "average_review_length_chars", "value": round(float(df_text["review_length_chars"].mean()), 4) if "review_length_chars" in df_text.columns else None},
            {"metric": "median_review_length_chars", "value": round(float(df_text["review_length_chars"].median()), 4) if "review_length_chars" in df_text.columns else None},
        ]
    )

    if language_label is None:
        rows.append({"metric": "languages_with_text", "value": int(df_text["language"].dropna().nunique())})
        rows.append({"metric": "selected_languages_for_separate_output", "value": ", ".join(selected_languages)})

    return pd.DataFrame(rows)


def create_text_metrics_by_polarity(df_text: pd.DataFrame) -> pd.DataFrame:
    """Create text metrics by polarity."""
    segments: List[Tuple[str, pd.DataFrame]] = [("overall", df_text)]

    if "is_positive" in df_text.columns:
        segments.append(("positive", df_text[df_text["is_positive"].fillna(False)]))
    if "is_negative" in df_text.columns:
        segments.append(("negative", df_text[df_text["is_negative"].fillna(False)]))

    rows = []
    for segment_name, subset in segments:
        token_counter = get_vocabulary_counter(subset["tokens"])
        total_tokens = sum(token_counter.values())
        unique_tokens = len(token_counter)

        rows.append(
            {
                "segment": segment_name,
                "review_count": int(len(subset)),
                "total_tokens": total_tokens,
                "unique_tokens": unique_tokens,
                "type_token_ratio": compute_type_token_ratio(token_counter),
                "mean_review_length_words": round(float(subset["review_length_words"].mean()), 4) if len(subset) > 0 and "review_length_words" in subset.columns else None,
                "median_review_length_words": round(float(subset["review_length_words"].median()), 4) if len(subset) > 0 and "review_length_words" in subset.columns else None,
                "mean_review_length_chars": round(float(subset["review_length_chars"].mean()), 4) if len(subset) > 0 and "review_length_chars" in subset.columns else None,
                "median_review_length_chars": round(float(subset["review_length_chars"].median()), 4) if len(subset) > 0 and "review_length_chars" in subset.columns else None,
            }
        )

    return pd.DataFrame(rows)


def create_text_metrics_by_playtime_band(df_text: pd.DataFrame) -> pd.DataFrame:
    """Create text metrics by playtime band."""
    if "playtime_at_review_band" not in df_text.columns:
        return pd.DataFrame()

    rows = []
    for band, subset in (
        df_text.groupby("playtime_at_review_band", dropna=False)
        if "playtime_at_review_band" in df_text.columns else []
    ):
        token_counter = get_vocabulary_counter(subset["tokens"])
        total_tokens = sum(token_counter.values())
        unique_tokens = len(token_counter)

        rows.append(
            {
                "playtime_at_review_band": band,
                "review_count": int(len(subset)),
                "total_tokens": total_tokens,
                "unique_tokens": unique_tokens,
                "type_token_ratio": compute_type_token_ratio(token_counter),
                "mean_review_length_words": round(float(subset["review_length_words"].mean()), 4) if len(subset) > 0 and "review_length_words" in subset.columns else None,
                "median_review_length_words": round(float(subset["review_length_words"].median()), 4) if len(subset) > 0 and "review_length_words" in subset.columns else None,
            }
        )

    return pd.DataFrame(rows).sort_values("playtime_at_review_band").reset_index(drop=True)


def create_text_metrics_by_language(df_text: pd.DataFrame) -> pd.DataFrame:
    """Create text metrics by language."""
    total_reviews = len(df_text)
    rows = []

    for language, subset in (
        df_text.groupby("language", dropna=False)
        if "language" in df_text.columns else []
    ):
        token_counter = get_vocabulary_counter(subset["tokens"])
        total_tokens = sum(token_counter.values())
        unique_tokens = len(token_counter)

        rows.append(
            {
                "language": language,
                "review_count": int(len(subset)),
                "review_percentage": safe_rate(len(subset), total_reviews),
                "total_tokens": total_tokens,
                "unique_tokens": unique_tokens,
                "type_token_ratio": compute_type_token_ratio(token_counter),
                "mean_review_length_words": round(float(subset["review_length_words"].mean()), 4) if len(subset) > 0 and "review_length_words" in subset.columns else None,
                "median_review_length_words": round(float(subset["review_length_words"].median()), 4) if len(subset) > 0 and "review_length_words" in subset.columns else None,
            }
        )

    return pd.DataFrame(rows).sort_values(
        by=["review_count", "language"],
        ascending=[False, True],
    ).reset_index(drop=True)


def create_top_terms_by_language(
    df_text: pd.DataFrame,
    top_n_unigrams: int,
) -> pd.DataFrame:
    """Create comparative top-terms table by language."""
    rows = []

    for language, subset in (
        df_text.groupby("language", dropna=False)
        if "language" in df_text.columns else []
    ):
        counter = get_vocabulary_counter(subset["tokens"])
        total_tokens = sum(counter.values())

        for rank, (token, frequency) in enumerate(counter.most_common(top_n_unigrams), start=1):
            rows.append(
                {
                    "language": language,
                    "rank": rank,
                    "token": token,
                    "frequency": frequency,
                    "relative_frequency_per_1000_tokens": safe_per_thousand(frequency, total_tokens),
                }
            )

    return pd.DataFrame(rows).sort_values(
        by=["language", "rank"],
        ascending=[True, True],
    ).reset_index(drop=True)


def create_distinctive_terms(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    label_a: str,
    label_b: str,
    top_n: int,
) -> pd.DataFrame:
    """Create distinctive terms table between two subsets."""
    counter_a = get_vocabulary_counter(df_a["tokens"])
    counter_b = get_vocabulary_counter(df_b["tokens"])

    total_a = sum(counter_a.values())
    total_b = sum(counter_b.values())

    all_terms = set(counter_a.keys()) | set(counter_b.keys())
    rows = []

    for token in all_terms:
        freq_a = counter_a.get(token, 0)
        freq_b = counter_b.get(token, 0)

        rel_a = (freq_a / total_a) if total_a > 0 else 0.0
        rel_b = (freq_b / total_b) if total_b > 0 else 0.0

        difference_per_1000 = (rel_a - rel_b) * 1000
        log_ratio = math.log2((rel_a + 1e-12) / (rel_b + 1e-12))

        rows.append(
            {
                "token": token,
                f"{label_a}_frequency": freq_a,
                f"{label_b}_frequency": freq_b,
                f"{label_a}_relative_per_1000": round(rel_a * 1000, 6),
                f"{label_b}_relative_per_1000": round(rel_b * 1000, 6),
                "difference_per_1000": round(difference_per_1000, 6),
                "log_ratio": round(log_ratio, 6),
            }
        )

    result = pd.DataFrame(rows).sort_values(
        by=["difference_per_1000", f"{label_a}_frequency", "token"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    return result.head(top_n).reset_index(drop=True)


# ============================================================================
# LANGUAGE SELECTION
# ============================================================================

def select_languages_for_export(
    df_text: pd.DataFrame,
    config: GameConfig,
) -> Tuple[List[str], pd.DataFrame]:
    """Select languages eligible for separate output."""
    total_reviews = len(df_text)

    language_counts = (
        df_text["language"]
        .fillna("unknown")
        .value_counts(dropna=False)
        .rename_axis("language")
        .reset_index(name="review_count")
    )
    language_counts["review_percentage"] = language_counts["review_count"].apply(
        lambda x: safe_rate(x, total_reviews)
    )

    selected_languages = language_counts[
        (language_counts["review_count"] >= config.min_reviews_per_language)
        | (language_counts["review_percentage"].fillna(0) >= config.min_share_per_language)
    ]["language"].astype(str).tolist()

    return selected_languages, language_counts


# ============================================================================
# EXPORT BLOCKS
# ============================================================================

def export_global_text_metrics(
    df_text: pd.DataFrame,
    config: GameConfig,
    paths: Dict[str, Path],
    selected_languages: List[str],
) -> Dict[str, str]:
    """Export global text metrics."""
    output_paths: Dict[str, str] = {}
    global_dir = paths["text_metrics_global_dir"]

    overview = create_text_corpus_overview(
        df_text=df_text,
        config=config,
        selected_languages=selected_languages,
        scope_label="global",
    )
    metrics_by_polarity = create_text_metrics_by_polarity(df_text)
    metrics_by_playtime_band = create_text_metrics_by_playtime_band(df_text)
    metrics_by_language = create_text_metrics_by_language(df_text)
    top_terms_by_language = create_top_terms_by_language(df_text, config.top_n_unigrams)

    unigram_counter_overall = get_vocabulary_counter(df_text["tokens"])
    unigram_counter_positive = get_vocabulary_counter(
        df_text[df_text["is_positive"].fillna(False)]["tokens"]
    )
    unigram_counter_negative = get_vocabulary_counter(
        df_text[df_text["is_negative"].fillna(False)]["tokens"]
    )

    bigram_counter_overall = build_ngram_counter(df_text["tokens"], 2)
    bigram_counter_positive = build_ngram_counter(
        df_text[df_text["is_positive"].fillna(False)]["tokens"], 2
    )
    bigram_counter_negative = build_ngram_counter(
        df_text[df_text["is_negative"].fillna(False)]["tokens"], 2
    )
    trigram_counter_overall = build_ngram_counter(df_text["tokens"], 3)

    top_unigrams_overall = build_frequency_table(
        unigram_counter_overall,
        config.top_n_unigrams,
        "token",
        "relative_frequency_per_1000_tokens",
    )
    top_unigrams_positive = build_frequency_table(
        unigram_counter_positive,
        config.top_n_unigrams,
        "token",
        "relative_frequency_per_1000_tokens",
    )
    top_unigrams_negative = build_frequency_table(
        unigram_counter_negative,
        config.top_n_unigrams,
        "token",
        "relative_frequency_per_1000_tokens",
    )

    top_bigrams_overall = build_frequency_table(
        bigram_counter_overall,
        config.top_n_bigrams,
        "bigram",
        "relative_frequency_per_1000_bigrams",
    )
    top_bigrams_positive = build_frequency_table(
        bigram_counter_positive,
        config.top_n_bigrams,
        "bigram",
        "relative_frequency_per_1000_bigrams",
    )
    top_bigrams_negative = build_frequency_table(
        bigram_counter_negative,
        config.top_n_bigrams,
        "bigram",
        "relative_frequency_per_1000_bigrams",
    )

    top_trigrams_overall = build_frequency_table(
        trigram_counter_overall,
        config.top_n_trigrams,
        "trigram",
        "relative_frequency_per_1000_trigrams",
    )

    positive_df = df_text[df_text["is_positive"].fillna(False)].copy()
    negative_df = df_text[df_text["is_negative"].fillna(False)].copy()

    distinctive_positive_vs_negative = create_distinctive_terms(
        positive_df,
        negative_df,
        "positive",
        "negative",
        config.top_n_unigrams,
    )
    distinctive_negative_vs_positive = create_distinctive_terms(
        negative_df,
        positive_df,
        "negative",
        "positive",
        config.top_n_unigrams,
    )

    tables = {
        "text_corpus_overview.csv": overview,
        "text_metrics_by_polarity.csv": metrics_by_polarity,
        "text_metrics_by_playtime_band.csv": metrics_by_playtime_band,
        "text_metrics_by_language.csv": metrics_by_language,
        "top_terms_by_language.csv": top_terms_by_language,
        "top_unigrams_overall.csv": top_unigrams_overall,
        "top_unigrams_positive.csv": top_unigrams_positive,
        "top_unigrams_negative.csv": top_unigrams_negative,
        "top_bigrams_overall.csv": top_bigrams_overall,
        "top_bigrams_positive.csv": top_bigrams_positive,
        "top_bigrams_negative.csv": top_bigrams_negative,
        "top_trigrams_overall.csv": top_trigrams_overall,
        "distinctive_terms_positive_vs_negative.csv": distinctive_positive_vs_negative,
        "distinctive_terms_negative_vs_positive.csv": distinctive_negative_vs_positive,
    }

    for filename, table_df in tables.items():
        output_path = global_dir / filename
        export_table(table_df, output_path)
        output_paths[filename] = str(output_path)

    return output_paths


def export_language_text_metrics(
    df_text: pd.DataFrame,
    config: GameConfig,
    paths: Dict[str, Path],
    language: str,
) -> Dict[str, str]:
    """Export text metrics for one language."""
    language_slug = slugify_language(language)
    language_dir = paths["text_metrics_by_language_dir"] / language_slug
    language_dir.mkdir(parents=True, exist_ok=True)

    subset = df_text[df_text["language"].fillna("unknown") == language].copy()

    output_paths: Dict[str, str] = {}

    overview = create_text_corpus_overview(
        df_text=subset,
        config=config,
        selected_languages=[],
        scope_label="by_language",
        language_label=language,
    )
    metrics_by_polarity = create_text_metrics_by_polarity(subset)
    metrics_by_playtime_band = create_text_metrics_by_playtime_band(subset)

    unigram_counter_overall = get_vocabulary_counter(subset["tokens"])
    unigram_counter_positive = get_vocabulary_counter(
        subset[subset["is_positive"].fillna(False)]["tokens"]
    )
    unigram_counter_negative = get_vocabulary_counter(
        subset[subset["is_negative"].fillna(False)]["tokens"]
    )

    bigram_counter_overall = build_ngram_counter(subset["tokens"], 2)
    bigram_counter_positive = build_ngram_counter(
        subset[subset["is_positive"].fillna(False)]["tokens"], 2
    )
    bigram_counter_negative = build_ngram_counter(
        subset[subset["is_negative"].fillna(False)]["tokens"], 2
    )

    top_unigrams_overall = build_frequency_table(
        unigram_counter_overall,
        config.top_n_unigrams,
        "token",
        "relative_frequency_per_1000_tokens",
    )
    top_unigrams_positive = build_frequency_table(
        unigram_counter_positive,
        config.top_n_unigrams,
        "token",
        "relative_frequency_per_1000_tokens",
    )
    top_unigrams_negative = build_frequency_table(
        unigram_counter_negative,
        config.top_n_unigrams,
        "token",
        "relative_frequency_per_1000_tokens",
    )

    top_bigrams_overall = build_frequency_table(
        bigram_counter_overall,
        config.top_n_bigrams,
        "bigram",
        "relative_frequency_per_1000_bigrams",
    )
    top_bigrams_positive = build_frequency_table(
        bigram_counter_positive,
        config.top_n_bigrams,
        "bigram",
        "relative_frequency_per_1000_bigrams",
    )
    top_bigrams_negative = build_frequency_table(
        bigram_counter_negative,
        config.top_n_bigrams,
        "bigram",
        "relative_frequency_per_1000_bigrams",
    )

    positive_df = subset[subset["is_positive"].fillna(False)].copy()
    negative_df = subset[subset["is_negative"].fillna(False)].copy()

    distinctive_positive_vs_negative = create_distinctive_terms(
        positive_df,
        negative_df,
        "positive",
        "negative",
        config.top_n_unigrams,
    )
    distinctive_negative_vs_positive = create_distinctive_terms(
        negative_df,
        positive_df,
        "negative",
        "positive",
        config.top_n_unigrams,
    )

    tables = {
        "text_corpus_overview.csv": overview,
        "text_metrics_by_polarity.csv": metrics_by_polarity,
        "text_metrics_by_playtime_band.csv": metrics_by_playtime_band,
        "top_unigrams_overall.csv": top_unigrams_overall,
        "top_unigrams_positive.csv": top_unigrams_positive,
        "top_unigrams_negative.csv": top_unigrams_negative,
        "top_bigrams_overall.csv": top_bigrams_overall,
        "top_bigrams_positive.csv": top_bigrams_positive,
        "top_bigrams_negative.csv": top_bigrams_negative,
        "distinctive_terms_positive_vs_negative.csv": distinctive_positive_vs_negative,
        "distinctive_terms_negative_vs_positive.csv": distinctive_negative_vs_positive,
    }

    for filename, table_df in tables.items():
        output_path = language_dir / filename
        export_table(table_df, output_path)
        output_paths[filename] = str(output_path)

    return output_paths


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
    print(f"[INFO] Global output dir: {paths['text_metrics_global_dir']}")
    print(f"[INFO] Per-language output dir: {paths['text_metrics_by_language_dir']}")
    print(f"[INFO] Summary JSON: {paths['summary_json']}")

    logging.info("Starting text metrics computation.")
    logging.info("Configuration file: %s", config_path)
    logging.info("Game title: %s", config.game_title)
    logging.info("App ID: %s", config.app_id)
    logging.info("Game slug: %s", config.game_slug)

    raw_df = load_cleaned_reviews(paths["input_csv"])
    raw_df = normalise_loaded_dataframe(raw_df)
    raw_df = add_band_columns(raw_df)

    logging.info("Rows loaded: %s", len(raw_df))
    logging.info("Columns loaded: %s", len(raw_df.columns))

    df_text = prepare_text_dataframe(
        raw_df,
        min_token_length=config.min_token_length,
        remove_stopwords=config.remove_stopwords,
    )

    logging.info("Rows with usable text: %s", len(df_text))
    logging.info("Languages with usable text: %s", df_text['language'].dropna().nunique())

    selected_languages, language_counts = select_languages_for_export(df_text, config)

    logging.info("Selected languages for separate output: %s", ", ".join(selected_languages) if selected_languages else "None")

    global_output_paths = export_global_text_metrics(
        df_text=df_text,
        config=config,
        paths=paths,
        selected_languages=selected_languages,
    )

    per_language_outputs: Dict[str, Dict[str, str]] = {}
    if config.export_per_language:
        for language in selected_languages:
            logging.info("Exporting per-language text metrics for: %s", language)
            per_language_outputs[str(language)] = export_language_text_metrics(
                df_text=df_text,
                config=config,
                paths=paths,
                language=str(language),
            )

    summary_payload = {
        "app_id": config.app_id,
        "game_slug": config.game_slug,
        "game_title": config.game_title,
        "generated_at_utc": pd.Timestamp.utcnow().isoformat(),
        "parameters": {
            "min_reviews_per_language": config.min_reviews_per_language,
            "min_share_per_language": config.min_share_per_language,
            "top_n_unigrams": config.top_n_unigrams,
            "top_n_bigrams": config.top_n_bigrams,
            "top_n_trigrams": config.top_n_trigrams,
            "min_token_length": config.min_token_length,
            "remove_stopwords": config.remove_stopwords,
            "use_lemmatisation": config.use_lemmatisation,
            "export_per_language": config.export_per_language,
        },
        "corpus_summary": {
            "rows_loaded_from_cleaned_csv": int(len(raw_df)),
            "rows_with_usable_text": int(len(df_text)),
            "languages_with_usable_text": int(df_text["language"].dropna().nunique()),
            "selected_languages_for_separate_output": selected_languages,
        },
        "language_selection_table": dataframe_to_json_records(language_counts),
        "global_outputs": global_output_paths,
        "per_language_outputs": per_language_outputs,
    }

    with paths["summary_json"].open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, ensure_ascii=False, indent=2)

    logging.info("Summary JSON written to: %s", paths["summary_json"])
    logging.info("Text metrics computation complete.")
    print("[INFO] Text metrics computation complete.")


if __name__ == "__main__":
    main()