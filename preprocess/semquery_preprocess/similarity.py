"""
Schema-property similarity utilities for SemQueryBench construction.

This module computes database-level similarity from tagged database metadata.

Input:
    preprocess/outputs/db_tags/{db_id}.json

Each tagged metadata file should follow:

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

Similarity components:
    1. Table-type composition similarity
    2. Per-table property-signature similarity
    3. Table-level property co-occurrence similarity

Final similarity:
    sim = w_table * sim_table_types
        + w_signature * sim_property_signature
        + w_cooccurrence * sim_cooccurrence
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from scipy.spatial.distance import cosine
from tqdm import tqdm


LOGGER = logging.getLogger(__name__)

TYPE_BUCKETS = ["INT", "FLOAT", "TEXT", "DATE", "BOOL", "OTHER"]

DEFAULT_TABLE_TAGS = [
    "DIMENSION",
    "LOG",
    "MASTER",
    "REFERENCE",
    "RELATION",
    "TRANSACTION",
    "UNK",
]

DEFAULT_COLUMN_TAGS = [
    "CATEGORY_TOPIC",
    "CONTACT_EMAIL",
    "CONTACT_PHONE",
    "CONTACT_URL",
    "DESC_LONG",
    "ID_COMPOSITE",
    "ID_EXTERNAL",
    "ID_MAIN",
    "LEVEL",
    "LOCATION",
    "NAME_ENTITY",
    "NAME_PERSON",
    "NAME_SHORT",
    "REL_ENTITY",
    "REL_PERSON",
    "STATUS_LIFE",
    "STATUS_WORK",
    "TIME_BIRTH",
    "TIME_CREATE",
    "TIME_DEADLINE",
    "TIME_EVENT",
    "TIME_UPDATE",
    "VAL_AMOUNT",
    "VAL_PERCENT",
    "VAL_QUANTITY",
    "VAL_RATING",
    "VAL_SCORE",
    "UNK",
]


def load_json(path: str | Path) -> Any:
    path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tag_vocabs(tag_schema_path: str | Path | None = None) -> Tuple[List[str], List[str]]:
    """
    Load table and column tag vocabularies from preprocess/configs/db_tag_schema.json.

    This function supports common schema shapes. If parsing fails or no schema path is
    provided, it falls back to the built-in SemQueryBench tag vocabulary.
    """
    if tag_schema_path is None:
        return DEFAULT_TABLE_TAGS, DEFAULT_COLUMN_TAGS

    tag_schema_path = Path(tag_schema_path)

    if not tag_schema_path.exists():
        LOGGER.warning(
            "Tag schema file does not exist: %s. Falling back to default tags.",
            tag_schema_path,
        )
        return DEFAULT_TABLE_TAGS, DEFAULT_COLUMN_TAGS

    data = load_json(tag_schema_path)

    table_tags: set[str] = set()
    column_tags: set[str] = set()

    def collect_tags(obj: Any, target: set[str]) -> None:
        if isinstance(obj, dict):
            if "tag" in obj and obj["tag"] is not None:
                target.add(str(obj["tag"]))
            else:
                for key, value in obj.items():
                    # If the key itself looks like an uppercase tag, collect it.
                    if isinstance(key, str) and key.isupper() and "_" in key or key in {
                        "MASTER",
                        "TRANSACTION",
                        "REFERENCE",
                        "RELATION",
                        "LOG",
                        "DIMENSION",
                    }:
                        target.add(key)
                    collect_tags(value, target)
        elif isinstance(obj, list):
            for item in obj:
                collect_tags(item, target)

    # Preferred structured schema.
    if isinstance(data, dict):
        if "table_tags" in data:
            collect_tags(data["table_tags"], table_tags)
        elif "table_types" in data:
            collect_tags(data["table_types"], table_tags)
        elif "tags" in data and isinstance(data["tags"], dict):
            table_section = data["tags"].get("table_types") or data["tags"].get("table_tags")
            if table_section:
                collect_tags(table_section, table_tags)

        if "column_property_tags" in data:
            collect_tags(data["column_property_tags"], column_tags)
        elif "column_semantic_tags" in data:
            collect_tags(data["column_semantic_tags"], column_tags)
        elif "tags" in data and isinstance(data["tags"], dict):
            column_section = (
                data["tags"].get("column_semantic_tags")
                or data["tags"].get("column_property_tags")
                or data["tags"].get("column_tags")
            )
            if column_section:
                collect_tags(column_section, column_tags)

    table_tags = {tag for tag in table_tags if tag in set(DEFAULT_TABLE_TAGS) - {"UNK"}}
    column_tags = {tag for tag in column_tags if tag in set(DEFAULT_COLUMN_TAGS) - {"UNK"}}

    if not table_tags:
        table_tags = set(DEFAULT_TABLE_TAGS) - {"UNK"}

    if not column_tags:
        column_tags = set(DEFAULT_COLUMN_TAGS) - {"UNK"}

    table_vocab = sorted(table_tags)
    column_vocab = sorted(column_tags)

    if "UNK" not in table_vocab:
        table_vocab.append("UNK")

    if "UNK" not in column_vocab:
        column_vocab.append("UNK")

    return table_vocab, column_vocab


def load_db_tags(db_tags_dir: str | Path) -> Dict[str, Dict[str, Any]]:
    """
    Load all tagged database metadata files from a directory.

    Returns:
        {db_id: db_meta}
    """
    db_tags_dir = Path(db_tags_dir)

    if not db_tags_dir.exists():
        raise FileNotFoundError(f"DB tags directory does not exist: {db_tags_dir}")

    files = sorted(db_tags_dir.glob("*.json"))

    if not files:
        raise FileNotFoundError(f"No .json files found under {db_tags_dir}")

    db_metas: Dict[str, Dict[str, Any]] = {}

    for path in files:
        db_id = path.stem
        db_metas[db_id] = load_json(path)

    return db_metas


def db_iter_tables(db_meta: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    """
    Yield (table_name, table_info) across all schema roots.

    Expected format:
        {
          "main": {
            "table_name": {
              "table_tag": "...",
              "colname_list": [...]
            }
          }
        }

    Also tolerates flat format:
        {
          "table_name": {
            "table_tag": "...",
            "colname_list": [...]
          }
        }
    """
    if not isinstance(db_meta, dict):
        return

    # Flat table dictionary.
    if all(
        isinstance(v, dict) and ("table_tag" in v or "colname_list" in v)
        for v in db_meta.values()
    ):
        for table_name, table_info in db_meta.items():
            if isinstance(table_info, dict):
                yield table_name, table_info
        return

    # Schema -> table dictionary.
    for _, schema_obj in db_meta.items():
        if not isinstance(schema_obj, dict):
            continue

        for table_name, table_info in schema_obj.items():
            if isinstance(table_info, dict):
                yield table_name, table_info


def safe_cosine_sim(u: List[float], v: List[float]) -> float:
    """
    Compute cosine similarity safely for zero vectors.
    """
    u_arr = np.array(u, dtype=float)
    v_arr = np.array(v, dtype=float)

    if np.all(u_arr == 0) and np.all(v_arr == 0):
        return 1.0

    if np.all(u_arr == 0) or np.all(v_arr == 0):
        return 0.0

    try:
        dist = cosine(u_arr, v_arr)
        if np.isnan(dist) or np.isinf(dist):
            return 0.0
        return float(1.0 - dist)
    except Exception:
        return 0.0


def normalize_col_type(raw_type: str) -> str:
    """
    Map raw SQL/database column types into coarse type buckets.
    """
    if not raw_type:
        return "OTHER"

    s = str(raw_type).strip().upper()

    if any(x in s for x in ["INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "MEDIUMINT"]):
        return "INT"

    if any(x in s for x in ["FLOAT", "DOUBLE", "REAL", "DECIMAL", "NUMERIC", "MONEY", "NUMBER"]):
        return "FLOAT"

    if any(x in s for x in ["DATE", "TIME", "TIMESTAMP", "DATETIME", "YEAR"]):
        return "DATE"

    if any(x in s for x in ["BOOL", "BOOLEAN", "BIT"]):
        return "BOOL"

    if any(x in s for x in ["CHAR", "TEXT", "CLOB", "STRING", "VARCHAR", "NVARCHAR", "NCHAR"]):
        return "TEXT"

    return "OTHER"


def tag_group_counts(col_tags: List[str]) -> Dict[str, int]:
    """
    Aggregate fine-grained column tags into role groups.
    """
    id_main = col_tags.count("ID_MAIN")
    id_external = col_tags.count("ID_EXTERNAL")
    id_composite = col_tags.count("ID_COMPOSITE")

    rel_person = col_tags.count("REL_PERSON")
    rel_entity = col_tags.count("REL_ENTITY")

    time_cnt = sum(1 for tag in col_tags if tag.startswith("TIME_"))
    val_cnt = sum(1 for tag in col_tags if tag.startswith("VAL_"))

    status_cnt = sum(1 for tag in col_tags if tag.startswith("STATUS_"))
    category_cnt = col_tags.count("CATEGORY_TOPIC")
    level_cnt = col_tags.count("LEVEL")

    name_cnt = sum(1 for tag in col_tags if tag.startswith("NAME_"))
    desc_long_cnt = col_tags.count("DESC_LONG")

    contact_cnt = sum(1 for tag in col_tags if tag.startswith("CONTACT_"))
    location_cnt = col_tags.count("LOCATION")

    return {
        "id_main": id_main,
        "id_external": id_external,
        "id_composite": id_composite,
        "rel_person": rel_person,
        "rel_entity": rel_entity,
        "time": time_cnt,
        "val": val_cnt,
        "status": status_cnt,
        "category": category_cnt,
        "level": level_cnt,
        "name": name_cnt,
        "desc_long": desc_long_cnt,
        "contact": contact_cnt,
        "location": location_cnt,
    }


def get_table_type_composition(db_meta: Dict[str, Any], table_vocab: List[str]) -> List[float]:
    """
    Vector: normalized distribution of table tags in one database.
    """
    table_tags: List[str] = []

    valid_tags = set(table_vocab)

    for _, table_info in db_iter_tables(db_meta):
        table_tag = table_info.get("table_tag", "UNK") or "UNK"
        table_tag = table_tag if table_tag in valid_tags else "UNK"
        table_tags.append(table_tag)

    total = max(1, len(table_tags))
    counts = Counter(table_tags)

    return [counts.get(tag, 0) / total for tag in table_vocab]


def get_per_table_property_signature_stats(db_meta: Dict[str, Any]) -> List[float]:
    """
    Build per-table property role signature ratios and aggregate them into
    database-level moments.

    The vector contains:
        - weighted role-ratio moments
        - physical type bucket moments

    Moments per dimension:
        mean, std, max, p90
    """
    weight_config = {
        "id_main": 3.5,
        "id_external": 3.5,
        "id_composite": 3.0,
        "rel": 3.0,
        "val": 2.5,
        "time": 2.0,
        "status": 1.5,
        "category": 1.5,
        "level": 1.5,
        "name": 1.0,
        "contact_location": 1.0,
    }

    per_table_signature: List[List[float]] = []
    per_table_type: List[List[float]] = []

    for _, table_info in db_iter_tables(db_meta):
        cols = table_info.get("colname_list", []) or []

        col_tags = [(col.get("col_tag", "UNK") or "UNK") for col in cols]
        col_types = [normalize_col_type(col.get("col_type", "")) for col in cols]

        n_cols = max(1, len(cols))
        group_counts = tag_group_counts(col_tags)

        signature_row = [
            (group_counts["id_main"] / n_cols) * weight_config["id_main"],
            (group_counts["id_external"] / n_cols) * weight_config["id_external"],
            (group_counts["id_composite"] / n_cols) * weight_config["id_composite"],
            ((group_counts["rel_person"] + group_counts["rel_entity"]) / n_cols) * weight_config["rel"],
            (group_counts["time"] / n_cols) * weight_config["time"],
            (group_counts["val"] / n_cols) * weight_config["val"],
            (group_counts["status"] / n_cols) * weight_config["status"],
            (group_counts["category"] / n_cols) * weight_config["category"],
            (group_counts["level"] / n_cols) * weight_config["level"],
            ((group_counts["name"] + group_counts["desc_long"]) / n_cols) * weight_config["name"],
            ((group_counts["contact"] + group_counts["location"]) / n_cols) * weight_config["contact_location"],
        ]

        per_table_signature.append(signature_row)

        type_counts = Counter(col_types)
        type_row = [type_counts.get(bucket, 0) / n_cols for bucket in TYPE_BUCKETS]
        per_table_type.append(type_row)

    if not per_table_signature:
        per_table_signature = [[0.0] * 11]
        per_table_type = [[0.0] * len(TYPE_BUCKETS)]

    signature_matrix = np.array(per_table_signature, dtype=float)
    type_matrix = np.array(per_table_type, dtype=float)

    def moments(matrix: np.ndarray) -> np.ndarray:
        mean = matrix.mean(axis=0)
        std = matrix.std(axis=0)
        max_value = matrix.max(axis=0)
        p90 = np.percentile(matrix, 90, axis=0)
        return np.concatenate([mean, std, max_value, p90], axis=0)

    signature_vec = moments(signature_matrix)
    type_vec = moments(type_matrix)

    return np.concatenate([signature_vec, type_vec], axis=0).tolist()


def get_property_cooccurrence_hist(db_meta: Dict[str, Any]) -> List[float]:
    """
    Table-level property co-occurrence patterns normalized by number of tables.

    These patterns approximate structural query affordances, including time
    filtering, value aggregation, entity joins, grouping, and fact/dimension-like
    behavior.
    """
    flags = Counter()
    n_tables = 0

    for _, table_info in db_iter_tables(db_meta):
        n_tables += 1

        cols = table_info.get("colname_list", []) or []
        col_tags = [(col.get("col_tag", "UNK") or "UNK") for col in cols]
        group_counts = tag_group_counts(col_tags)

        has_time = group_counts["time"] > 0
        has_val = group_counts["val"] > 0
        has_status = group_counts["status"] > 0
        has_category = group_counts["category"] > 0
        rel_count = group_counts["rel_person"] + group_counts["rel_entity"]
        has_rel = rel_count > 0
        has_multi_rel = rel_count >= 2
        has_composite_id = group_counts["id_composite"] > 0
        has_text = (group_counts["name"] + group_counts["desc_long"]) > 0

        flags["time&val"] += int(has_time and has_val)
        flags["rel&val"] += int(has_rel and has_val)
        flags["status&time"] += int(has_status and has_time)
        flags["category&val"] += int(has_category and has_val)
        flags["multi_rel"] += int(has_multi_rel)
        flags["composite_id"] += int(has_composite_id)
        flags["composite&rel"] += int(has_composite_id and has_rel)
        flags["fact_like"] += int(has_val and (has_time or has_rel))
        flags["dim_like"] += int((has_text or has_category) and not has_val)

    n_tables = max(1, n_tables)

    keys = [
        "time&val",
        "rel&val",
        "status&time",
        "category&val",
        "multi_rel",
        "composite_id",
        "composite&rel",
        "fact_like",
        "dim_like",
    ]

    return [flags.get(key, 0) / n_tables for key in keys]


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


def tokenize_name(value: str) -> List[str]:
    if not value:
        return []
    return _TOKEN_PATTERN.findall(str(value).lower())


def lexical_similarity(db1_meta: Dict[str, Any], db2_meta: Dict[str, Any]) -> float:
    """
    Lightweight lexical similarity based on table and column name token overlap.
    This is not included in the final schema-property similarity score.
    """
    def collect_tokens(db_meta: Dict[str, Any]) -> set[str]:
        tokens: List[str] = []

        for table_name, table_info in db_iter_tables(db_meta):
            tokens.extend(tokenize_name(table_name))

            cols = table_info.get("colname_list", []) or []
            for col in cols:
                tokens.extend(tokenize_name(col.get("col_name", "")))

        return set(tokens)

    tokens_1 = collect_tokens(db1_meta)
    tokens_2 = collect_tokens(db2_meta)

    if not tokens_1 and not tokens_2:
        return 1.0

    if not tokens_1 or not tokens_2:
        return 0.0

    return len(tokens_1 & tokens_2) / len(tokens_1 | tokens_2)


def compare_databases(
    db1_meta: Dict[str, Any],
    db2_meta: Dict[str, Any],
    table_vocab: List[str],
    w_table: float = 0.35,
    w_signature: float = 0.40,
    w_cooccurrence: float = 0.25,
) -> Tuple[float, Dict[str, float]]:
    """
    Compute schema-property similarity between two databases.

    Returns:
        final_similarity, component_scores
    """
    weight_sum = w_table + w_signature + w_cooccurrence

    if abs(weight_sum - 1.0) > 1e-8:
        raise ValueError(
            f"Similarity weights must sum to 1.0, got {weight_sum}"
        )

    table_vec_1 = get_table_type_composition(db1_meta, table_vocab)
    table_vec_2 = get_table_type_composition(db2_meta, table_vocab)
    sim_table_types = safe_cosine_sim(table_vec_1, table_vec_2)

    signature_vec_1 = get_per_table_property_signature_stats(db1_meta)
    signature_vec_2 = get_per_table_property_signature_stats(db2_meta)
    sim_property_signature = safe_cosine_sim(signature_vec_1, signature_vec_2)

    cooc_vec_1 = get_property_cooccurrence_hist(db1_meta)
    cooc_vec_2 = get_property_cooccurrence_hist(db2_meta)
    sim_cooccurrence = safe_cosine_sim(cooc_vec_1, cooc_vec_2)

    final_similarity = (
        w_table * sim_table_types
        + w_signature * sim_property_signature
        + w_cooccurrence * sim_cooccurrence
    )

    return float(final_similarity), {
        "sim_table_types": float(sim_table_types),
        "sim_property_signature": float(sim_property_signature),
        "sim_cooccurrence": float(sim_cooccurrence),
    }


def compute_pairwise_similarity(
    db_metas: Dict[str, Dict[str, Any]],
    table_vocab: List[str],
    w_table: float = 0.35,
    w_signature: float = 0.40,
    w_cooccurrence: float = 0.25,
    include_lexical_similarity: bool = True,
) -> pd.DataFrame:
    """
    Compute pairwise schema-property similarity for all database pairs.
    """
    db_items = sorted(db_metas.items(), key=lambda x: x[0])
    total_pairs = len(db_items) * (len(db_items) - 1) // 2

    rows: List[Dict[str, Any]] = []

    for (db1_id, db1_meta), (db2_id, db2_meta) in tqdm(
        combinations(db_items, 2),
        total=total_pairs,
        desc="Computing database similarities",
        ncols=100,
        dynamic_ncols=True,
        leave=False,
    ):
        similarity, parts = compare_databases(
            db1_meta=db1_meta,
            db2_meta=db2_meta,
            table_vocab=table_vocab,
            w_table=w_table,
            w_signature=w_signature,
            w_cooccurrence=w_cooccurrence,
        )

        row = {
            "db1": db1_id,
            "db2": db2_id,
            "schema_property_similarity": similarity,
            "sim_table_types": parts["sim_table_types"],
            "sim_property_signature": parts["sim_property_signature"],
            "sim_cooccurrence": parts["sim_cooccurrence"],
        }

        if include_lexical_similarity:
            row["lexical_similarity"] = lexical_similarity(db1_meta, db2_meta)

        rows.append(row)

    df = pd.DataFrame(rows)

    if include_lexical_similarity and not df.empty:
        df.sort_values(
            ["schema_property_similarity", "lexical_similarity"],
            ascending=[False, True],
            inplace=True,
        )
    elif not df.empty:
        df.sort_values(
            ["schema_property_similarity"],
            ascending=[False],
            inplace=True,
        )

    return df


def pairwise_to_matrix(
    pairs_df: pd.DataFrame,
    db_ids: List[str],
    value_col: str = "schema_property_similarity",
) -> pd.DataFrame:
    """
    Convert pairwise long-form similarity results into a symmetric matrix.
    """
    matrix = pd.DataFrame(
        np.eye(len(db_ids), dtype=float),
        index=db_ids,
        columns=db_ids,
    )

    for _, row in pairs_df.iterrows():
        db1 = row["db1"]
        db2 = row["db2"]
        value = float(row[value_col])

        matrix.loc[db1, db2] = value
        matrix.loc[db2, db1] = value

    matrix.index.name = "db_id"
    return matrix


def write_similarity_outputs(
    pairs_df: pd.DataFrame,
    matrix_df: pd.DataFrame,
    output_dir: str | Path,
    pairs_filename: str = "db_similarity_pairs.csv",
    matrix_filename: str = "db_similarity_matrix.csv",
) -> Tuple[Path, Path]:
    """
    Write pairwise and matrix similarity CSV outputs.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pairs_path = output_dir / pairs_filename
    matrix_path = output_dir / matrix_filename

    pairs_df.to_csv(pairs_path, index=False, encoding="utf-8-sig")
    matrix_df.to_csv(matrix_path, encoding="utf-8-sig")

    return pairs_path, matrix_path