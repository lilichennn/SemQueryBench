"""
Command-line entry point for building SemQueryBench database fingerprints.

Input:
    preprocess/outputs/db_tags/{db_id}.json
    preprocess/outputs/clustering/difficulty_tiers.csv

Output:
    preprocess/outputs/fingerprints/{tier}/{db_id}.json
    preprocess/outputs/fingerprints/fingerprint_summary.csv

Example:

    python preprocess/scripts/build_fingerprints.py ^
        --db_tags_dir preprocess/outputs/db_tags ^
        --difficulty_tiers preprocess/outputs/clustering/difficulty_tiers.csv ^
        --output_dir preprocess/outputs/fingerprints
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def add_repo_paths() -> None:
    script_path = Path(__file__).resolve()
    preprocess_dir = script_path.parents[1]
    sys.path.insert(0, str(preprocess_dir))


add_repo_paths()

from semquery_preprocess.fingerprint import build_fingerprints_from_tiers  # noqa: E402


def configure_logging(log_file: str | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, mode="w", encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build database fingerprints from tagged metadata and difficulty tiers."
    )

    parser.add_argument(
        "--db_tags_dir",
        required=True,
        help="Directory containing tagged database metadata JSON files.",
    )
    parser.add_argument(
        "--difficulty_tiers",
        required=True,
        help="Path to difficulty_tiers.csv.",
    )
    parser.add_argument(
        "--output_dir",
        default="preprocess/outputs/fingerprints",
        help="Output directory for database fingerprints.",
    )

    parser.add_argument(
        "--db_col",
        default="db_id",
        help="Database id column in difficulty_tiers.csv.",
    )
    parser.add_argument(
        "--tier_col",
        default="difficulty",
        help="Tier column in difficulty_tiers.csv.",
    )
    parser.add_argument(
        "--include_untagged_columns",
        action="store_true",
        help="Include columns without col_tag under the UNK column tag.",
    )
    parser.add_argument(
        "--log_file",
        default=None,
        help="Optional log file path.",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    db_tags_dir = Path(args.db_tags_dir)
    difficulty_tiers = Path(args.difficulty_tiers)

    if not db_tags_dir.exists():
        raise FileNotFoundError(f"DB tags directory does not exist: {db_tags_dir}")

    if not list(db_tags_dir.glob("*.json")):
        raise FileNotFoundError(f"No JSON files found under {db_tags_dir}")

    if not difficulty_tiers.exists():
        raise FileNotFoundError(f"Difficulty tiers file does not exist: {difficulty_tiers}")


def main() -> None:
    args = parse_args()
    configure_logging(args.log_file)
    validate_args(args)

    build_fingerprints_from_tiers(
        db_tags_dir=args.db_tags_dir,
        difficulty_tiers_path=args.difficulty_tiers,
        output_dir=args.output_dir,
        include_untagged_columns=args.include_untagged_columns,
        db_col=args.db_col,
        tier_col=args.tier_col,
    )


if __name__ == "__main__":
    main()