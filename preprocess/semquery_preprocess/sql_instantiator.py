"""
SQL instantiation utilities for SemQueryBench.

This module instantiates tier-level SQA templates on concrete databases.

Input:
    preprocess/outputs/sqa/{tier}_sqa.json
    dataset/{tier}/all_meta/{db_id}.json
    preprocess/prompts/sql_instantiation_prompt.md

Output:
    preprocess/outputs/sql/{tier}/{db_id}.json
"""

from __future__ import annotations

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


def normalize_db_id_from_meta_path(path: str | Path) -> str:
    """
    Convert dataset/easy/all_meta/Refinery.json -> Refinery.
    """
    return Path(path).stem


def load_sqa_templates(sqa_file: str | Path) -> Dict[str, Any]:
    """
    Load SQA templates.

    Expected current format:
        {
          "tier": "easy",
          "sqa_templates": [
            {
              "sqa_id": "easy_sqa_001",
              "sqa": "...",
              "intent": "...",
              "difficulty_hint": "...",
              "required_slots": {...}
            }
          ]
        }

    Also tolerates a legacy format:
        {
          "easy": {
            "skeleton1": {
              "skeleton": "...",
              ...
            }
          }
        }
    """
    data = load_json(sqa_file)

    if isinstance(data, dict) and isinstance(data.get("sqa_templates"), list):
        tier = str(data.get("tier", "unknown"))
        templates = []

        for idx, item in enumerate(data["sqa_templates"], start=1):
            if not isinstance(item, dict):
                continue

            sqa = item.get("sqa") or item.get("skeleton")
            if not isinstance(sqa, str) or not sqa.strip():
                continue

            sqa_id = item.get("sqa_id") or item.get("skeleton_id") or f"{tier}_sqa_{idx:03d}"

            templates.append(
                {
                    "sqa_id": str(sqa_id),
                    "sqa": sqa.strip(),
                    "intent": item.get("intent", ""),
                    "difficulty_hint": item.get("difficulty_hint", ""),
                    "required_slots": item.get("required_slots", {}),
                }
            )

        return {
            "tier": tier,
            "sqa_templates": templates,
        }

    # Legacy format compatibility.
    if isinstance(data, dict) and len(data) == 1:
        tier = next(iter(data.keys()))
        tier_obj = data[tier]

        if isinstance(tier_obj, dict):
            templates = []

            for idx, (key, value) in enumerate(tier_obj.items(), start=1):
                if not isinstance(value, dict):
                    continue

                sqa = value.get("skeleton") or value.get("sqa")
                if not isinstance(sqa, str) or not sqa.strip():
                    continue

                templates.append(
                    {
                        "sqa_id": str(key),
                        "sqa": sqa.strip(),
                        "intent": value.get("intent", ""),
                        "difficulty_hint": value.get("difficulty_hint", ""),
                        "required_slots": value.get("required_slots", {}),
                    }
                )

            return {
                "tier": str(tier),
                "sqa_templates": templates,
            }

    raise ValueError(f"Unsupported SQA file format: {sqa_file}")


def iter_tables_from_meta(db_meta: Dict[str, Any]) -> Iterable[tuple[str, str, Dict[str, Any]]]:
    """
    Yield (schema_name, table_name, table_info) from all_meta JSON.

    Supports:
        {
          "TABLE": {"table_tag": "...", "colname_list": [...]}
        }

    and:
        {
          "main": {
            "TABLE": {"table_tag": "...", "colname_list": [...]}
          }
        }
    """
    if not isinstance(db_meta, dict):
        return

    # Flat table-level dict.
    if all(
        isinstance(value, dict) and ("table_tag" in value or "colname_list" in value)
        for value in db_meta.values()
    ):
        for table_name, table_info in db_meta.items():
            if isinstance(table_info, dict):
                yield "main", str(table_name), table_info
        return

    # Schema-level dict.
    for schema_name, schema_obj in db_meta.items():
        if not isinstance(schema_obj, dict):
            continue

        for table_name, table_info in schema_obj.items():
            if isinstance(table_info, dict) and (
                "table_tag" in table_info or "colname_list" in table_info
            ):
                yield str(schema_name), str(table_name), table_info


def truncate_value(value: Any, max_chars: int = 120) -> Any:
    if value is None:
        return None

    text = str(value)
    if len(text) <= max_chars:
        return value

    return text[:max_chars] + "..."


def build_compact_db_meta(
    db_meta: Dict[str, Any],
    db_id: str,
    max_sample_chars: int = 120,
) -> Dict[str, Any]:
    """
    Build compact database metadata for LLM SQL instantiation.

    Keeps only:
        schema_name
        table_name
        table_tag
        col_name
        col_tag
        col_type
        sample_value
    """
    tables: List[Dict[str, Any]] = []

    for schema_name, table_name, table_info in iter_tables_from_meta(db_meta):
        columns = []

        for col in table_info.get("colname_list", []) or []:
            if not isinstance(col, dict):
                continue

            col_name = col.get("col_name")
            if not col_name:
                continue

            columns.append(
                {
                    "col_name": col_name,
                    "col_tag": col.get("col_tag"),
                    "col_type": col.get("col_type"),
                    "sample_value": truncate_value(
                        col.get("sample_value"),
                        max_chars=max_sample_chars,
                    ),
                }
            )

        tables.append(
            {
                "schema_name": schema_name,
                "table_name": table_name,
                "full_table_name": f"{schema_name}.{table_name}",
                "table_tag": table_info.get("table_tag"),
                "columns": columns,
            }
        )

    return {
        "db_id": db_id,
        "tables": tables,
    }


def build_sql_instantiation_user_prompt(
    sqa_payload: Dict[str, Any],
    compact_db_meta: Dict[str, Any],
    db_id: str,
    tier: str,
) -> str:
    """
    Build user prompt for SQL instantiation.
    """
    payload = {
        "db_id": db_id,
        "tier": tier,
        "sqa_templates": sqa_payload.get("sqa_templates", []),
        "database_metadata": compact_db_meta,
    }

    return (
        "# SQL Instantiation Input\n\n"
        "Instantiate the given SQAs on the provided database metadata.\n\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "```"
    )


def normalize_instance(
    item: Dict[str, Any],
    fallback_sqa_id: str,
) -> Dict[str, Any]:
    """
    Normalize one instance record.
    """
    sqa_id = item.get("sqa_id") or item.get("skeleton_id") or fallback_sqa_id
    status = item.get("status")

    if status not in {"instantiated", "skip"}:
        status = "skip"

    if status == "instantiated":
        event_scope = item.get("event_scope")
        tag_mapping = item.get("tag_mapping")
        sql = item.get("sql")
        question = item.get("question")
        notes = item.get("notes", "")

        if not isinstance(event_scope, str) or not event_scope.strip():
            status = "skip"
        if not isinstance(tag_mapping, dict) or not tag_mapping:
            status = "skip"
        if not isinstance(sql, str) or not sql.strip():
            status = "skip"
        if not isinstance(question, str) or not question.strip():
            status = "skip"

        if status == "instantiated":
            return {
                "sqa_id": str(sqa_id),
                "status": "instantiated",
                "event_scope": event_scope.strip(),
                "tag_mapping": {str(k): str(v) for k, v in tag_mapping.items()},
                "sql": sql.strip(),
                "question": question.strip(),
                "notes": str(notes).strip(),
            }

    notes = item.get("notes")
    if not isinstance(notes, str) or not notes.strip():
        notes = "Skipped because the SQA cannot be reasonably instantiated on this database."

    return {
        "sqa_id": str(sqa_id),
        "status": "skip",
        "event_scope": None,
        "tag_mapping": None,
        "sql": None,
        "question": None,
        "notes": notes.strip(),
    }


def normalize_sql_instantiation_output(
    raw_output: Dict[str, Any],
    db_id: str,
    tier: str,
    sqa_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Normalize the LLM output and ensure every SQA has one record.
    """
    expected_sqa_ids = [
        str(item["sqa_id"])
        for item in sqa_payload.get("sqa_templates", [])
        if isinstance(item, dict) and item.get("sqa_id")
    ]

    raw_instances = raw_output.get("instances", [])
    if not isinstance(raw_instances, list):
        raw_instances = []

    by_id: Dict[str, Dict[str, Any]] = {}

    for item in raw_instances:
        if not isinstance(item, dict):
            continue

        raw_sqa_id = item.get("sqa_id") or item.get("skeleton_id")
        if not raw_sqa_id:
            continue

        normalized = normalize_instance(item, fallback_sqa_id=str(raw_sqa_id))
        by_id[normalized["sqa_id"]] = normalized

    final_instances: List[Dict[str, Any]] = []

    for sqa_id in expected_sqa_ids:
        if sqa_id in by_id:
            final_instances.append(by_id[sqa_id])
        else:
            final_instances.append(
                {
                    "sqa_id": sqa_id,
                    "status": "skip",
                    "event_scope": None,
                    "tag_mapping": None,
                    "sql": None,
                    "question": None,
                    "notes": "The LLM did not return an instance for this SQA.",
                }
            )

    any_instantiated = any(
        item["status"] == "instantiated" for item in final_instances
    )

    return {
        "db_id": db_id,
        "tier": tier,
        "status": "ok" if any_instantiated else "no_instantiable_sqa",
        "instances": final_instances,
    }


def instantiate_sqa_for_db(
    sqa_payload: Dict[str, Any],
    db_meta: Dict[str, Any],
    prompt: str,
    llm_client: Any,
    db_id: str,
    tier: str,
    max_sample_chars: int = 120,
) -> Dict[str, Any]:
    """
    Instantiate all SQAs for one database.

    The LLM client must implement:
        chat(system_prompt: str, user_prompt: str) -> str
    """
    compact_db_meta = build_compact_db_meta(
        db_meta=db_meta,
        db_id=db_id,
        max_sample_chars=max_sample_chars,
    )

    user_prompt = build_sql_instantiation_user_prompt(
        sqa_payload=sqa_payload,
        compact_db_meta=compact_db_meta,
        db_id=db_id,
        tier=tier,
    )

    response_text = llm_client.chat(
        system_prompt=prompt,
        user_prompt=user_prompt,
    )

    raw_output = extract_json_object(response_text)

    return normalize_sql_instantiation_output(
        raw_output=raw_output,
        db_id=db_id,
        tier=tier,
        sqa_payload=sqa_payload,
    )


def instantiate_sqa_for_meta_file(
    sqa_file: str | Path,
    meta_file: str | Path,
    prompt_path: str | Path,
    output_file: str | Path,
    llm_client: Any,
    tier: Optional[str] = None,
    max_sample_chars: int = 120,
) -> Dict[str, Any]:
    """
    Instantiate SQAs for one database metadata file and save the result.
    """
    sqa_payload = load_sqa_templates(sqa_file)
    prompt = load_prompt(prompt_path)

    db_id = normalize_db_id_from_meta_path(meta_file)
    db_meta = load_json(meta_file)

    final_tier = tier or str(sqa_payload.get("tier", "unknown"))

    LOGGER.info("Instantiating SQA for db_id=%s, tier=%s", db_id, final_tier)

    result = instantiate_sqa_for_db(
        sqa_payload=sqa_payload,
        db_meta=db_meta,
        prompt=prompt,
        llm_client=llm_client,
        db_id=db_id,
        tier=final_tier,
        max_sample_chars=max_sample_chars,
    )

    write_json(result, output_file)

    instantiated_count = sum(
        1 for item in result.get("instances", []) if item.get("status") == "instantiated"
    )

    LOGGER.info(
        "Written SQL instances for db_id=%s to %s. Instantiated=%d/%d",
        db_id,
        output_file,
        instantiated_count,
        len(result.get("instances", [])),
    )

    return result