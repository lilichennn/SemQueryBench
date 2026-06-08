"""
Command-line entry point for building Anchor Matrices and SQA templates.

Pipeline:
    fingerprints/{tier}/*.json
        -> anchor_matrices/{tier}_anchor_matrix.json
        -> sqa/{tier}_sqa.json

Example:

    python preprocess/scripts/build_sqa.py ^
        --fingerprints_dir preprocess/outputs/fingerprints ^
        --anchor_template preprocess/configs/anchor_matrix_template.json ^
        --anchor_prompt preprocess/prompts/anchor_matrix_prompt.md ^
        --sqa_prompt preprocess/prompts/sqa_generation_prompt.md ^
        --output_anchor_dir preprocess/outputs/anchor_matrices ^
        --output_sqa_dir preprocess/outputs/sqa ^
        --model qwen-plus ^
        --tiers easy mid hard
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

from semquery_preprocess.anchor_matrix import build_anchor_matrix_for_tier  # noqa: E402
from semquery_preprocess.llm_client import OpenAICompatibleClient  # noqa: E402
from semquery_preprocess.sqa_generator import build_sqa_for_tier  # noqa: E402


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
        description="Build tier-level Anchor Matrices and SQA templates."
    )

    parser.add_argument(
        "--fingerprints_dir",
        default="preprocess/outputs/fingerprints",
        help="Root directory containing fingerprints/{tier}/*.json.",
    )
    parser.add_argument(
        "--anchor_template",
        required=True,
        help="Path to Anchor Matrix JSON template.",
    )
    parser.add_argument(
        "--anchor_prompt",
        required=True,
        help="Prompt file for Anchor Matrix filling.",
    )
    parser.add_argument(
        "--sqa_prompt",
        required=True,
        help="Prompt file for SQA generation.",
    )
    parser.add_argument(
        "--output_anchor_dir",
        default="preprocess/outputs/anchor_matrices",
        help="Output directory for generated Anchor Matrices.",
    )
    parser.add_argument(
        "--output_sqa_dir",
        default="preprocess/outputs/sqa",
        help="Output directory for generated SQA templates.",
    )
    parser.add_argument(
        "--tiers",
        nargs="+",
        default=["easy", "mid", "hard"],
        help="Tiers to process, e.g., --tiers easy mid hard.",
    )

    parser.add_argument(
        "--num_sqa",
        type=int,
        default=20,
        help="Requested number of SQA templates per tier.",
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
        "--skip_anchor",
        action="store_true",
        help="Skip Anchor Matrix generation and use existing anchor matrix files.",
    )
    parser.add_argument(
        "--skip_sqa",
        action="store_true",
        help="Skip SQA generation after Anchor Matrix generation.",
    )
    parser.add_argument(
        "--log_file",
        default=None,
        help="Optional log file path.",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    fingerprints_dir = Path(args.fingerprints_dir)

    if not fingerprints_dir.exists():
        raise FileNotFoundError(f"Fingerprints directory does not exist: {fingerprints_dir}")

    for tier in args.tiers:
        tier_dir = fingerprints_dir / tier
        if not tier_dir.exists():
            raise FileNotFoundError(f"Fingerprint tier directory does not exist: {tier_dir}")
        if not list(tier_dir.glob("*.json")):
            raise FileNotFoundError(f"No fingerprint JSON files found under {tier_dir}")

    if not Path(args.anchor_template).exists():
        raise FileNotFoundError(f"Anchor template file does not exist: {args.anchor_template}")

    if not Path(args.anchor_prompt).exists():
        raise FileNotFoundError(f"Anchor prompt file does not exist: {args.anchor_prompt}")

    if not Path(args.sqa_prompt).exists():
        raise FileNotFoundError(f"SQA prompt file does not exist: {args.sqa_prompt}")

    if args.num_sqa <= 0:
        raise ValueError("--num_sqa must be a positive integer.")

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

    logger = logging.getLogger(__name__)

    client = OpenAICompatibleClient(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )

    output_anchor_dir = Path(args.output_anchor_dir)
    output_sqa_dir = Path(args.output_sqa_dir)

    for tier in args.tiers:
        logger.info("Processing tier=%s", tier)

        anchor_path = output_anchor_dir / f"{tier}_anchor_matrix.json"
        sqa_path = output_sqa_dir / f"{tier}_sqa.json"

        if args.skip_anchor:
            if not anchor_path.exists():
                raise FileNotFoundError(
                    f"--skip_anchor was set, but anchor matrix does not exist: {anchor_path}"
                )
            logger.info("Skipping Anchor Matrix generation for tier=%s", tier)
        else:
            build_anchor_matrix_for_tier(
                fingerprints_dir=args.fingerprints_dir,
                anchor_template_path=args.anchor_template,
                anchor_prompt_path=args.anchor_prompt,
                output_anchor_path=anchor_path,
                llm_client=client,
                tier=tier,
            )

        if args.skip_sqa:
            logger.info("Skipping SQA generation for tier=%s", tier)
            continue

        build_sqa_for_tier(
            anchor_matrix_path=anchor_path,
            sqa_prompt_path=args.sqa_prompt,
            output_sqa_path=sqa_path,
            llm_client=client,
            tier=tier,
            num_sqa=args.num_sqa,
        )

    logger.info("SQA construction pipeline finished.")


if __name__ == "__main__":
    main()