"""
Command-line entry point for constructing SemQueryBench difficulty tiers.

Input:
    preprocess/outputs/similarity/db_similarity_pairs.csv

Outputs:
    preprocess/outputs/clustering/difficulty_tiers.csv
    preprocess/outputs/clustering/difficulty_metrics.csv
    preprocess/outputs/clustering/selected_distance_matrix.csv

Production example:

    python preprocess/scripts/build_difficulty_tiers.py ^
        --similarity_pairs preprocess/outputs/similarity/db_similarity_pairs.csv ^
        --output_dir preprocess/outputs/clustering ^
        --easy_size 20 ^
        --mid_size 21 ^
        --hard_size 21 ^
        --easy_target_dist 0.10 ^
        --mid_target_dist 0.20 ^
        --hard_target_dist 0.30

Smoke-test example for three sample databases:

    python preprocess/scripts/build_difficulty_tiers.py ^
        --similarity_pairs preprocess/outputs/similarity/db_similarity_pairs.csv ^
        --output_dir preprocess/outputs/clustering_sample ^
        --easy_size 1 ^
        --mid_size 1 ^
        --hard_size 1
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

from semquery_preprocess.clustering import (  # noqa: E402
    TierConfig,
    build_difficulty_tiers,
    build_similarity_matrix,
    load_similarity_pairs,
    similarity_to_distance_matrix,
    write_clustering_outputs,
)


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
        description="Build easy/mid/hard difficulty tiers from schema-property similarity."
    )

    parser.add_argument(
        "--similarity_pairs",
        required=True,
        help="Pairwise schema-property similarity CSV.",
    )
    parser.add_argument(
        "--output_dir",
        default="preprocess/outputs/clustering",
        help="Output directory for difficulty-tier files.",
    )

    parser.add_argument(
        "--similarity_col",
        default="schema_property_similarity",
        help="Similarity score column in the pairwise CSV.",
    )
    parser.add_argument(
        "--db1_col",
        default="db1",
        help="First database id column in the pairwise CSV.",
    )
    parser.add_argument(
        "--db2_col",
        default="db2",
        help="Second database id column in the pairwise CSV.",
    )

    parser.add_argument(
        "--easy_size",
        type=int,
        default=20,
        help="Number of databases in the easy tier.",
    )
    parser.add_argument(
        "--mid_size",
        type=int,
        default=21,
        help="Number of databases in the mid tier.",
    )
    parser.add_argument(
        "--hard_size",
        type=int,
        default=21,
        help="Number of databases in the hard tier.",
    )

    parser.add_argument(
        "--easy_target_dist",
        type=float,
        default=0.10,
        help="Target average intra-tier distance for the easy tier.",
    )
    parser.add_argument(
        "--mid_target_dist",
        type=float,
        default=0.20,
        help="Target average intra-tier distance for the mid tier.",
    )
    parser.add_argument(
        "--hard_target_dist",
        type=float,
        default=0.30,
        help="Target average intra-tier distance for the hard tier.",
    )

    parser.add_argument(
        "--alpha",
        type=float,
        default=1.5,
        help="Penalty weight for intra-tier distance standard deviation.",
    )

    parser.add_argument(
        "--tiers_filename",
        default="difficulty_tiers.csv",
        help="Output filename for selected database tiers.",
    )
    parser.add_argument(
        "--metrics_filename",
        default="difficulty_metrics.csv",
        help="Output filename for tier distance metrics.",
    )
    parser.add_argument(
        "--selected_matrix_filename",
        default="selected_distance_matrix.csv",
        help="Output filename for selected database distance matrix.",
    )

    parser.add_argument(
        "--log_file",
        default=None,
        help="Optional log file path.",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    similarity_pairs = Path(args.similarity_pairs)

    if not similarity_pairs.exists():
        raise FileNotFoundError(
            f"Similarity pairs file does not exist: {similarity_pairs}"
        )

    for name in ["easy_size", "mid_size", "hard_size"]:
        value = getattr(args, name)
        if value <= 0:
            raise ValueError(f"--{name} must be a positive integer.")

    for name in ["easy_target_dist", "mid_target_dist", "hard_target_dist"]:
        value = getattr(args, name)
        if value < 0.0 or value > 1.0:
            raise ValueError(f"--{name} must be in [0, 1].")

    if args.alpha < 0:
        raise ValueError("--alpha must be non-negative.")


def main() -> None:
    args = parse_args()
    configure_logging(args.log_file)
    validate_args(args)

    logger = logging.getLogger(__name__)

    logger.info("Loading similarity pairs from %s", args.similarity_pairs)

    pairs_df = load_similarity_pairs(
        similarity_pairs_path=args.similarity_pairs,
        db1_col=args.db1_col,
        db2_col=args.db2_col,
        similarity_col=args.similarity_col,
    )

    db_ids, sim_matrix = build_similarity_matrix(pairs_df)
    dist_matrix = similarity_to_distance_matrix(sim_matrix)

    logger.info("Loaded %d databases.", len(db_ids))

    tier_configs = [
        TierConfig(
            name="easy",
            target_distance=args.easy_target_dist,
            size=args.easy_size,
        ),
        TierConfig(
            name="mid",
            target_distance=args.mid_target_dist,
            size=args.mid_size,
        ),
        TierConfig(
            name="hard",
            target_distance=args.hard_target_dist,
            size=args.hard_size,
        ),
    ]

    logger.info(
        "Tier config: easy=(size=%d, tau=%.4f), mid=(size=%d, tau=%.4f), hard=(size=%d, tau=%.4f), alpha=%.4f",
        args.easy_size,
        args.easy_target_dist,
        args.mid_size,
        args.mid_target_dist,
        args.hard_size,
        args.hard_target_dist,
        args.alpha,
    )

    difficulty_tiers_df, difficulty_metrics_df, selected_dist_df = build_difficulty_tiers(
        dist_matrix=dist_matrix,
        db_ids=db_ids,
        tier_configs=tier_configs,
        alpha=args.alpha,
    )

    tiers_path, metrics_path, selected_matrix_path = write_clustering_outputs(
        difficulty_tiers_df=difficulty_tiers_df,
        difficulty_metrics_df=difficulty_metrics_df,
        selected_distance_matrix_df=selected_dist_df,
        output_dir=args.output_dir,
        tiers_filename=args.tiers_filename,
        metrics_filename=args.metrics_filename,
        selected_matrix_filename=args.selected_matrix_filename,
    )

    logger.info("Written difficulty tiers: %s", tiers_path)
    logger.info("Written difficulty metrics: %s", metrics_path)
    logger.info("Written selected distance matrix: %s", selected_matrix_path)

    logger.info("Difficulty metrics:\n%s", difficulty_metrics_df.to_string(index=False))


if __name__ == "__main__":
    main()