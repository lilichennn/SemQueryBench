"""
Database semantic tagging utilities for SemQueryBench construction.

Input format:
    dataset/
    ├── easy/
    │   └── all_meta/
    │       └── DB_ID.json
    ├── mid/
    │   └── all_meta/
    │       └── DB_ID.json
    └── hard/
        └── all_meta/
            └── DB_ID.json

Each all_meta/[db_id].json file should have the following structure:

{
  "TABLE_NAME": {
    "table_tag": "...",
    "colname_list": [
      {
        "col_name": "...",
        "col_tag": "...",
        "col_type": "...",
        "sample_value": "..."
      }
    ]
  }
}

The existing tags in all_meta are treated only as metadata and are not trusted
as final outputs. This script can regenerate table and column tags using an LLM.
"""

from __future__ import annotations

import json
import logging
import re
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


LOGGER = logging.getLogger(__name__)

DEFAULT_SCHEMA_NAME = "main"

STANDARD_TABLE_TAGS = {
    "MASTER",
    "TRANSACTION",
    "REFERENCE",
    "RELATION",
    "LOG",
    "DIMENSION",
}

STANDARD_COLUMN_TAGS = {
    "ID_MAIN",
    "ID_EXTERNAL",
    "ID_COMPOSITE",
    "NAME_PERSON",
    "NAME_ENTITY",
    "NAME_SHORT",
    "DESC_LONG",
    "TIME_EVENT",
    "TIME_CREATE",
    "TIME_UPDATE",
    "TIME_BIRTH",
    "TIME_DEADLINE",
    "VAL_AMOUNT",
    "VAL_SCORE",
    "VAL_PERCENT",
    "VAL_RATING",
    "VAL_QUANTITY",
    "CATEGORY_TOPIC",
    "STATUS_LIFE",
    "STATUS_WORK",
    "LEVEL",
    "REL_PERSON",
    "REL_ENTITY",
    "CONTACT_EMAIL",
    "CONTACT_PHONE",
    "CONTACT_URL",
    "LOCATION",
}

INDEX_TAGS = {"ID_MAIN", "ID_EXTERNAL", "ID_COMPOSITE"}


def find_all_meta_files(dataset_dir: str | Path) -> List[Path]:
    """
    Find all all_meta/*.json files under the SemQueryBench dataset directory.

    Expected layout:
        dataset/{easy,mid,hard}/all_meta/{db_id}.json
    """
    dataset_dir = Path(dataset_dir)

    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory does not exist: {dataset_dir}")

    meta_files = sorted(dataset_dir.glob("*/all_meta/*.json"))

    if not meta_files:
        raise FileNotFoundError(
            f"No all_meta JSON files found under {dataset_dir}. "
            "Expected layout: dataset/{easy,mid,hard}/all_meta/{db_id}.json"
        )

    return meta_files


def infer_tier_from_meta_path(meta_path: str | Path, dataset_dir: str | Path) -> str:
    """
    Infer tier from a metadata path.

    Example:
        dataset/easy/all_meta/WORD_VECTORS_US.json -> easy
    """
    meta_path = Path(meta_path)
    dataset_dir = Path(dataset_dir)

    relative = meta_path.relative_to(dataset_dir)
    parts = relative.parts

    if len(parts) < 3:
        return "unknown"

    return parts[0]


def load_all_meta_json(path: str | Path) -> Dict[str, Any]:
    """
    Load one all_meta/[db_id].json file.
    """
    path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a table dictionary in {path}")

    return data


def _truncate_sample_value(value: Any, max_chars: int = 100) -> Any:
    """
    Truncate long sample values to keep prompts compact.
    """
    if value is None:
        return None

    if isinstance(value, str):
        return value[:max_chars] if len(value) > max_chars else value

    value_str = str(value)
    return value_str[:max_chars] if len(value_str) > max_chars else value


def build_table_metadata_from_all_meta(
    db_id: str,
    table_name: str,
    table_info: Dict[str, Any],
    tier: str,
    source_file: str | Path,
    max_sample_chars: int = 100,
) -> Dict[str, Any]:
    """
    Build prompt-ready metadata for one table from all_meta JSON.
    """
    colname_list = table_info.get("colname_list", [])

    if not isinstance(colname_list, list):
        raise ValueError(f"Invalid colname_list for {db_id}.{table_name}")

    type_dict: Dict[str, str] = {}
    value_dict: Dict[str, Any] = {}
    original_col_tags: Dict[str, Any] = {}

    for col in colname_list:
        if not isinstance(col, dict):
            continue

        col_name = col.get("col_name")
        if not col_name:
            continue

        col_name = str(col_name)
        col_type = str(col.get("col_type", "UNKNOWN"))
        sample_value = _truncate_sample_value(col.get("sample_value"), max_chars=max_sample_chars)

        type_dict[col_name] = col_type
        value_dict[col_name] = sample_value
        original_col_tags[col_name] = col.get("col_tag")

    index_fields = [
        col_name
        for col_name in type_dict.keys()
        if any(keyword in col_name.upper() for keyword in ["ID", "INDEX", "CODE", "UID", "NO"])
    ]
    other_fields = [col_name for col_name in type_dict.keys() if col_name not in index_fields]
    sorted_column_names = index_fields + other_fields

    column_lines: List[str] = []

    for idx, col_name in enumerate(sorted_column_names):
        col_type = type_dict[col_name]
        sample_value = value_dict.get(col_name)

        if sample_value is None or sample_value == "":
            line = f"{idx + 1}. Field name: {col_name} | Type: {col_type}"
        elif isinstance(sample_value, str):
            line = (
                f"{idx + 1}. Field name: {col_name} | "
                f'Sample: "{sample_value}" | '
                f"Type: {col_type}"
            )
        else:
            line = (
                f"{idx + 1}. Field name: {col_name} | "
                f"Sample: {sample_value} | "
                f"Type: {col_type}"
            )

        column_lines.append(line)

    return {
        "database": db_id,
        "schema": DEFAULT_SCHEMA_NAME,
        "table": table_name,
        "tier": tier,
        "source_file": str(source_file),
        "original_table_tag": table_info.get("table_tag"),
        "original_col_tags": original_col_tags,
        "type_dict": type_dict,
        "value_dict": value_dict,
        "columns_prompt_lines": column_lines,
    }


def iter_table_metadata_from_dataset(
    dataset_dir: str | Path,
    max_sample_chars: int = 100,
) -> List[Dict[str, Any]]:
    """
    Convert all dataset/{tier}/all_meta/{db_id}.json files into per-table metadata.
    """
    dataset_dir = Path(dataset_dir)
    table_metadata_list: List[Dict[str, Any]] = []

    for meta_path in find_all_meta_files(dataset_dir):
        tier = infer_tier_from_meta_path(meta_path, dataset_dir)
        db_id = meta_path.stem
        db_meta = load_all_meta_json(meta_path)

        LOGGER.info(
            "Loaded %d tables from %s",
            len(db_meta),
            meta_path,
        )

        for table_name, table_info in db_meta.items():
            if not isinstance(table_info, dict):
                LOGGER.warning("Skip invalid table metadata: %s.%s", db_id, table_name)
                continue

            table_metadata = build_table_metadata_from_all_meta(
                db_id=db_id,
                table_name=table_name,
                table_info=table_info,
                tier=tier,
                source_file=meta_path,
                max_sample_chars=max_sample_chars,
            )
            table_metadata_list.append(table_metadata)

    return sorted(
        table_metadata_list,
        key=lambda x: (x["tier"], x["database"], x["table"]),
    )


def load_existing_tags(output_dir: str | Path) -> Tuple[set[Tuple[str, str, str]], Dict[str, Any]]:
    """
    Load previously generated tag files for resume mode.

    Output layout:
        output_dir/
        └── db_id.json

    Output JSON structure:
        {
          "main": {
            "table_name": {
              "table_tag": "...",
              "colname_list": [...]
            }
          }
        }
    """
    output_dir = Path(output_dir)
    processed: set[Tuple[str, str, str]] = set()
    all_results: Dict[str, Any] = {}

    if not output_dir.exists():
        return processed, all_results

    for json_path in sorted(output_dir.glob("*.json")):
        db_id = json_path.stem

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                db_data = json.load(f)
        except Exception as exc:
            LOGGER.warning("Failed to load existing tag file %s: %s", json_path, exc)
            continue

        all_results[db_id] = db_data

        if not isinstance(db_data, dict):
            continue

        for schema_name, schema_data in db_data.items():
            if not isinstance(schema_data, dict):
                continue

            for table_name in schema_data.keys():
                processed.add((db_id, schema_name, table_name))

    return processed, all_results


def reuse_duplicate_table_tags(
    all_results: Dict[str, Any],
    table_metadata: Dict[str, Any],
) -> bool:
    """
    Reuse tags if another table in the same database has identical column names and types.
    """
    db_id = table_metadata["database"]
    schema = table_metadata["schema"]
    table = table_metadata["table"]
    type_dict = table_metadata["type_dict"]

    if db_id not in all_results or schema not in all_results[db_id]:
        return False

    for existing_table, table_info in all_results[db_id][schema].items():
        if not isinstance(table_info, dict):
            continue

        existing_fields = {
            col.get("col_name"): col.get("col_type")
            for col in table_info.get("colname_list", [])
            if col.get("col_name")
        }

        if type_dict == existing_fields:
            LOGGER.info(
                "%s.%s has the same schema as %s.%s. Reusing existing tags.",
                db_id,
                table,
                db_id,
                existing_table,
            )
            all_results[db_id][schema][table] = table_info
            return True

    return False


def load_prompt(path: str | Path) -> str:
    """
    Load a prompt template.
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render_user_prompt(table_metadata: Dict[str, Any]) -> str:
    """
    Render user prompt for one table.
    """
    fields_info = "\n".join(table_metadata["columns_prompt_lines"])

    return f"""
# Database table to analyze

Database: {table_metadata["database"]}
Schema: {table_metadata["schema"]}
Table: {table_metadata["table"]}
Tier: {table_metadata["tier"]}

# Field information

{fields_info}
""".strip()


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


def normalize_table_tag(tag: Optional[str]) -> Optional[str]:
    if not tag:
        return None

    tag = str(tag).strip()
    return tag if tag in STANDARD_TABLE_TAGS else None


def normalize_column_tag(tag: Optional[str]) -> Optional[str]:
    if not tag:
        return None

    tag = str(tag).strip()
    return tag if tag in STANDARD_COLUMN_TAGS else None


def build_table_tag_record(
    llm_content: Dict[str, Any],
    type_dict: Dict[str, str],
    value_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert raw LLM output into normalized db tag format.
    """
    columns_from_llm = llm_content.get("columns", [])

    if not isinstance(columns_from_llm, list):
        columns_from_llm = []

    llm_tag_by_field = {
        item.get("field_name"): item.get("field_tag")
        for item in columns_from_llm
        if isinstance(item, dict)
    }

    colname_list: List[Dict[str, Any]] = []

    for col_name, col_type in type_dict.items():
        col_tag = normalize_column_tag(llm_tag_by_field.get(col_name))

        colname_list.append(
            {
                "col_name": col_name,
                "col_tag": col_tag,
                "col_type": col_type,
                "sample_value": value_dict.get(col_name),
            }
        )

    colname_list.sort(
        key=lambda x: (
            0 if x.get("col_tag") in INDEX_TAGS else 1,
            x.get("col_name") or "",
        )
    )

    return {
        "table_tag": normalize_table_tag(llm_content.get("table_tag")),
        "colname_list": colname_list,
    }


def save_database_tags(
    output_dir: str | Path,
    db_id: str,
    all_results: Dict[str, Any],
) -> None:
    """
    Save one database's tags to output_dir/db_id.json.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{db_id}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results.get(db_id, {}), f, ensure_ascii=False, indent=4)

    LOGGER.info("Saved database tags to %s", json_path)


def save_all_database_tags(output_dir: str | Path, all_results: Dict[str, Any]) -> None:
    for db_id in sorted(all_results.keys()):
        save_database_tags(output_dir, db_id, all_results)


def tag_one_table(
    table_metadata: Dict[str, Any],
    llm_client: Any,
    detailed_prompt: str,
    compact_prompt: Optional[str] = None,
    compact_threshold: int = 100,
    request_interval: float = 0.0,
) -> Dict[str, Any]:
    """
    Tag one table with an LLM client.

    The LLM client must implement:
        chat(system_prompt: str, user_prompt: str) -> str
    """
    column_count = len(table_metadata["columns_prompt_lines"])

    if compact_prompt is not None and column_count > compact_threshold:
        system_prompt = compact_prompt
    else:
        system_prompt = detailed_prompt

    user_prompt = render_user_prompt(table_metadata)

    if request_interval > 0:
        time.sleep(request_interval)

    response_text = llm_client.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    llm_content = extract_json_object(response_text)

    return build_table_tag_record(
        llm_content=llm_content,
        type_dict=table_metadata["type_dict"],
        value_dict=table_metadata["value_dict"],
    )


def tag_databases(
    dataset_dir: str | Path,
    output_dir: str | Path,
    llm_client: Any,
    detailed_prompt_path: str | Path,
    compact_prompt_path: Optional[str | Path] = None,
    compact_threshold: int = 100,
    resume: bool = True,
    save_every: int = 20,
    request_interval: float = 0.0,
    tier_filter: Optional[str] = None,
    db_id_filter: Optional[str] = None,
    table_filter: Optional[str] = None,
    limit: Optional[int] = None,
    max_sample_chars: int = 100,
) -> Dict[str, Any]:
    """
    Tag all databases in SemQueryBench all_meta metadata.
    """
    detailed_prompt = load_prompt(detailed_prompt_path)
    compact_prompt = load_prompt(compact_prompt_path) if compact_prompt_path else None

    table_metadata_list = iter_table_metadata_from_dataset(
        dataset_dir=dataset_dir,
        max_sample_chars=max_sample_chars,
    )

    if tier_filter:
        table_metadata_list = [
            item for item in table_metadata_list
            if item.get("tier") == tier_filter
        ]

    if db_id_filter:
        table_metadata_list = [
            item for item in table_metadata_list
            if item.get("database") == db_id_filter
        ]

    if table_filter:
        table_metadata_list = [
            item for item in table_metadata_list
            if item.get("table") == table_filter
        ]

    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be a positive integer.")
        table_metadata_list = table_metadata_list[:limit]

    total_tables = len(table_metadata_list)

    if resume:
        processed_tables, all_results = load_existing_tags(output_dir)
    else:
        processed_tables, all_results = set(), {}

    LOGGER.info(
        "Found %d tables after filters. tier=%s, db_id=%s, table=%s, limit=%s",
        total_tables,
        tier_filter,
        db_id_filter,
        table_filter,
        limit,
    )
    LOGGER.info("Resume mode: %s. Already processed tables: %d.", resume, len(processed_tables))

    successful_count = 0
    failed_count = 0

    for idx, table_metadata in enumerate(table_metadata_list, start=1):
        db_id = table_metadata["database"]
        schema = table_metadata["schema"]
        table = table_metadata["table"]
        table_key = (db_id, schema, table)

        try:
            LOGGER.info(
                "[%d/%d] Processing %s.%s",
                idx,
                total_tables,
                db_id,
                table,
            )

            if resume and table_key in processed_tables:
                LOGGER.info("Skip existing table: %s.%s", db_id, table)
                continue

            all_results.setdefault(db_id, {})
            all_results[db_id].setdefault(schema, {})

            if reuse_duplicate_table_tags(all_results, table_metadata):
                successful_count += 1
                continue

            table_record = tag_one_table(
                table_metadata=table_metadata,
                llm_client=llm_client,
                detailed_prompt=detailed_prompt,
                compact_prompt=compact_prompt,
                compact_threshold=compact_threshold,
                request_interval=request_interval,
            )

            all_results[db_id][schema][table] = table_record

            successful_count += 1

            if successful_count % save_every == 0:
                save_all_database_tags(output_dir, all_results)

        except Exception as exc:
            failed_count += 1
            LOGGER.error("Failed to process %s.%s: %s", db_id, table, exc)
            LOGGER.error(traceback.format_exc())
            continue

    save_all_database_tags(output_dir, all_results)

    LOGGER.info(
        "Tagging finished. Total tables: %d. Successful/new or reused: %d. Failed: %d.",
        total_tables,
        successful_count,
        failed_count,
    )

    return all_results