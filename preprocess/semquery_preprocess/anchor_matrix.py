"""
Anchor Matrix construction for SemQueryBench.

This module fills an Anchor Matrix template from database fingerprints.

Input:
    preprocess/outputs/fingerprints/{tier}/{db_id}.json

Fingerprint format:
    {
      "TABLE_TAG": {
        "COLUMN_TAG": [
          {
            "path": "schema.table.column",
            "type": "TEXT",
            "sample": "..."
          }
        ]
      }
    }

Anchor Matrix template format:
    {
      "DB_ID.json": {
        "TABLE_TAG": {
          "COLUMN_TAG": []
        }
      }
    }

Output:
    preprocess/outputs/anchor_matrices/{tier}_anchor_matrix.json
"""

from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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


def load_fingerprints_for_tier(
    fingerprints_dir: str | Path,
    tier: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Load all fingerprint JSON files for one tier.

    Args:
        fingerprints_dir:
            Root fingerprint directory, usually preprocess/outputs/fingerprints.
        tier:
            Difficulty tier, e.g., easy, mid, hard.

    Returns:
        Mapping from "db_id.json" to fingerprint object.
    """
    tier_dir = Path(fingerprints_dir) / tier

    if not tier_dir.exists():
        raise FileNotFoundError(f"Fingerprint tier directory does not exist: {tier_dir}")

    files = sorted(tier_dir.glob("*.json"))

    if not files:
        raise FileNotFoundError(f"No fingerprint JSON files found under {tier_dir}")

    fingerprints: Dict[str, Dict[str, Any]] = {}

    for path in files:
        key = path.name
        fingerprints[key] = load_json(path)

    return fingerprints

def build_anchor_template_for_fingerprints(
    slot_template: Dict[str, Any],
    fingerprints: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Expand a generic single-database Anchor Matrix slot template into a
    tier-level Anchor Matrix template.

    Input slot_template:
        {
          "REFERENCE": {
            "TIME_EVENT": [],
            "ID_MAIN": []
          },
          "MASTER": {
            "ID_MAIN": []
          }
        }

    Output:
        {
          "DB_A.json": {
            "REFERENCE": {
              "TIME_EVENT": [],
              "ID_MAIN": []
            },
            "MASTER": {
              "ID_MAIN": []
            }
          },
          "DB_B.json": {
            ...
          }
        }
    """
    if not isinstance(slot_template, dict) or not slot_template:
        raise ValueError("Anchor Matrix slot template must be a non-empty JSON object.")

    expanded: Dict[str, Any] = {}

    for db_file in sorted(fingerprints.keys()):
        expanded[db_file] = copy.deepcopy(slot_template)

    return expanded


def build_anchor_matrix_user_prompt(
    fingerprints: Dict[str, Dict[str, Any]],
    anchor_template: Dict[str, Any],
    tier: str,
) -> str:
    """
    Build the user prompt for Anchor Matrix filling.
    """
    payload = {
        "tier": tier,
        "fingerprints": fingerprints,
        "anchor_matrix_template": anchor_template,
    }

    return (
        "# Anchor Matrix Construction Input\n\n"
        "Fill the Anchor Matrix template using the fingerprints.\n\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "```"
    )


def validate_anchor_matrix_structure(
    generated_am: Dict[str, Any],
    anchor_template: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Enforce template key stability.

    The LLM must not add/remove/rename keys. This function returns a cleaned
    Anchor Matrix that preserves exactly the template keys and keeps only list
    values under valid slots.
    """
    cleaned: Dict[str, Any] = {}

    for db_file, table_template in anchor_template.items():
        cleaned[db_file] = {}

        generated_db = generated_am.get(db_file, {})
        if not isinstance(generated_db, dict):
            generated_db = {}

        for table_tag, col_template in table_template.items():
            cleaned[db_file][table_tag] = {}

            generated_table = generated_db.get(table_tag, {})
            if not isinstance(generated_table, dict):
                generated_table = {}

            for col_tag in col_template.keys():
                value = generated_table.get(col_tag, [])

                if not isinstance(value, list):
                    value = []

                # Keep only string paths.
                value = [str(item) for item in value if isinstance(item, str)]

                cleaned[db_file][table_tag][col_tag] = value

    return cleaned


def fill_anchor_matrix(
    fingerprints: Dict[str, Dict[str, Any]],
    anchor_template: Dict[str, Any],
    anchor_prompt: str,
    llm_client: Any,
    tier: str,
) -> Dict[str, Any]:
    """
    Fill an Anchor Matrix with an LLM.

    The LLM client must implement:
        chat(system_prompt: str, user_prompt: str) -> str
    """
    user_prompt = build_anchor_matrix_user_prompt(
        fingerprints=fingerprints,
        anchor_template=anchor_template,
        tier=tier,
    )

    response_text = llm_client.chat(
        system_prompt=anchor_prompt,
        user_prompt=user_prompt,
    )

    generated_am = extract_json_object(response_text)

    return validate_anchor_matrix_structure(
        generated_am=generated_am,
        anchor_template=anchor_template,
    )


def build_anchor_matrix_for_tier(
    fingerprints_dir: str | Path,
    anchor_template_path: str | Path,
    anchor_prompt_path: str | Path,
    output_anchor_path: str | Path,
    llm_client: Any,
    tier: str,
    keep_template_only: bool = False,
) -> Dict[str, Any]:
    """
    Build and save Anchor Matrix for one tier.
    """
    fingerprints = load_fingerprints_for_tier(
        fingerprints_dir=fingerprints_dir,
        tier=tier,
    )

    slot_template = load_json(anchor_template_path)
    anchor_template = build_anchor_template_for_fingerprints(
        slot_template=slot_template,
        fingerprints=fingerprints,
    )

    anchor_prompt = load_prompt(anchor_prompt_path)

    LOGGER.info(
        "Building Anchor Matrix for tier=%s using %d fingerprints.",
        tier,
        len(fingerprints),
    )

    anchor_matrix = fill_anchor_matrix(
        fingerprints=fingerprints,
        anchor_template=anchor_template,
        anchor_prompt=anchor_prompt,
        llm_client=llm_client,
        tier=tier,
    )

    write_json(anchor_matrix, output_anchor_path)

    LOGGER.info("Written Anchor Matrix for tier=%s to %s", tier, output_anchor_path)

    return anchor_matrix