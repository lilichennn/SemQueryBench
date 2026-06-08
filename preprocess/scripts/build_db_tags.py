"""
Command-line entry point for building database semantic tags from SemQueryBench
all_meta files.

Expected input layout:

    dataset/
    ├── easy/all_meta/{db_id}.json
    ├── mid/all_meta/{db_id}.json
    └── hard/all_meta/{db_id}.json

Example:

    python preprocess/scripts/build_db_tags.py ^
        --dataset_dir dataset ^
        --output_dir preprocess/outputs/db_tags_test ^
        --detailed_prompt preprocess/prompts/db_tagging_prompt.md ^
        --compact_prompt preprocess/prompts/db_tagging_prompt_compact.md ^
        --model qwen-plus ^
        --tier easy ^
        --db_id WORD_VECTORS_US ^
        --limit 2
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


def add_repo_paths() -> None:
    script_path = Path(__file__).resolve()
    preprocess_dir = script_path.parents[1]
    sys.path.insert(0, str(preprocess_dir))


add_repo_paths()

from semquery_preprocess.db_tagger import tag_databases  # noqa: E402
from semquery_preprocess.llm_client import OpenAICompatibleClient  # noqa: E402


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
        description="Build table-level and column-level semantic tags from SemQueryBench all_meta files."
    )

    parser.add_argument(
        "--dataset_dir",
        required=True,
        help="SemQueryBench dataset directory. Expected layout: dataset/{easy,mid,hard}/all_meta/{db_id}.json",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Directory for generated per-database tag JSON files.",
    )
    parser.add_argument(
        "--detailed_prompt",
        required=True,
        help="Prompt file for normal-size tables.",
    )
    parser.add_argument(
        "--compact_prompt",
        default=None,
        help="Optional prompt file for wide tables.",
    )
    parser.add_argument(
        "--compact_threshold",
        type=int,
        default=100,
        help="Use compact prompt when a table has more columns than this threshold.",
    )
    parser.add_argument(
        "--max_sample_chars",
        type=int,
        default=100,
        help="Maximum number of characters kept for each sample value in the prompt.",
    )

    parser.add_argument(
        "--model",
        required=True,
        help="LLM model name.",
    )
    parser.add_argument(
        "--base_url",
        default=os.getenv("OPENAI_BASE_URL"),
        help="OpenAI-compatible API base URL. Can also be set by OPENAI_BASE_URL.",
    )
    parser.add_argument(
        "--api_key",
        default=os.getenv("OPENAI_API_KEY"),
        help="API key. Can also be set by OPENAI_API_KEY.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="LLM sampling temperature.",
    )
    parser.add_argument(
        "--max_tokens",
        type=int,
        default=4096,
        help="Maximum output tokens.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="HTTP request timeout in seconds.",
    )
    parser.add_argument(
        "--request_interval",
        type=float,
        default=0.0,
        help="Sleep interval between LLM requests in seconds.",
    )

    parser.add_argument(
        "--tier",
        default=None,
        choices=["easy", "mid", "hard"],
        help="Optional tier filter for debugging or partial runs.",
    )
    parser.add_argument(
        "--db_id",
        default=None,
        help="Optional database id filter, e.g., WORD_VECTORS_US.",
    )
    parser.add_argument(
        "--table",
        default=None,
        help="Optional table name filter.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of tables to process.",
    )

    parser.add_argument(
        "--save_every",
        type=int,
        default=20,
        help="Save progress after this many newly processed or reused tables.",
    )
    parser.add_argument(
        "--no_resume",
        action="store_true",
        help="Disable resume mode and ignore existing output files.",
    )
    parser.add_argument(
        "--log_file",
        default=None,
        help="Optional log file path.",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)

    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory does not exist: {args.dataset_dir}")

    if not list(dataset_dir.glob("*/all_meta/*.json")):
        raise FileNotFoundError(
            f"No all_meta JSON files found under {args.dataset_dir}. "
            "Expected layout: dataset/{easy,mid,hard}/all_meta/{db_id}.json"
        )

    if not Path(args.detailed_prompt).exists():
        raise FileNotFoundError(
            f"Detailed prompt file does not exist: {args.detailed_prompt}"
        )

    if args.compact_prompt and not Path(args.compact_prompt).exists():
        raise FileNotFoundError(
            f"Compact prompt file does not exist: {args.compact_prompt}"
        )

    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be a positive integer.")

    if args.max_sample_chars <= 0:
        raise ValueError("--max_sample_chars must be a positive integer.")

    if not args.base_url:
        raise ValueError(
            "Missing API base URL. Provide --base_url or set OPENAI_BASE_URL."
        )

    if not args.api_key:
        raise ValueError(
            "Missing API key. Provide --api_key or set OPENAI_API_KEY."
        )


def main() -> None:
    args = parse_args()
    configure_logging(args.log_file)
    validate_args(args)

    client = OpenAICompatibleClient(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )

    tag_databases(
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        llm_client=client,
        detailed_prompt_path=args.detailed_prompt,
        compact_prompt_path=args.compact_prompt,
        compact_threshold=args.compact_threshold,
        resume=not args.no_resume,
        save_every=args.save_every,
        request_interval=args.request_interval,
        tier_filter=args.tier,
        db_id_filter=args.db_id,
        table_filter=args.table,
        limit=args.limit,
        max_sample_chars=args.max_sample_chars,
    )


if __name__ == "__main__":
    main()