"""
SQA generation utilities for SemQueryBench.

This module generates SQL-like Semantic Query Abstractions (SQAs) from a
cluster/tier-level Anchor Matrix.

Input:
    preprocess/outputs/anchor_matrices/{tier}_anchor_matrix.json
    preprocess/prompts/sqa_generation_prompt.md

Output:
    preprocess/outputs/sqa/{tier}_sqa.json
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


LOGGER = logging.getLogger(__name__)


def load_json(path: str | Path) -> Any:
    path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(data: Any, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_prompt(path: str | Path) -> str:
    path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_json_object(text: str) -> Dict[str, Any]:
    """
    Extract one JSON object from an LLM response.
    """
    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM response.")

    return json.loads(match.group(0))


def collect_available_slots(anchor_matrix: Dict[str, Any]) -> Dict[str, Any]:
    """
    Summarize non-empty slots in the Anchor Matrix.

    Returns:
        {
          "table_tags": [...],
          "column_tags": [...],
          "slots": {
            "TABLE_TAG": {
              "COLUMN_TAG": count
            }
          }
        }
    """
    table_tags: set[str] = set()
    column_tags: set[str] = set()
    slots: Dict[str, Dict[str, int]] = {}

    for _, db_am in anchor_matrix.items():
        if not isinstance(db_am, dict):
            continue

        for table_tag, col_groups in db_am.items():
            if not isinstance(col_groups, dict):
                continue

            for col_tag, anchors in col_groups.items():
                if isinstance(anchors, list) and len(anchors) > 0:
                    table_tags.add(table_tag)
                    column_tags.add(col_tag)
                    slots.setdefault(table_tag, {})
                    slots[table_tag][col_tag] = slots[table_tag].get(col_tag, 0) + len(anchors)

    return {
        "table_tags": sorted(table_tags),
        "column_tags": sorted(column_tags),
        "slots": slots,
    }


def build_sqa_user_prompt(
    anchor_matrix: Dict[str, Any],
    tier: str,
    num_sqa: int,
) -> str:
    """
    Build user prompt for SQA generation.
    """
    available_slots = collect_available_slots(anchor_matrix)

    payload = {
        "tier": tier,
        "num_sqa": num_sqa,
        "available_slots_summary": available_slots,
        "anchor_matrix": anchor_matrix,
    }

    return (
        "# SQA Generation Input\n\n"
        "Generate SQL-like Semantic Query Abstractions from the Anchor Matrix.\n\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "```"
    )


def normalize_sqa_output(
    raw_output: Dict[str, Any],
    tier: str,
) -> Dict[str, Any]:
    """
    Normalize generated SQA output to the expected JSON shape.
    """
    templates = raw_output.get("sqa_templates", [])

    if not isinstance(templates, list):
        templates = []

    normalized_templates: List[Dict[str, Any]] = []

    for idx, item in enumerate(templates, start=1):
        if not isinstance(item, dict):
            continue

        sqa = item.get("sqa")
        if not isinstance(sqa, str) or not sqa.strip():
            continue

        sqa_id = item.get("sqa_id")
        if not isinstance(sqa_id, str) or not sqa_id.strip():
            sqa_id = f"{tier}_sqa_{idx:03d}"

        intent = item.get("intent")
        if not isinstance(intent, str):
            intent = ""

        difficulty_hint = item.get("difficulty_hint")
        if difficulty_hint not in {"simple", "medium", "complex"}:
            difficulty_hint = "medium"

        required_slots = item.get("required_slots", {})
        if not isinstance(required_slots, dict):
            required_slots = {}

        table_tags = required_slots.get("table_tags", [])
        column_tags = required_slots.get("column_tags", [])

        if not isinstance(table_tags, list):
            table_tags = []
        if not isinstance(column_tags, list):
            column_tags = []

        normalized_templates.append(
            {
                "sqa_id": sqa_id,
                "sqa": sqa.strip(),
                "intent": intent.strip(),
                "difficulty_hint": difficulty_hint,
                "required_slots": {
                    "table_tags": [str(tag) for tag in table_tags],
                    "column_tags": [str(tag) for tag in column_tags],
                },
            }
        )

    return {
        "tier": tier,
        "sqa_templates": normalized_templates,
    }


def generate_sqa_from_anchor_matrix(
    anchor_matrix: Dict[str, Any],
    sqa_prompt: str,
    llm_client: Any,
    tier: str,
    num_sqa: int,
) -> Dict[str, Any]:
    """
    Generate SQAs from one Anchor Matrix.

    The LLM client must implement:
        chat(system_prompt: str, user_prompt: str) -> str
    """
    user_prompt = build_sqa_user_prompt(
        anchor_matrix=anchor_matrix,
        tier=tier,
        num_sqa=num_sqa,
    )

    response_text = llm_client.chat(
        system_prompt=sqa_prompt,
        user_prompt=user_prompt,
    )

    raw_output = extract_json_object(response_text)

    return normalize_sqa_output(raw_output, tier=tier)


def build_sqa_for_tier(
    anchor_matrix_path: str | Path,
    sqa_prompt_path: str | Path,
    output_sqa_path: str | Path,
    llm_client: Any,
    tier: str,
    num_sqa: int = 20,
) -> Dict[str, Any]:
    """
    Generate and save SQA templates for one tier.
    """
    anchor_matrix = load_json(anchor_matrix_path)
    sqa_prompt = load_prompt(sqa_prompt_path)

    LOGGER.info(
        "Generating SQA templates for tier=%s from %s",
        tier,
        anchor_matrix_path,
    )

    sqa_output = generate_sqa_from_anchor_matrix(
        anchor_matrix=anchor_matrix,
        sqa_prompt=sqa_prompt,
        llm_client=llm_client,
        tier=tier,
        num_sqa=num_sqa,
    )

    write_json(sqa_output, output_sqa_path)

    LOGGER.info(
        "Written %d SQA templates for tier=%s to %s",
        len(sqa_output.get("sqa_templates", [])),
        tier,
        output_sqa_path,
    )

    return sqa_output