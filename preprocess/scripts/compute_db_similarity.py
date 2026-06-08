"""
Command-line entry point for computing SemQueryBench schema-property similarity.

Input:
    preprocess/outputs/db_tags/*.json

Outputs:
    preprocess/outputs/similarity/db_similarity_pairs.csv
    preprocess/outputs/similarity/db_similarity_matrix.csv

Example:

    python preprocess/scripts/compute_db_similarity.py ^
        --db_tags_dir preprocess/outputs/db_tags ^
        --tag_schema preprocess/configs/db_tag_schema.json ^
        --output_dir preprocess/outputs/similarity
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

from semquery_preprocess.similarity import (  # noqa: E402
    compute_pairwise_similarity,
    load_db_tags,
    load_tag_vocabs,
    pairwise_to_matrix,
    write_similarity_outputs,
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
        description="Compute pairwise schema-property similarity between tagged databases."
    )

    parser.add_argument(
        "--db_tags_dir",
        required=True,
        help="Directory containing tagged database metadata JSON files.",
    )
    parser.add_argument(
        "--tag_schema",
        default="preprocess/configs/db_tag_schema.json",
        help="Path to db tag schema JSON.",
    )
    parser.add_argument(
        "--output_dir",
        default="preprocess/outputs/similarity",
        help="Output directory for similarity CSV files.",
    )

    parser.add_argument(
        "--w_table",
        type=float,
        default=0.35,
        help="Weight of table-type composition similarity.",
    )
    parser.add_argument(
        "--w_signature",
        type=float,
        default=0.40,
        help="Weight of per-table property-signature similarity.",
    )
    parser.add_argument(
        "--w_cooccurrence",
        type=float,
        default=0.25,
        help="Weight of property co-occurrence similarity.",
    )
    parser.add_argument(
        "--no_lexical_similarity",
        action="store_true",
        help="Disable lexical similarity column in pairwise output.",
    )

    parser.add_argument(
        "--pairs_filename",
        default="db_similarity_pairs.csv",
        help="Filename for pairwise similarity output.",
    )
    parser.add_argument(
        "--matrix_filename",
        default="db_similarity_matrix.csv",
        help="Filename for matrix similarity output.",
    )
    parser.add_argument(
        "--log_file",
        default=None,
        help="Optional log file path.",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    db_tags_dir = Path(args.db_tags_dir)

    if not db_tags_dir.exists():
        raise FileNotFoundError(f"DB tags directory does not exist: {db_tags_dir}")

    if not list(db_tags_dir.glob("*.json")):
        raise FileNotFoundError(f"No JSON files found under {db_tags_dir}")

    tag_schema = Path(args.tag_schema)
    if args.tag_schema and not tag_schema.exists():
        raise FileNotFoundError(f"Tag schema file does not exist: {tag_schema}")

    weight_sum = args.w_table + args.w_signature + args.w_cooccurrence
    if abs(weight_sum - 1.0) > 1e-8:
        raise ValueError(
            f"Similarity weights must sum to 1.0, got {weight_sum}"
        )


def main() -> None:
    args = parse_args()
    configure_logging(args.log_file)
    validate_args(args)

    logger = logging.getLogger(__name__)

    logger.info("Loading tag vocabularies from %s", args.tag_schema)
    table_vocab, column_vocab = load_tag_vocabs(args.tag_schema)
    logger.info("Loaded %d table tags and %d column tags.", len(table_vocab), len(column_vocab))

    logger.info("Loading tagged database metadata from %s", args.db_tags_dir)
    db_metas = load_db_tags(args.db_tags_dir)
    db_ids = sorted(db_metas.keys())
    logger.info("Loaded %d databases.", len(db_ids))

    logger.info(
        "Computing schema-property similarity with weights: table=%.2f, signature=%.2f, cooccurrence=%.2f",
        args.w_table,
        args.w_signature,
        args.w_cooccurrence,
    )

    pairs_df = compute_pairwise_similarity(
        db_metas=db_metas,
        table_vocab=table_vocab,
        w_table=args.w_table,
        w_signature=args.w_signature,
        w_cooccurrence=args.w_cooccurrence,
        include_lexical_similarity=not args.no_lexical_similarity,
    )

    matrix_df = pairwise_to_matrix(
        pairs_df=pairs_df,
        db_ids=db_ids,
        value_col="schema_property_similarity",
    )

    pairs_path, matrix_path = write_similarity_outputs(
        pairs_df=pairs_df,
        matrix_df=matrix_df,
        output_dir=args.output_dir,
        pairs_filename=args.pairs_filename,
        matrix_filename=args.matrix_filename,
    )

    logger.info("Written pairwise similarity output: %s", pairs_path)
    logger.info("Written matrix similarity output: %s", matrix_path)

    if not pairs_df.empty:
        logger.info("Top 10 most similar database pairs:")
        logger.info("\n%s", pairs_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()