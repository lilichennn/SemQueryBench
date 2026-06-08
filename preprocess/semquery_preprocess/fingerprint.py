"""
Database fingerprint construction for SemQueryBench.

This module converts tagged database metadata into compact database fingerprints.

Input:
    preprocess/outputs/db_tags/{db_id}.json

Tagged metadata format:
    {
      "main": {
        "table_name": {
          "table_tag": "MASTER",
          "colname_list": [
            {
              "col_name": "id",
              "col_tag": "ID_MAIN",
              "col_type": "TEXT",
              "sample_value": "..."
            }
          ]
        }
      }
    }

Output fingerprint format:
    {
      "MASTER": {
        "ID_MAIN": [
          {
            "path": "main.table_name.id",
            "type": "TEXT",
            "sample": "..."
          }
        ]
      }
    }
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


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


def iter_tables(db_meta: Dict[str, Any]) -> Iterable[Tuple[str, str, Dict[str, Any]]]:
    """
    Yield (schema_name, table_name, table_info) from tagged database metadata.

    Supports both:

    1. Schema-level structure:
        {
          "main": {
            "table_a": {"table_tag": "...", "colname_list": [...]}
          }
        }

    2. Flat table-level structure:
        {
          "table_a": {"table_tag": "...", "colname_list": [...]}
        }
    """
    if not isinstance(db_meta, dict):
        return

    # Flat table dictionary.
    if all(
        isinstance(value, dict) and ("table_tag" in value or "colname_list" in value)
        for value in db_meta.values()
    ):
        for table_name, table_info in db_meta.items():
            if isinstance(table_info, dict):
                yield "main", table_name, table_info
        return

    # Schema -> table dictionary.
    for schema_name, schema_obj in db_meta.items():
        if not isinstance(schema_obj, dict):
            continue

        for table_name, table_info in schema_obj.items():
            if isinstance(table_info, dict) and (
                "table_tag" in table_info or "colname_list" in table_info
            ):
                yield str(schema_name), str(table_name), table_info


def build_database_fingerprint(
    db_meta: Dict[str, Any],
    include_untagged_columns: bool = False,
    default_table_tag: str = "UNK",
    default_column_tag: str = "UNK",
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Build one database fingerprint.

    Structure:
        table_tag -> column_tag -> list[{path, type, sample}]
    """
    fingerprint: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    for schema_name, table_name, table_info in iter_tables(db_meta):
        table_tag = table_info.get("table_tag") or default_table_tag

        if table_tag not in fingerprint:
            fingerprint[table_tag] = {}

        columns = table_info.get("colname_list", []) or []

        for col in columns:
            if not isinstance(col, dict):
                continue

            col_name = col.get("col_name")
            if not col_name:
                continue

            col_tag = col.get("col_tag")

            if not col_tag:
                if not include_untagged_columns:
                    continue
                col_tag = default_column_tag

            if col_tag not in fingerprint[table_tag]:
                fingerprint[table_tag][col_tag] = []

            fingerprint[table_tag][col_tag].append(
                {
                    "path": f"{schema_name}.{table_name}.{col_name}",
                    "type": col.get("col_type"),
                    "sample": col.get("sample_value"),
                }
            )

    return fingerprint


def load_difficulty_tiers(
    difficulty_tiers_path: str | Path,
    db_col: str = "db_id",
    tier_col: str = "difficulty",
) -> pd.DataFrame:
    """
    Load difficulty tier assignments.
    """
    difficulty_tiers_path = Path(difficulty_tiers_path)

    if not difficulty_tiers_path.exists():
        raise FileNotFoundError(
            f"Difficulty tiers file does not exist: {difficulty_tiers_path}"
        )

    df = pd.read_csv(difficulty_tiers_path)

    required_cols = {db_col, tier_col}
    missing_cols = required_cols - set(df.columns)

    if missing_cols:
        raise ValueError(
            f"Difficulty tiers file is missing required columns: {sorted(missing_cols)}. "
            f"Available columns: {list(df.columns)}"
        )

    df = df[[db_col, tier_col]].copy()
    df.rename(columns={db_col: "db_id", tier_col: "tier"}, inplace=True)

    df["db_id"] = df["db_id"].astype(str)
    df["tier"] = df["tier"].astype(str)

    return df


def build_fingerprints_from_tiers(
    db_tags_dir: str | Path,
    difficulty_tiers_path: str | Path,
    output_dir: str | Path,
    include_untagged_columns: bool = False,
    db_col: str = "db_id",
    tier_col: str = "difficulty",
) -> pd.DataFrame:
    """
    Build fingerprints for databases selected in difficulty_tiers.csv.

    Returns:
        A summary dataframe with one row per processed database.
    """
    db_tags_dir = Path(db_tags_dir)
    output_dir = Path(output_dir)

    if not db_tags_dir.exists():
        raise FileNotFoundError(f"DB tags directory does not exist: {db_tags_dir}")

    tiers_df = load_difficulty_tiers(
        difficulty_tiers_path=difficulty_tiers_path,
        db_col=db_col,
        tier_col=tier_col,
    )

    rows: List[Dict[str, Any]] = []

    for _, row in tiers_df.iterrows():
        db_id = row["db_id"]
        tier = row["tier"]

        tag_path = db_tags_dir / f"{db_id}.json"

        if not tag_path.exists():
            LOGGER.warning("Skip %s because tagged meta file is missing: %s", db_id, tag_path)
            rows.append(
                {
                    "db_id": db_id,
                    "tier": tier,
                    "status": "missing_db_tags",
                    "fingerprint_path": None,
                    "table_tag_count": 0,
                    "column_tag_group_count": 0,
                    "field_count": 0,
                }
            )
            continue

        db_meta = load_json(tag_path)
        fingerprint = build_database_fingerprint(
            db_meta=db_meta,
            include_untagged_columns=include_untagged_columns,
        )

        fingerprint_path = output_dir / tier / f"{db_id}.json"
        write_json(fingerprint, fingerprint_path)

        table_tag_count = len(fingerprint)
        column_tag_group_count = sum(len(col_groups) for col_groups in fingerprint.values())
        field_count = sum(
            len(columns)
            for col_groups in fingerprint.values()
            for columns in col_groups.values()
        )

        rows.append(
            {
                "db_id": db_id,
                "tier": tier,
                "status": "ok",
                "fingerprint_path": str(fingerprint_path),
                "table_tag_count": table_tag_count,
                "column_tag_group_count": column_tag_group_count,
                "field_count": field_count,
            }
        )

        LOGGER.info("Written fingerprint for %s to %s", db_id, fingerprint_path)

    summary_df = pd.DataFrame(rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "fingerprint_summary.csv"
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    LOGGER.info("Written fingerprint summary to %s", summary_path)

    return summary_df