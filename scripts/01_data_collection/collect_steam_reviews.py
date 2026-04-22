#!/usr/bin/env python3
"""
collect_steam_reviews.py

Generic Steam review collection script for multiple games.

This script:
- reads a per-game JSON configuration file;
- collects all accessible Steam reviews for one selected game;
- exports chunked CSV and JSON files;
- exports combined CSV and JSON files;
- writes collection metadata and logs;
- stores all outputs under data/raw/steam_reviews/<game_slug>/.

Usage examples:

    python scripts/01_data_collection/collect_steam_reviews.py \
        --config config/games/example_game.json

    python scripts/01_data_collection/collect_steam_reviews.py \
        --config config/games/example_game.json \
        --resume

Author:
    Rubén Alcaraz Martínez

Licence:
    GNU General Public License v3.0
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd
import requests


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class GameConfig:
    """Configuration values for a single game collection run."""
    app_id: int
    game_slug: str
    game_title: str
    language: str = "all"
    filter: str = "updated"
    review_type: str = "all"
    purchase_type: str = "all"
    num_per_page: int = 100
    filter_offtopic_activity: int = 0
    chunk_size: int = 1000
    sleep_seconds: float = 1.2
    request_timeout: int = 60
    max_consecutive_errors: int = 5
    user_agent: str = "Mozilla/5.0 (compatible; AcademicResearchBot/1.0; +research use)"


@dataclass
class ReviewRecord:
    """Normalised review record exported by the collection workflow."""
    recommendationid: Optional[str]
    steamid: Optional[str]
    num_games_owned: Optional[int]
    num_reviews: Optional[int]
    playtime_forever: Optional[int]
    playtime_last_two_weeks: Optional[int]
    playtime_at_review: Optional[int]
    deck_playtime_at_review: Optional[int]
    last_played: Optional[int]
    language: Optional[str]
    review: Optional[str]
    timestamp_created: Optional[int]
    timestamp_updated: Optional[int]
    voted_up: Optional[bool]
    votes_up: Optional[int]
    votes_funny: Optional[int]
    weighted_vote_score: Optional[str]
    comment_count: Optional[int]
    steam_purchase: Optional[bool]
    received_for_free: Optional[bool]
    written_during_early_access: Optional[bool]
    developer_response: Optional[str]
    timestamp_dev_responded: Optional[int]
    primarily_steam_deck: Optional[bool]


REVIEW_FIELDNAMES: List[str] = [field.name for field in fields(ReviewRecord)]


# ============================================================================
# ARGUMENT PARSING
# ============================================================================


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Collect Steam reviews for one game using a JSON configuration file."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the JSON configuration file for the target game.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the last saved cursor in the progress file when possible.",
    )
    parser.add_argument(
        "--no-combined-json",
        action="store_true",
        help="Skip export of the combined JSON file.",
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
        language=str(raw_config.get("language", "all")).strip(),
        filter=str(raw_config.get("filter", "updated")).strip(),
        review_type=str(raw_config.get("review_type", "all")).strip(),
        purchase_type=str(raw_config.get("purchase_type", "all")).strip(),
        num_per_page=int(raw_config.get("num_per_page", 100)),
        filter_offtopic_activity=int(raw_config.get("filter_offtopic_activity", 0)),
        chunk_size=int(raw_config.get("chunk_size", 1000)),
        sleep_seconds=float(raw_config.get("sleep_seconds", 1.2)),
        request_timeout=int(raw_config.get("request_timeout", 60)),
        max_consecutive_errors=int(raw_config.get("max_consecutive_errors", 5)),
        user_agent=str(
            raw_config.get(
                "user_agent",
                "Mozilla/5.0 (compatible; AcademicResearchBot/1.0; +research use)",
            )
        ).strip(),
    )


# ============================================================================
# PATH MANAGEMENT
# ============================================================================


def get_repository_root() -> Path:
    """
    Resolve the repository root assuming this file lives at:
    scripts/01_data_collection/collect_steam_reviews.py
    """
    return Path(__file__).resolve().parents[2]



def build_paths(repository_root: Path, game_slug: str) -> Dict[str, Path]:
    """Build all directory and file paths for one game."""
    raw_root = repository_root / "data" / "raw" / "steam_reviews" / game_slug
    processed_root = repository_root / "data" / "processed" / "steam_reviews" / game_slug
    results_root = repository_root / "results" / game_slug

    paths = {
        "raw_root": raw_root,
        "chunks_dir": raw_root / "chunks",
        "combined_dir": raw_root / "combined",
        "metadata_dir": raw_root / "metadata",
        "logs_dir": raw_root / "logs",
        "processed_root": processed_root,
        "cleaned_dir": processed_root / "cleaned",
        "enriched_dir": processed_root / "enriched",
        "metrics_dir": processed_root / "metrics",
        "results_root": results_root,
        "tables_dir": results_root / "tables",
        "figures_dir": results_root / "figures",
    }

    paths["progress_json"] = paths["metadata_dir"] / f"{game_slug}_progress.json"
    paths["master_index_csv"] = paths["metadata_dir"] / f"{game_slug}_master_index.csv"
    paths["combined_csv"] = paths["combined_dir"] / f"{game_slug}_reviews_all.csv"
    paths["combined_json"] = paths["combined_dir"] / f"{game_slug}_reviews_all.json"
    paths["log_file"] = paths["logs_dir"] / f"{game_slug}_collection.log"

    return paths



def ensure_directories(paths: Dict[str, Path]) -> None:
    """Create all required directories for the game."""
    directory_keys = [
        "chunks_dir",
        "combined_dir",
        "metadata_dir",
        "logs_dir",
        "cleaned_dir",
        "enriched_dir",
        "metrics_dir",
        "tables_dir",
        "figures_dir",
    ]
    for key in directory_keys:
        paths[key].mkdir(parents=True, exist_ok=True)



def cleanup_previous_collection_outputs(paths: Dict[str, Path]) -> None:
    """Remove prior raw collection outputs for a fresh non-resume run."""
    removable_patterns = {
        "chunks_dir": ["*_reviews_part_*.csv", "*_reviews_part_*.json"],
        "combined_dir": ["*.csv", "*.json"],
        "metadata_dir": ["*_progress.json", "*_master_index.csv"],
    }

    removed_count = 0
    for directory_key, patterns in removable_patterns.items():
        directory = paths[directory_key]
        if not directory.exists():
            continue
        for pattern in patterns:
            for file_path in directory.glob(pattern):
                try:
                    file_path.unlink()
                    removed_count += 1
                except OSError as exc:
                    logging.warning("Could not remove old file %s: %s", file_path, exc)

    if removed_count > 0:
        logging.info("Removed %s stale output files before fresh collection.", removed_count)


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
# HELPER CONVERSIONS
# ============================================================================


def as_int(value: Any) -> Optional[int]:
    """Safely convert a value to integer."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None



def as_str(value: Any) -> Optional[str]:
    """Safely convert a value to string."""
    if value is None:
        return None
    return str(value)



def as_bool(value: Any) -> Optional[bool]:
    """Safely convert a value to boolean."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return bool(value)


# ============================================================================
# API REQUESTS
# ============================================================================


def build_base_url(app_id: int) -> str:
    """Build the Steam reviews endpoint URL for a given application ID."""
    return f"https://store.steampowered.com/appreviews/{app_id}"



def fetch_steam_reviews(base_url: str, config: GameConfig, cursor: str) -> Dict[str, Any]:
    """Fetch one page of Steam reviews."""
    params = {
        "json": 1,
        "language": config.language,
        "filter": config.filter,
        "review_type": config.review_type,
        "purchase_type": config.purchase_type,
        "num_per_page": config.num_per_page,
        "cursor": cursor,
        "filter_offtopic_activity": config.filter_offtopic_activity,
    }

    response = requests.get(
        base_url,
        params=params,
        timeout=config.request_timeout,
        headers={
            "Accept": "application/json",
            "User-Agent": config.user_agent,
        },
    )
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("The Steam API response could not be parsed as a JSON object.")

    return data


# ============================================================================
# NORMALISATION
# ============================================================================


def normalise_review(review: Dict[str, Any]) -> ReviewRecord:
    """Normalise a raw Steam review into the repository schema."""
    author = review.get("author", {}) or {}

    return ReviewRecord(
        recommendationid=as_str(review.get("recommendationid")),
        steamid=as_str(author.get("steamid")),
        num_games_owned=as_int(author.get("num_games_owned")),
        num_reviews=as_int(author.get("num_reviews")),
        playtime_forever=as_int(author.get("playtime_forever")),
        playtime_last_two_weeks=as_int(author.get("playtime_last_two_weeks")),
        playtime_at_review=as_int(author.get("playtime_at_review")),
        deck_playtime_at_review=as_int(author.get("deck_playtime_at_review")),
        last_played=as_int(author.get("last_played")),
        language=as_str(review.get("language")),
        review=as_str(review.get("review")),
        timestamp_created=as_int(review.get("timestamp_created")),
        timestamp_updated=as_int(review.get("timestamp_updated")),
        voted_up=as_bool(review.get("voted_up")),
        votes_up=as_int(review.get("votes_up")),
        votes_funny=as_int(review.get("votes_funny")),
        weighted_vote_score=as_str(review.get("weighted_vote_score")),
        comment_count=as_int(review.get("comment_count")),
        steam_purchase=as_bool(review.get("steam_purchase")),
        received_for_free=as_bool(review.get("received_for_free")),
        written_during_early_access=as_bool(review.get("written_during_early_access")),
        developer_response=as_str(review.get("developer_response")),
        timestamp_dev_responded=as_int(review.get("timestamp_dev_responded")),
        primarily_steam_deck=as_bool(review.get("primarily_steam_deck")),
    )


# ============================================================================
# PROGRESS AND RESUME
# ============================================================================


def read_progress(progress_json: Path) -> Dict[str, Any]:
    """Read the saved progress file if it exists."""
    if not progress_json.exists():
        return {}

    with progress_json.open("r", encoding="utf-8") as handle:
        return json.load(handle)



def write_progress(progress_json: Path, payload: Dict[str, Any]) -> None:
    """Write progress metadata as JSON."""
    with progress_json.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


# ============================================================================
# EXPORT UTILITIES
# ============================================================================


def build_chunk_base_name(game_slug: str, chunk_number: int) -> str:
    """Build a zero-padded chunk file stem."""
    return f"{game_slug}_reviews_part_{chunk_number:04d}"



def export_chunk(
    game_slug: str,
    chunks_dir: Path,
    records: List[Dict[str, Any]],
    chunk_number: int,
    cumulative_total: int,
) -> Dict[str, Any]:
    """Export one chunk to CSV and JSON and return index metadata."""
    if not records:
        raise ValueError("Cannot export an empty chunk.")

    base_name = build_chunk_base_name(game_slug, chunk_number)
    json_path = chunks_dir / f"{base_name}.json"
    csv_path = chunks_dir / f"{base_name}.csv"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)

    df = pd.DataFrame(records)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    return {
        "chunk_number": chunk_number,
        "json_file": json_path.name,
        "csv_file": csv_path.name,
        "record_count": len(records),
        "cumulative_records": cumulative_total,
    }



def write_master_index(master_index_csv: Path, rows: List[Dict[str, Any]]) -> None:
    """Write the master index CSV."""
    if not rows:
        return

    fieldnames = list(rows[0].keys())
    with master_index_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)



def discover_chunk_csv_paths(chunks_dir: Path) -> List[Path]:
    """Return chunk CSV paths in numeric order."""
    return sorted(
        chunks_dir.glob("*_reviews_part_*.csv"),
        key=lambda path: int(path.stem.split("_")[-1]),
    )



def stream_chunk_rows(chunk_csv_paths: Iterable[Path]) -> Iterable[Dict[str, Any]]:
    """Yield rows from chunk CSV files in order."""
    for chunk_path in chunk_csv_paths:
        with chunk_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield row



def export_combined_dataset_from_chunks(
    chunks_dir: Path,
    combined_csv: Path,
    combined_json: Path,
    write_json: bool = True,
) -> Tuple[int, int]:
    """
    Rebuild the final combined dataset from chunk CSV files.

    Returns:
        (row_count_written, duplicate_rows_skipped)
    """
    chunk_csv_paths = discover_chunk_csv_paths(chunks_dir)
    if not chunk_csv_paths:
        logging.warning("No chunk CSV files found. Combined dataset was not rebuilt.")
        return 0, 0

    seen_ids: Set[str] = set()
    rows_written = 0
    duplicate_rows_skipped = 0

    with combined_csv.open("w", encoding="utf-8-sig", newline="") as csv_handle:
        writer = csv.DictWriter(csv_handle, fieldnames=REVIEW_FIELDNAMES)
        writer.writeheader()

        json_handle = None
        first_json_row = True
        if write_json:
            json_handle = combined_json.open("w", encoding="utf-8")
            json_handle.write("[\n")

        try:
            for row in stream_chunk_rows(chunk_csv_paths):
                recommendation_id = str(row.get("recommendationid", "")).strip()
                if not recommendation_id:
                    duplicate_rows_skipped += 1
                    continue
                if recommendation_id in seen_ids:
                    duplicate_rows_skipped += 1
                    continue

                seen_ids.add(recommendation_id)

                normalised_row = {field: row.get(field, "") for field in REVIEW_FIELDNAMES}
                writer.writerow(normalised_row)
                rows_written += 1

                if json_handle is not None:
                    if not first_json_row:
                        json_handle.write(",\n")
                    json.dump(normalised_row, json_handle, ensure_ascii=False)
                    first_json_row = False
        finally:
            if json_handle is not None:
                json_handle.write("\n]\n")
                json_handle.close()

    logging.info("Combined CSV rebuilt from chunks: %s", combined_csv)
    if write_json:
        logging.info("Combined JSON rebuilt from chunks: %s", combined_json)
    logging.info("Combined dataset rows written: %s", rows_written)
    if duplicate_rows_skipped > 0:
        logging.warning(
            "Duplicate or empty recommendation IDs skipped while rebuilding combined dataset: %s",
            duplicate_rows_skipped,
        )

    return rows_written, duplicate_rows_skipped


# ============================================================================
# EXISTING DATA HELPERS FOR RESUME
# ============================================================================


def infer_next_chunk_number(chunks_dir: Path) -> int:
    """Infer the next chunk number from existing chunk filenames."""
    existing_numbers: List[int] = []

    for file_path in chunks_dir.glob("*_reviews_part_*.csv"):
        name = file_path.stem
        try:
            number = int(name.split("_")[-1])
            existing_numbers.append(number)
        except (ValueError, IndexError):
            continue

    if not existing_numbers:
        return 1

    return max(existing_numbers) + 1



def load_existing_master_index(master_index_csv: Path) -> List[Dict[str, Any]]:
    """Load an existing master index CSV if present."""
    if not master_index_csv.exists():
        return []

    try:
        df = pd.read_csv(master_index_csv)
        return df.to_dict(orient="records")
    except Exception as exc:
        logging.warning("Could not load existing master index CSV: %s", exc)
        return []



def load_existing_state_from_chunks(paths: Dict[str, Path]) -> Tuple[Set[str], int, List[Dict[str, Any]]]:
    """
    Load seen recommendation IDs and chunk metadata from existing chunk CSV files.

    This is the source of truth for resume mode.
    """
    chunk_csv_paths = discover_chunk_csv_paths(paths["chunks_dir"])
    if not chunk_csv_paths:
        return set(), 0, load_existing_master_index(paths["master_index_csv"])

    seen_ids: Set[str] = set()
    total_rows = 0

    for chunk_path in chunk_csv_paths:
        try:
            df = pd.read_csv(chunk_path, dtype={"recommendationid": "string"}, low_memory=False)
        except Exception as exc:
            logging.warning("Could not read chunk file during resume initialisation: %s | %s", chunk_path, exc)
            continue

        if "recommendationid" not in df.columns:
            logging.warning("Chunk file missing recommendationid column: %s", chunk_path)
            continue

        ids = (
            df["recommendationid"]
            .dropna()
            .astype(str)
            .str.strip()
        )
        ids = [value for value in ids.tolist() if value]
        seen_ids.update(ids)
        total_rows += len(ids)

    master_index_rows = load_existing_master_index(paths["master_index_csv"])
    return seen_ids, total_rows, master_index_rows



def initialise_resume_state(
    resume: bool,
    paths: Dict[str, Path],
) -> Tuple[str, int, int, Set[str], List[Dict[str, Any]]]:
    """
    Initialise resume state.

    Returns:
        cursor,
        starting_chunk_number,
        existing_total_records,
        seen_recommendation_ids,
        master_index_rows
    """
    if not resume:
        return "*", 1, 0, set(), []

    progress = read_progress(paths["progress_json"])
    cursor = str(progress.get("current_cursor") or progress.get("final_cursor") or "*")
    next_chunk_number = infer_next_chunk_number(paths["chunks_dir"])
    seen_recommendation_ids, existing_total_records, master_index_rows = load_existing_state_from_chunks(paths)

    logging.info("Resume mode enabled.")
    logging.info("Loaded %s previously exported recommendation IDs from chunk files.", existing_total_records)
    logging.info("Resuming from cursor: %s", cursor)
    logging.info("Next chunk number will be: %s", next_chunk_number)

    return cursor, next_chunk_number, existing_total_records, seen_recommendation_ids, master_index_rows


# ============================================================================
# CORE COLLECTION LOGIC
# ============================================================================


def build_progress_payload(
    config: GameConfig,
    page: int,
    master_index_rows: List[Dict[str, Any]],
    total_exported: int,
    current_cursor: str,
    last_query_summary: Dict[str, Any],
    last_non_empty_query_summary: Dict[str, Any],
    collection_finished: bool,
    expected_total_reviews: Optional[int],
    final_total_unique_reviews: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a consistent progress payload."""
    payload: Dict[str, Any] = {
        "app_id": config.app_id,
        "game_slug": config.game_slug,
        "game_title": config.game_title,
        "pages_downloaded_in_current_run": page,
        "chunks_exported": len(master_index_rows),
        "records_exported": total_exported,
        "current_cursor": current_cursor,
        "last_query_summary": last_query_summary,
        "last_non_empty_query_summary": last_non_empty_query_summary,
        "expected_total_reviews_from_api": expected_total_reviews,
        "collection_finished": collection_finished,
        "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
    }

    if final_total_unique_reviews is not None:
        payload["final_total_unique_reviews"] = final_total_unique_reviews
        payload["final_cursor"] = current_cursor
        if expected_total_reviews is not None:
            payload["difference_vs_api_total_reviews"] = final_total_unique_reviews - expected_total_reviews

    return payload



def collect_reviews(
    config: GameConfig,
    paths: Dict[str, Path],
    resume: bool,
    write_combined_json: bool,
) -> None:
    """Collect all accessible reviews for the selected game."""
    base_url = build_base_url(config.app_id)

    cursor, chunk_number, existing_total, seen_recommendation_ids, master_index_rows = initialise_resume_state(
        resume=resume,
        paths=paths,
    )

    current_chunk: List[Dict[str, Any]] = []
    previous_cursor: Optional[str] = None
    page = 0
    total_exported = existing_total
    consecutive_errors = 0
    last_query_summary: Dict[str, Any] = {}
    last_non_empty_query_summary: Dict[str, Any] = {}
    expected_total_reviews: Optional[int] = None

    while True:
        page += 1
        logging.info("Downloading page %s for '%s'...", page, config.game_title)

        try:
            data = fetch_steam_reviews(base_url=base_url, config=config, cursor=cursor)
            consecutive_errors = 0
        except Exception as exc:
            consecutive_errors += 1
            logging.exception("Request failed on page %s: %s", page, exc)

            if consecutive_errors >= config.max_consecutive_errors:
                logging.error("Stopping after too many consecutive errors.")
                break

            time.sleep(config.sleep_seconds * 2)
            page -= 1
            continue

        if data.get("success") != 1:
            logging.error("Steam API did not return success=1.")
            break

        reviews = data.get("reviews", [])
        current_query_summary = data.get("query_summary", {}) or {}
        last_query_summary = current_query_summary

        if expected_total_reviews is None and isinstance(current_query_summary.get("total_reviews"), (int, float, str)):
            expected_total_reviews = as_int(current_query_summary.get("total_reviews"))
            if expected_total_reviews is not None:
                logging.info("API query_summary.total_reviews reported on first page: %s", expected_total_reviews)

        if reviews:
            last_non_empty_query_summary = current_query_summary

        logging.info("Reviews received on this page: %s", len(reviews))

        if not reviews:
            logging.info("No more reviews returned. Pagination finished.")
            break

        new_this_page = 0

        for review in reviews:
            recommendation_id = str(review.get("recommendationid", "")).strip()
            if not recommendation_id:
                continue

            if recommendation_id in seen_recommendation_ids:
                continue

            seen_recommendation_ids.add(recommendation_id)
            record = asdict(normalise_review(review))
            current_chunk.append(record)
            new_this_page += 1

            if len(current_chunk) >= config.chunk_size:
                new_cumulative_total = total_exported + len(current_chunk)
                index_row = export_chunk(
                    game_slug=config.game_slug,
                    chunks_dir=paths["chunks_dir"],
                    records=current_chunk,
                    chunk_number=chunk_number,
                    cumulative_total=new_cumulative_total,
                )
                master_index_rows.append(index_row)
                write_master_index(paths["master_index_csv"], master_index_rows)

                total_exported = new_cumulative_total

                logging.info(
                    "Chunk %s exported with %s reviews. Total exported to chunks: %s",
                    chunk_number,
                    len(current_chunk),
                    total_exported,
                )

                write_progress(
                    paths["progress_json"],
                    build_progress_payload(
                        config=config,
                        page=page,
                        master_index_rows=master_index_rows,
                        total_exported=total_exported,
                        current_cursor=cursor,
                        last_query_summary=last_query_summary,
                        last_non_empty_query_summary=last_non_empty_query_summary,
                        collection_finished=False,
                        expected_total_reviews=expected_total_reviews,
                    ),
                )

                current_chunk = []
                chunk_number += 1

        logging.info("New unique reviews added on this page: %s", new_this_page)
        logging.info("Reviews currently in memory chunk: %s", len(current_chunk))
        logging.info("Unique reviews known so far: %s", len(seen_recommendation_ids))

        next_cursor = data.get("cursor")
        if not isinstance(next_cursor, str) or not next_cursor.strip():
            logging.info("No valid cursor returned. Pagination finished.")
            break

        if next_cursor == cursor or next_cursor == previous_cursor:
            logging.info("Cursor stopped advancing. Pagination finished.")
            break

        previous_cursor = cursor
        cursor = next_cursor

        time.sleep(config.sleep_seconds)

    if current_chunk:
        new_cumulative_total = total_exported + len(current_chunk)
        index_row = export_chunk(
            game_slug=config.game_slug,
            chunks_dir=paths["chunks_dir"],
            records=current_chunk,
            chunk_number=chunk_number,
            cumulative_total=new_cumulative_total,
        )
        master_index_rows.append(index_row)
        write_master_index(paths["master_index_csv"], master_index_rows)
        total_exported = new_cumulative_total

        logging.info(
            "Final chunk %s exported with %s reviews. Final chunk-export total: %s",
            chunk_number,
            len(current_chunk),
            total_exported,
        )

    final_total_unique_reviews, duplicate_rows_skipped = export_combined_dataset_from_chunks(
        chunks_dir=paths["chunks_dir"],
        combined_csv=paths["combined_csv"],
        combined_json=paths["combined_json"],
        write_json=write_combined_json,
    )

    write_progress(
        paths["progress_json"],
        build_progress_payload(
            config=config,
            page=page,
            master_index_rows=master_index_rows,
            total_exported=final_total_unique_reviews,
            current_cursor=cursor,
            last_query_summary=last_query_summary,
            last_non_empty_query_summary=last_non_empty_query_summary,
            collection_finished=True,
            expected_total_reviews=expected_total_reviews,
            final_total_unique_reviews=final_total_unique_reviews,
        ),
    )

    logging.info("Collection complete.")
    logging.info("Game title: %s", config.game_title)
    logging.info("App ID: %s", config.app_id)
    logging.info("Game slug: %s", config.game_slug)
    logging.info("Total unique reviews exported: %s", final_total_unique_reviews)
    logging.info("Duplicates skipped while rebuilding combined dataset: %s", duplicate_rows_skipped)
    if expected_total_reviews is not None:
        logging.info(
            "API query_summary.total_reviews: %s | final combined rows: %s | difference: %s",
            expected_total_reviews,
            final_total_unique_reviews,
            final_total_unique_reviews - expected_total_reviews,
        )
    logging.info("Chunks directory: %s", paths["chunks_dir"])
    logging.info("Combined CSV: %s", paths["combined_csv"])
    logging.info("Combined JSON: %s", paths["combined_json"])
    logging.info("Master index CSV: %s", paths["master_index_csv"])
    logging.info("Progress JSON: %s", paths["progress_json"])


# ============================================================================
# MAIN
# ============================================================================


def main() -> None:
    """Main entry point."""
    args = parse_arguments()

    config_path = Path(args.config).resolve()
    config = load_game_config(config_path)

    repository_root = get_repository_root()
    paths = build_paths(repository_root=repository_root, game_slug=config.game_slug)
    ensure_directories(paths)
    configure_logging(paths["log_file"])

    logging.info("Starting Steam review collection.")
    logging.info("Configuration file: %s", config_path)
    logging.info("Game title: %s", config.game_title)
    logging.info("App ID: %s", config.app_id)
    logging.info("Game slug: %s", config.game_slug)

    if args.resume:
        logging.info("Collection mode: resume")
    else:
        logging.info("Collection mode: fresh run")
        cleanup_previous_collection_outputs(paths)

    collect_reviews(
        config=config,
        paths=paths,
        resume=args.resume,
        write_combined_json=not args.no_combined_json,
    )


if __name__ == "__main__":
    main()
