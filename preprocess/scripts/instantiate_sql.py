"""
Command-line entry point for instantiating SQAs into SQL and questions.

Formal pipeline:
    difficulty_tiers.csv
        -> selected db_ids for one tier
        -> dataset/{tier}/all_meta/{db_id}.json
        -> preprocess/outputs/sql/{tier}/{db_id}.json

Example:

    python preprocess/scripts/instantiate_sql.py ^
        --tier easy ^
        --difficulty_tiers preprocess/outputs/clustering/difficulty_tiers.csv ^
        --sqa_file preprocess/outputs/sqa/easy_sqa.json ^
        --meta_dir dataset/easy/all_meta ^
        --prompt preprocess/prompts/sql_instantiation_prompt.md ^
        --output_dir preprocess/outputs/sql/easy ^
        --model qwen-plus

Debug only selected DBs:

    python preprocess/scripts/instantiate_sql.py ^
        --tier easy ^
        --difficulty_tiers preprocess/outputs/clustering/difficulty_tiers.csv ^
        --sqa_file preprocess/outputs/sqa/easy_sqa.json ^
        --meta_dir dataset/easy/all_meta ^
        --prompt preprocess/prompts/sql_instantiation_prompt.md ^
        --output_dir preprocess/outputs/sql/easy ^
        --model qwen-plus ^
        --db_ids Refinery ELECTRONIC_SALES
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd


def add_repo_paths() -> None:
    script_path = Path(__file__).resolve()
    preprocess_dir = script_path.parents[1]
    sys.path.insert(0, str(preprocess_dir))


add_repo_paths()

from semquery_preprocess.llm_client import OpenAICompatibleClient  # noqa: E402
from semquery_preprocess.sql_instantiator import instantiate_sqa_for_meta_file  # noqa: E402


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
        description="Instantiate SQA templates into SQL and natural-language questions."
    )

    parser.add_argument(
        "--tier",
        required=True,
        help="Difficulty tier to process, e.g., easy, mid, hard.",
    )
    parser.add_argument(
        "--difficulty_tiers",
        required=True,
        help="Path to difficulty_tiers.csv.",
    )
    parser.add_argument(
        "--sqa_file",
        required=True,
        help="Path to SQA JSON file, e.g., preprocess/outputs/sqa/easy_sqa.json.",
    )
    parser.add_argument(
        "--meta_dir",
        required=True,
        help="Directory containing all_meta JSON files, e.g., dataset/easy/all_meta.",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Path to SQL instantiation prompt.",
    )
    parser.add_argument(
        "--output_dir",
        default=None,
        help="Output directory. Default: preprocess/outputs/sql/{tier}.",
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
        "--db_ids",
        nargs="*",
        default=None,
        help=(
            "Optional DB id filter. The final DB list is still constrained by "
            "difficulty_tiers.csv."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of DBs to process after tier filtering.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip DBs whose output JSON already exists.",
    )
    parser.add_argument(
        "--request_interval",
        type=float,
        default=0.0,
        help="Sleep seconds between LLM requests.",
    )
    parser.add_argument(
        "--max_sample_chars",
        type=int,
        default=120,
        help="Maximum characters kept for each sample value in DB metadata.",
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
        default=8192,
        help="Maximum output tokens.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="HTTP request timeout in seconds.",
    )
    parser.add_argument(
        "--log_file",
        default=None,
        help="Optional log file path.",
    )

    return parser.parse_args()


def normalize_db_id(value: str) -> str:
    """
    Normalize db id from CSV or CLI.

    Examples:
        Refinery.json -> Refinery
        Refinery      -> Refinery
    """
    text = str(value).strip()

    if text.endswith(".json"):
        text = text[:-5]

    return text


def validate_args(args: argparse.Namespace) -> None:
    if not Path(args.difficulty_tiers).exists():
        raise FileNotFoundError(
            f"Difficulty tiers file does not exist: {args.difficulty_tiers}"
        )

    if not Path(args.sqa_file).exists():
        raise FileNotFoundError(f"SQA file does not exist: {args.sqa_file}")

    if not Path(args.meta_dir).exists():
        raise FileNotFoundError(f"Meta directory does not exist: {args.meta_dir}")

    if not Path(args.prompt).exists():
        raise FileNotFoundError(f"Prompt file does not exist: {args.prompt}")

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


def load_db_ids_from_difficulty_tiers(
    difficulty_tiers_path: str | Path,
    tier: str,
    db_col: str = "db_id",
    tier_col: str = "difficulty",
) -> list[str]:
    """
    Load DB ids assigned to a given tier from difficulty_tiers.csv.
    """
    df = pd.read_csv(difficulty_tiers_path)

    required_cols = {db_col, tier_col}
    missing_cols = required_cols - set(df.columns)

    if missing_cols:
        raise ValueError(
            f"difficulty_tiers.csv is missing required columns: {sorted(missing_cols)}. "
            f"Available columns: {list(df.columns)}"
        )

    selected = df[df[tier_col].astype(str) == str(tier)].copy()

    if selected.empty:
        raise ValueError(
            f"No databases found for tier='{tier}' in {difficulty_tiers_path}."
        )

    db_ids = [normalize_db_id(value) for value in selected[db_col].tolist()]
    db_ids = [db_id for db_id in db_ids if db_id]

    if not db_ids:
        raise ValueError(
            f"No valid db_id values found for tier='{tier}' in {difficulty_tiers_path}."
        )

    return db_ids


def collect_meta_files_from_tiers(
    meta_dir: str | Path,
    db_ids_from_tiers: list[str],
    db_ids_filter: list[str] | None = None,
    limit: int | None = None,
) -> list[Path]:
    """
    Collect meta files using difficulty_tiers.csv as the source of truth.

    If db_ids_filter is provided, it is applied as a filter on top of the tier DB list.
    """
    meta_dir = Path(meta_dir)

    db_ids = db_ids_from_tiers

    if db_ids_filter:
        filter_set = {normalize_db_id(db_id) for db_id in db_ids_filter}
        db_ids = [db_id for db_id in db_ids if db_id in filter_set]

        missing_from_tier = sorted(filter_set - set(db_ids_from_tiers))
        if missing_from_tier:
            raise ValueError(
                "The following --db_ids are not assigned to the requested tier "
                f"according to difficulty_tiers.csv: {missing_from_tier}"
            )

    if limit is not None:
        db_ids = db_ids[:limit]

    files: list[Path] = []
    missing_files: list[Path] = []

    for db_id in db_ids:
        path = meta_dir / f"{db_id}.json"

        if path.exists():
            files.append(path)
        else:
            missing_files.append(path)

    if missing_files:
        missing_text = "\n".join(str(path) for path in missing_files[:20])
        raise FileNotFoundError(
            "Some DBs selected by difficulty_tiers.csv do not have meta files "
            f"under meta_dir={meta_dir}.\n"
            f"Missing files:\n{missing_text}"
        )

    if not files:
        raise FileNotFoundError(
            f"No meta files collected from {meta_dir}. "
            "Check tier, difficulty_tiers.csv, and optional --db_ids filter."
        )

    return files


def main() -> None:
    args = parse_args()
    configure_logging(args.log_file)
    validate_args(args)

    logger = logging.getLogger(__name__)

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path("preprocess/outputs/sql") / args.tier
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    db_ids_from_tiers = load_db_ids_from_difficulty_tiers(
        difficulty_tiers_path=args.difficulty_tiers,
        tier=args.tier,
        db_col=args.db_col,
        tier_col=args.tier_col,
    )

    logger.info(
        "Loaded %d DB ids for tier=%s from %s",
        len(db_ids_from_tiers),
        args.tier,
        args.difficulty_tiers,
    )

    meta_files = collect_meta_files_from_tiers(
        meta_dir=args.meta_dir,
        db_ids_from_tiers=db_ids_from_tiers,
        db_ids_filter=args.db_ids,
        limit=args.limit,
    )

    client = OpenAICompatibleClient(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )

    logger.info(
        "Instantiating SQL for tier=%s, db_count=%d",
        args.tier,
        len(meta_files),
    )

    for idx, meta_file in enumerate(meta_files, start=1):
        db_id = meta_file.stem
        output_file = output_dir / f"{db_id}.json"

        if args.resume and output_file.exists():
            logger.info(
                "[%d/%d] Skip existing output: %s",
                idx,
                len(meta_files),
                output_file,
            )
            continue

        logger.info("[%d/%d] Processing db_id=%s", idx, len(meta_files), db_id)

        try:
            instantiate_sqa_for_meta_file(
                sqa_file=args.sqa_file,
                meta_file=meta_file,
                prompt_path=args.prompt,
                output_file=output_file,
                llm_client=client,
                tier=args.tier,
                max_sample_chars=args.max_sample_chars,
            )
        except Exception as exc:
            logger.exception(
                "Failed to instantiate SQL for db_id=%s: %s",
                db_id,
                exc,
            )
            raise

        if args.request_interval > 0 and idx < len(meta_files):
            time.sleep(args.request_interval)

    logger.info("SQL instantiation finished. Output directory: %s", output_dir)


if __name__ == "__main__":
    main()