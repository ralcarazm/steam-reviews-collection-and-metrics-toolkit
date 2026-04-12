#!/usr/bin/env python3
"""
run_pipeline.py

Repository pipeline runner for one selected game configuration.

This script:
- reads a per-game JSON configuration file;
- resolves the repository root;
- executes the repository scripts in the expected order;
- supports skipping selected stages;
- captures stdout, stderr, return codes, and timestamps;
- generates a pipeline log;
- generates an output manifest JSON file describing expected and existing outputs.

Usage examples:

    python scripts/run_pipeline.py --config config/games/game_02.json

    python scripts/run_pipeline.py --config config/games/game_02.json --skip-collection

    python scripts/run_pipeline.py --config config/games/game_02.json --skip-figures --skip-wordcloud

Author:
    Rubén Alcaraz Martínez

Licence:
    GNU General Public License v3.0
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class GameConfig:
    """Configuration values required by the pipeline runner."""
    app_id: int
    game_slug: str
    game_title: str


@dataclass
class StageSpec:
    """Definition of one pipeline stage."""
    stage_id: str
    stage_label: str
    script_path: str
    enabled: bool = True


# ============================================================================
# ARGUMENT PARSING
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the full Steam reviews collection and analysis pipeline for one game."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the JSON configuration file for the target game.",
    )
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python executable to use for subprocess calls. Defaults to the current interpreter.",
    )

    parser.add_argument("--skip-collection", action="store_true", help="Skip data collection stage.")
    parser.add_argument("--skip-preparation", action="store_true", help="Skip data preparation stage.")
    parser.add_argument("--skip-basic", action="store_true", help="Skip basic metrics stage.")
    parser.add_argument("--skip-temporal", action="store_true", help="Skip temporal metrics stage.")
    parser.add_argument("--skip-text", action="store_true", help="Skip text metrics stage.")
    parser.add_argument("--skip-emotion", action="store_true", help="Skip emotion metrics stage.")
    parser.add_argument("--skip-theme", action="store_true", help="Skip theme metrics stage.")
    parser.add_argument("--skip-figures", action="store_true", help="Skip Excel figure generation stage.")
    parser.add_argument("--skip-wordcloud", action="store_true", help="Skip word-cloud generation stage.")
    parser.add_argument("--skip-validation", action="store_true", help="Skip validation stage.")

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue executing later stages even if one stage fails.",
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
    scripts/run_pipeline.py
    """
    return Path(__file__).resolve().parents[1]


def build_paths(repository_root: Path, config: GameConfig) -> Dict[str, Path]:
    """Build all required repository paths."""
    raw_root = repository_root / "data" / "raw" / "steam_reviews" / config.game_slug
    processed_root = repository_root / "data" / "processed" / "steam_reviews" / config.game_slug
    results_root = repository_root / "results" / config.game_slug

    metrics_dir = processed_root / "metrics"

    return {
        "repository_root": repository_root,
        "raw_root": raw_root,
        "processed_root": processed_root,
        "results_root": results_root,
        "metrics_dir": metrics_dir,
        "pipeline_log": metrics_dir / f"{config.game_slug}_pipeline.log",
        "manifest_json": metrics_dir / f"{config.game_slug}_output_manifest.json",
        "pipeline_summary_json": metrics_dir / f"{config.game_slug}_pipeline_summary.json",
    }


def ensure_directories(paths: Dict[str, Path]) -> None:
    """Create required directories for pipeline metadata."""
    paths["metrics_dir"].mkdir(parents=True, exist_ok=True)


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
# STAGE DEFINITIONS
# ============================================================================

def get_stage_specs(args: argparse.Namespace) -> List[StageSpec]:
    """Return the ordered list of pipeline stages."""
    return [
        StageSpec(
            stage_id="collection",
            stage_label="Data collection",
            script_path="scripts/01_data_collection/collect_steam_reviews.py",
            enabled=not args.skip_collection,
        ),
        StageSpec(
            stage_id="preparation",
            stage_label="Data preparation",
            script_path="scripts/02_data_preparation/prepare_reviews.py",
            enabled=not args.skip_preparation,
        ),
        StageSpec(
            stage_id="basic_metrics",
            stage_label="Basic descriptive metrics",
            script_path="scripts/03_analysis/compute_basic_metrics.py",
            enabled=not args.skip_basic,
        ),
        StageSpec(
            stage_id="temporal_metrics",
            stage_label="Temporal metrics",
            script_path="scripts/03_analysis/compute_temporal_metrics.py",
            enabled=not args.skip_temporal,
        ),
        StageSpec(
            stage_id="text_metrics",
            stage_label="Text metrics",
            script_path="scripts/03_analysis/compute_text_metrics.py",
            enabled=not args.skip_text,
        ),
        StageSpec(
            stage_id="emotion_metrics",
            stage_label="Emotion metrics",
            script_path="scripts/03_analysis/compute_emotion_metrics.py",
            enabled=not args.skip_emotion,
        ),
        StageSpec(
            stage_id="theme_metrics",
            stage_label="Theme metrics",
            script_path="scripts/03_analysis/compute_theme_metrics.py",
            enabled=not args.skip_theme,
        ),
        StageSpec(
            stage_id="excel_figures",
            stage_label="Excel figure generation",
            script_path="scripts/04_visualisation/create_excel_figures.py",
            enabled=not args.skip_figures,
        ),
        StageSpec(
            stage_id="word_cloud",
            stage_label="Word-cloud generation",
            script_path="scripts/04_visualisation/create_word_clouds.py",
            enabled=not args.skip_wordcloud,
        ),
        StageSpec(
            stage_id="validation",
            stage_label="Output validation",
            script_path="scripts/validate_outputs.py",
            enabled=not args.skip_validation,
        ),
    ]


# ============================================================================
# SUBPROCESS EXECUTION
# ============================================================================

def utc_now_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def run_stage(
    stage: StageSpec,
    config_path: Path,
    python_executable: str,
    repository_root: Path,
) -> Dict[str, Any]:
    """Execute one stage via subprocess."""
    script_full_path = repository_root / stage.script_path
    if not script_full_path.exists():
        return {
            "stage_id": stage.stage_id,
            "stage_label": stage.stage_label,
            "script_path": str(script_full_path),
            "enabled": stage.enabled,
            "status": "failed",
            "return_code": None,
            "started_at_utc": utc_now_iso(),
            "finished_at_utc": utc_now_iso(),
            "stdout": "",
            "stderr": f"Script not found: {script_full_path}",
        }

    command = [
        python_executable,
        str(script_full_path),
        "--config",
        str(config_path),
    ]

    started_at = utc_now_iso()
    logging.info("Starting stage: %s", stage.stage_label)
    logging.info("Command: %s", " ".join(command))

    completed = subprocess.run(
        command,
        cwd=repository_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    finished_at = utc_now_iso()
    status = "success" if completed.returncode == 0 else "failed"

    if completed.stdout.strip():
        logging.info("Stage stdout (%s):\n%s", stage.stage_id, completed.stdout.strip())
    if completed.stderr.strip():
        if completed.returncode == 0:
            logging.warning("Stage stderr (%s):\n%s", stage.stage_id, completed.stderr.strip())
        else:
            logging.error("Stage stderr (%s):\n%s", stage.stage_id, completed.stderr.strip())

    logging.info("Finished stage: %s | status=%s | return_code=%s", stage.stage_label, status, completed.returncode)

    return {
        "stage_id": stage.stage_id,
        "stage_label": stage.stage_label,
        "script_path": str(script_full_path),
        "enabled": stage.enabled,
        "status": status,
        "return_code": completed.returncode,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


# ============================================================================
# OUTPUT MANIFEST
# ============================================================================

def file_record(path: Path) -> Dict[str, Any]:
    """Create a manifest record for one file or directory."""
    exists = path.exists()
    record: Dict[str, Any] = {
        "path": str(path),
        "exists": exists,
        "is_file": path.is_file() if exists else False,
        "is_dir": path.is_dir() if exists else False,
    }

    if exists and path.is_file():
        record["size_bytes"] = path.stat().st_size
        record["modified_at_utc"] = datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat()
    elif exists and path.is_dir():
        try:
            record["entry_count"] = len(list(path.iterdir()))
        except Exception:
            record["entry_count"] = None

    return record


def gather_directory_listing(directory: Path, recursive: bool = False) -> List[Dict[str, Any]]:
    """Gather file records for a directory."""
    if not directory.exists() or not directory.is_dir():
        return []

    paths = sorted(directory.rglob("*") if recursive else directory.glob("*"))
    records: List[Dict[str, Any]] = []
    for path in paths:
        if path.is_file():
            records.append(file_record(path))
    return records


def build_output_manifest(paths: Dict[str, Path], config: GameConfig, stage_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a structured output manifest for the whole pipeline."""
    repository_root = paths["repository_root"]
    game_slug = config.game_slug

    raw_root = repository_root / "data" / "raw" / "steam_reviews" / game_slug
    processed_root = repository_root / "data" / "processed" / "steam_reviews" / game_slug
    results_root = repository_root / "results" / game_slug

    important_outputs = {
        "raw_combined_csv": raw_root / "combined" / f"{game_slug}_reviews_all.csv",
        "cleaned_csv": processed_root / "cleaned" / f"{game_slug}_reviews_cleaned.csv",
        "basic_metrics_summary_json": processed_root / "metrics" / f"{game_slug}_basic_metrics_summary.json",
        "temporal_metrics_summary_json": processed_root / "metrics" / f"{game_slug}_temporal_metrics_summary.json",
        "text_metrics_summary_json": processed_root / "metrics" / f"{game_slug}_text_metrics_summary.json",
        "emotion_metrics_summary_json": processed_root / "metrics" / f"{game_slug}_emotion_metrics_summary.json",
        "theme_metrics_summary_json": processed_root / "metrics" / f"{game_slug}_theme_metrics_summary.json",
        "figures_summary_json": processed_root / "metrics" / f"{game_slug}_figures_summary.json",
        "word_cloud_summary_json": processed_root / "metrics" / f"{game_slug}_word_cloud_summary.json",
        "validation_summary_json": processed_root / "metrics" / f"{game_slug}_validation_summary.json",
        "figure_index_csv": results_root / "figures" / f"{game_slug}_figure_index.csv",
    }

    manifest = {
        "app_id": config.app_id,
        "game_slug": config.game_slug,
        "game_title": config.game_title,
        "generated_at_utc": utc_now_iso(),
        "roots": {
            "raw_root": str(raw_root),
            "processed_root": str(processed_root),
            "results_root": str(results_root),
        },
        "stage_results": [
            {
                key: value
                for key, value in stage_result.items()
                if key not in {"stdout", "stderr"}
            }
            for stage_result in stage_results
        ],
        "important_outputs": {
            name: file_record(path)
            for name, path in important_outputs.items()
        },
        "directories": {
            "raw_combined": gather_directory_listing(raw_root / "combined"),
            "raw_chunks": gather_directory_listing(raw_root / "chunks"),
            "raw_metadata": gather_directory_listing(raw_root / "metadata"),
            "raw_logs": gather_directory_listing(raw_root / "logs"),
            "processed_cleaned": gather_directory_listing(processed_root / "cleaned"),
            "processed_enriched": gather_directory_listing(processed_root / "enriched"),
            "processed_metrics": gather_directory_listing(processed_root / "metrics"),
            "results_tables": gather_directory_listing(results_root / "tables", recursive=True),
            "results_figures": gather_directory_listing(results_root / "figures", recursive=True),
        },
    }

    return manifest


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
    configure_logging(paths["pipeline_log"])

    print(f"[INFO] Loading configuration: {config_path}")
    print(f"[INFO] Repository root: {repository_root}")
    print(f"[INFO] Game slug: {config.game_slug}")
    print(f"[INFO] Pipeline log: {paths['pipeline_log']}")
    print(f"[INFO] Output manifest: {paths['manifest_json']}")

    logging.info("Starting pipeline run.")
    logging.info("Game title: %s", config.game_title)
    logging.info("App ID: %s", config.app_id)
    logging.info("Game slug: %s", config.game_slug)
    logging.info("Python executable: %s", args.python_executable)
    logging.info("Continue on error: %s", args.continue_on_error)

    stage_specs = get_stage_specs(args)
    stage_results: List[Dict[str, Any]] = []

    for stage in stage_specs:
        if not stage.enabled:
            logging.info("Skipping stage: %s", stage.stage_label)
            stage_results.append(
                {
                    "stage_id": stage.stage_id,
                    "stage_label": stage.stage_label,
                    "script_path": str(repository_root / stage.script_path),
                    "enabled": False,
                    "status": "skipped",
                    "return_code": None,
                    "started_at_utc": None,
                    "finished_at_utc": None,
                    "stdout": "",
                    "stderr": "",
                }
            )
            continue

        result = run_stage(
            stage=stage,
            config_path=config_path,
            python_executable=args.python_executable,
            repository_root=repository_root,
        )
        stage_results.append(result)

        if result["status"] != "success" and not args.continue_on_error:
            logging.error("Pipeline stopped because stage failed: %s", stage.stage_label)
            break

    manifest = build_output_manifest(paths=paths, config=config, stage_results=stage_results)

    with paths["manifest_json"].open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    pipeline_summary = {
        "app_id": config.app_id,
        "game_slug": config.game_slug,
        "game_title": config.game_title,
        "generated_at_utc": utc_now_iso(),
        "config_path": str(config_path),
        "pipeline_log": str(paths["pipeline_log"]),
        "output_manifest": str(paths["manifest_json"]),
        "stage_count_total": len(stage_specs),
        "stage_count_executed": sum(1 for r in stage_results if r["status"] in {"success", "failed"}),
        "stage_count_success": sum(1 for r in stage_results if r["status"] == "success"),
        "stage_count_failed": sum(1 for r in stage_results if r["status"] == "failed"),
        "stage_count_skipped": sum(1 for r in stage_results if r["status"] == "skipped"),
        "final_status": (
            "failed"
            if any(r["status"] == "failed" for r in stage_results)
            else "success"
        ),
    }

    with paths["pipeline_summary_json"].open("w", encoding="utf-8") as handle:
        json.dump(pipeline_summary, handle, ensure_ascii=False, indent=2)

    logging.info("Output manifest written to: %s", paths["manifest_json"])
    logging.info("Pipeline summary written to: %s", paths["pipeline_summary_json"])

    if pipeline_summary["final_status"] == "failed":
        print("[INFO] Pipeline finished with failures.")
        sys.exit(1)

    print("[INFO] Pipeline finished successfully.")


if __name__ == "__main__":
    main()