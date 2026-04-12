#!/usr/bin/env python3
"""
create_word_clouds.py

Create unigram, bigram, and trigram word clouds from the cleaned Steam reviews
dataset for one selected game.

This script:
- reads a per-game JSON configuration file;
- loads the cleaned review dataset for one selected game;
- optionally filters by language;
- tokenises the review text;
- builds unigram, bigram, and trigram frequency dictionaries;
- generates three word-cloud PNG files;
- exports the frequencies used for each cloud as CSV files;
- writes a JSON summary and a log.

Usage example:

    python scripts/04_visualisation/create_word_clouds.py \
        --config config/games/game_01.json

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
from typing import Any, Dict, Iterable, List, Sequence

import pandas as pd
from wordcloud import WordCloud


# ============================================================================
# CONSTANTS
# ============================================================================

TOKEN_PATTERN = re.compile(r"\b[\w'-]+\b", flags=re.UNICODE)

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
    "german": {
        "der", "die", "das", "ein", "eine", "und", "oder", "aber", "wenn", "dann",
        "zu", "von", "in", "im", "am", "für", "mit", "ohne", "ist", "sind", "war",
        "waren", "sein", "ich", "du", "er", "sie", "wir", "ihr", "mein", "dein",
        "nicht", "ja", "so", "sehr", "nur", "spiel", "spiele"
    },
    "french": {
        "le", "la", "les", "un", "une", "des", "et", "ou", "mais", "si", "de", "du",
        "dans", "sur", "à", "au", "aux", "pour", "avec", "sans", "est", "sont",
        "était", "être", "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
        "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses", "pas", "oui",
        "très", "plus", "jeu", "jeux"
    },
    "italian": {
        "il", "lo", "la", "i", "gli", "le", "un", "una", "e", "o", "ma", "se", "di",
        "del", "della", "in", "nel", "sul", "per", "con", "senza", "è", "sono", "era",
        "essere", "io", "tu", "lui", "lei", "noi", "voi", "loro", "mio", "mia", "tuo",
        "tua", "suo", "sua", "non", "sì", "molto", "più", "gioco", "giochi"
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
    "russian": {
        "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
        "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
        "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "еще", "нет",
        "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли", "если",
        "или", "ни", "быть", "был", "него", "до", "вас", "игра", "игры"
    },
}


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class GameConfig:
    """Configuration values for one word-cloud generation run."""
    app_id: int
    game_slug: str
    game_title: str
    target_language: str = "all"
    min_token_length: int = 2
    remove_stopwords: bool = True
    max_words_unigrams: int = 200
    max_words_bigrams: int = 150
    max_words_trigrams: int = 100
    min_frequency_unigrams: int = 2
    min_frequency_bigrams: int = 2
    min_frequency_trigrams: int = 2
    width: int = 1800
    height: int = 1200
    background_colour: str = "white"
    collocations: bool = False


# ============================================================================
# ARGUMENT PARSING
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Create unigram, bigram, and trigram word clouds from cleaned Steam reviews."
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

    wc_cfg = raw_config.get("word_cloud", {})

    return GameConfig(
        app_id=int(raw_config["app_id"]),
        game_slug=str(raw_config["game_slug"]).strip(),
        game_title=str(raw_config["game_title"]).strip(),
        target_language=str(wc_cfg.get("target_language", "all")).strip().lower(),
        min_token_length=int(wc_cfg.get("min_token_length", 2)),
        remove_stopwords=bool(wc_cfg.get("remove_stopwords", True)),
        max_words_unigrams=int(wc_cfg.get("max_words_unigrams", 200)),
        max_words_bigrams=int(wc_cfg.get("max_words_bigrams", 150)),
        max_words_trigrams=int(wc_cfg.get("max_words_trigrams", 100)),
        min_frequency_unigrams=int(wc_cfg.get("min_frequency_unigrams", 2)),
        min_frequency_bigrams=int(wc_cfg.get("min_frequency_bigrams", 2)),
        min_frequency_trigrams=int(wc_cfg.get("min_frequency_trigrams", 2)),
        width=int(wc_cfg.get("width", 1800)),
        height=int(wc_cfg.get("height", 1200)),
        background_colour=str(wc_cfg.get("background_colour", "white")).strip(),
        collocations=bool(wc_cfg.get("collocations", False)),
    )


# ============================================================================
# PATH MANAGEMENT
# ============================================================================

def get_repository_root() -> Path:
    """
    Resolve the repository root assuming this file lives at:
    scripts/04_visualisation/create_word_clouds.py
    """
    return Path(__file__).resolve().parents[2]


def build_paths(repository_root: Path, config: GameConfig) -> Dict[str, Path]:
    """Build all required input and output paths."""
    processed_root = repository_root / "data" / "processed" / "steam_reviews" / config.game_slug
    results_root = repository_root / "results" / config.game_slug

    paths = {
        "cleaned_dir": processed_root / "cleaned",
        "metrics_dir": processed_root / "metrics",
        "results_root": results_root,
        "figures_dir": results_root / "figures",
        "word_cloud_dir": results_root / "figures" / "word_cloud",
    }

    paths["input_csv"] = paths["cleaned_dir"] / f"{config.game_slug}_reviews_cleaned.csv"
    paths["summary_json"] = paths["metrics_dir"] / f"{config.game_slug}_word_cloud_summary.json"
    paths["analysis_log"] = paths["metrics_dir"] / f"{config.game_slug}_word_cloud.log"

    paths["unigram_png"] = paths["word_cloud_dir"] / f"{config.game_slug}_wordcloud_unigrams.png"
    paths["bigram_png"] = paths["word_cloud_dir"] / f"{config.game_slug}_wordcloud_bigrams.png"
    paths["trigram_png"] = paths["word_cloud_dir"] / f"{config.game_slug}_wordcloud_trigrams.png"

    paths["unigram_csv"] = paths["word_cloud_dir"] / f"{config.game_slug}_wordcloud_unigrams_frequencies.csv"
    paths["bigram_csv"] = paths["word_cloud_dir"] / f"{config.game_slug}_wordcloud_bigrams_frequencies.csv"
    paths["trigram_csv"] = paths["word_cloud_dir"] / f"{config.game_slug}_wordcloud_trigrams_frequencies.csv"

    return paths


def ensure_directories(paths: Dict[str, Path]) -> None:
    """Create required output directories."""
    for key in ["metrics_dir", "figures_dir", "word_cloud_dir"]:
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
# TEXT PREPARATION
# ============================================================================

def get_language_stopwords(language: str) -> set[str]:
    """Return stopwords for the requested language, if available."""
    return STOPWORDS_BY_LANGUAGE.get(str(language).strip().lower(), set())


def tokenise_text(
    text: str,
    language: str,
    min_token_length: int,
    remove_stopwords: bool,
) -> List[str]:
    """Tokenise text into a cleaned list of tokens."""
    tokens = TOKEN_PATTERN.findall(text.lower())
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


def prepare_text_subset(df: pd.DataFrame, config: GameConfig) -> pd.DataFrame:
    """Prepare the subset used for word-cloud generation."""
    temp = df.copy()

    if "language" not in temp.columns:
        temp["language"] = "unknown"

    temp["language"] = temp["language"].fillna("unknown").astype("string").str.lower()
    temp["review"] = temp["review"].fillna(pd.NA).astype("string")

    if config.target_language != "all":
        temp = temp[temp["language"] == config.target_language].copy()

    temp = temp[temp["review"].notna()].copy()
    temp["review"] = temp["review"].str.strip()
    temp = temp[temp["review"] != ""].copy()

    temp["tokens"] = temp.apply(
        lambda row: tokenise_text(
            text=str(row["review"]),
            language=str(row["language"]),
            min_token_length=config.min_token_length,
            remove_stopwords=config.remove_stopwords,
        ),
        axis=1,
    )
    temp["token_count_for_word_cloud"] = temp["tokens"].map(len)
    temp = temp[temp["token_count_for_word_cloud"] > 0].copy()

    return temp.reset_index(drop=True)


# ============================================================================
# N-GRAMS
# ============================================================================

def build_ngrams(tokens: Sequence[str], n: int) -> List[str]:
    """Build n-grams from a token list."""
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def build_counter(token_lists: Iterable[List[str]]) -> Counter:
    """Build a unigram counter."""
    counter: Counter = Counter()
    for tokens in token_lists:
        counter.update(tokens)
    return counter


def build_ngram_counter(token_lists: Iterable[List[str]], n: int) -> Counter:
    """Build a bigram or trigram counter."""
    counter: Counter = Counter()
    for tokens in token_lists:
        counter.update(build_ngrams(tokens, n))
    return counter


def filter_counter(counter: Counter, min_frequency: int, max_words: int) -> Counter:
    """Filter a counter by minimum frequency and maximum number of entries."""
    items = [(term, freq) for term, freq in counter.items() if freq >= min_frequency]
    items.sort(key=lambda item: (-item[1], item[0]))
    return Counter(dict(items[:max_words]))


# ============================================================================
# EXPORT HELPERS
# ============================================================================

def counter_to_dataframe(counter: Counter, label: str) -> pd.DataFrame:
    """Convert a counter to a ranked dataframe."""
    rows = []
    for rank, (term, frequency) in enumerate(counter.most_common(), start=1):
        rows.append(
            {
                "rank": rank,
                label: term,
                "frequency": frequency,
            }
        )
    return pd.DataFrame(rows)


def save_word_cloud(
    frequencies: Dict[str, int],
    output_path: Path,
    config: GameConfig,
) -> None:
    """Generate and save one word cloud image."""
    if not frequencies:
        raise ValueError(f"No frequencies available for word cloud: {output_path.name}")

    wordcloud = WordCloud(
        width=config.width,
        height=config.height,
        background_color=config.background_colour,
        collocations=config.collocations,
    ).generate_from_frequencies(frequencies)

    wordcloud.to_file(str(output_path))


def to_serialisable(value: Any) -> Any:
    """Convert values to JSON-safe Python values."""
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    if isinstance(value, (int, str, bool)):
        return value
    return str(value)


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
    print(f"[INFO] Output directory: {paths['word_cloud_dir']}")
    print(f"[INFO] Summary JSON: {paths['summary_json']}")

    logging.info("Starting word-cloud generation.")
    logging.info("Game title: %s", config.game_title)
    logging.info("App ID: %s", config.app_id)
    logging.info("Game slug: %s", config.game_slug)
    logging.info("Target language: %s", config.target_language)

    raw_df = load_cleaned_reviews(paths["input_csv"])
    text_df = prepare_text_subset(raw_df, config)

    if text_df.empty:
        raise ValueError("No usable reviews found for word-cloud generation.")

    logging.info("Rows loaded from cleaned dataset: %s", len(raw_df))
    logging.info("Rows used for word clouds: %s", len(text_df))

    unigram_counter = build_counter(text_df["tokens"])
    bigram_counter = build_ngram_counter(text_df["tokens"], 2)
    trigram_counter = build_ngram_counter(text_df["tokens"], 3)

    unigram_counter = filter_counter(
        counter=unigram_counter,
        min_frequency=config.min_frequency_unigrams,
        max_words=config.max_words_unigrams,
    )
    bigram_counter = filter_counter(
        counter=bigram_counter,
        min_frequency=config.min_frequency_bigrams,
        max_words=config.max_words_bigrams,
    )
    trigram_counter = filter_counter(
        counter=trigram_counter,
        min_frequency=config.min_frequency_trigrams,
        max_words=config.max_words_trigrams,
    )

    save_word_cloud(dict(unigram_counter), paths["unigram_png"], config)
    save_word_cloud(dict(bigram_counter), paths["bigram_png"], config)
    save_word_cloud(dict(trigram_counter), paths["trigram_png"], config)

    counter_to_dataframe(unigram_counter, "unigram").to_csv(
        paths["unigram_csv"], index=False, encoding="utf-8-sig"
    )
    counter_to_dataframe(bigram_counter, "bigram").to_csv(
        paths["bigram_csv"], index=False, encoding="utf-8-sig"
    )
    counter_to_dataframe(trigram_counter, "trigram").to_csv(
        paths["trigram_csv"], index=False, encoding="utf-8-sig"
    )

    summary_payload = {
        "app_id": config.app_id,
        "game_slug": config.game_slug,
        "game_title": config.game_title,
        "generated_at_utc": pd.Timestamp.utcnow().isoformat(),
        "parameters": {
            "target_language": config.target_language,
            "min_token_length": config.min_token_length,
            "remove_stopwords": config.remove_stopwords,
            "max_words_unigrams": config.max_words_unigrams,
            "max_words_bigrams": config.max_words_bigrams,
            "max_words_trigrams": config.max_words_trigrams,
            "min_frequency_unigrams": config.min_frequency_unigrams,
            "min_frequency_bigrams": config.min_frequency_bigrams,
            "min_frequency_trigrams": config.min_frequency_trigrams,
            "width": config.width,
            "height": config.height,
            "background_colour": config.background_colour,
            "collocations": config.collocations,
        },
        "corpus_summary": {
            "rows_in_cleaned_dataset": int(len(raw_df)),
            "rows_used_for_word_clouds": int(len(text_df)),
            "total_tokens_used": int(text_df["token_count_for_word_cloud"].sum()),
        },
        "outputs": {
            "unigram_png": str(paths["unigram_png"]),
            "bigram_png": str(paths["bigram_png"]),
            "trigram_png": str(paths["trigram_png"]),
            "unigram_csv": str(paths["unigram_csv"]),
            "bigram_csv": str(paths["bigram_csv"]),
            "trigram_csv": str(paths["trigram_csv"]),
        },
        "frequency_counts": {
            "unigrams": int(len(unigram_counter)),
            "bigrams": int(len(bigram_counter)),
            "trigrams": int(len(trigram_counter)),
        },
    }

    with paths["summary_json"].open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, ensure_ascii=False, indent=2)

    logging.info("Word clouds created successfully.")
    logging.info("Unigram PNG: %s", paths["unigram_png"])
    logging.info("Bigram PNG: %s", paths["bigram_png"])
    logging.info("Trigram PNG: %s", paths["trigram_png"])
    logging.info("Summary JSON: %s", paths["summary_json"])
    print("[INFO] Word-cloud generation complete.")


if __name__ == "__main__":
    main()