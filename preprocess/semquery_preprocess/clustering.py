"""
Difficulty-tier construction for SemQueryBench.

This module builds easy / mid / hard database tiers from a pairwise
schema-property similarity file.

Input pairwise CSV columns:
    db1
    db2
    schema_property_similarity

Main procedure:
    1. Convert similarity to distance: d(D_i, D_j) = 1 - Sim(D_i, D_j).
    2. Run average-linkage hierarchical clustering over the distance matrix.
    3. For each tier, search hierarchy branches with enough databases.
    4. Select a branch whose average intra-cluster distance is close to the
       tier target distance.
    5. Prune the branch using:
           L(C) = |AvgDist(C) - tau| + alpha * StdDist(C)
       until the target tier size is reached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, to_tree
from scipy.spatial.distance import squareform


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TierConfig:
    name: str
    target_distance: float
    size: int


@dataclass(frozen=True)
class TierMetrics:
    tier: str
    size: int
    target_distance: float
    avg_intra_distance: float
    std_distance: float
    diameter: float
    min_distance: float
    max_distance: float
    pruning_alpha: float


def load_similarity_pairs(
    similarity_pairs_path: str | Path,
    db1_col: str = "db1",
    db2_col: str = "db2",
    similarity_col: str = "schema_property_similarity",
) -> pd.DataFrame:
    """
    Load pairwise similarity CSV.
    """
    similarity_pairs_path = Path(similarity_pairs_path)

    if not similarity_pairs_path.exists():
        raise FileNotFoundError(
            f"Similarity pairs file does not exist: {similarity_pairs_path}"
        )

    df = pd.read_csv(similarity_pairs_path)

    required_cols = {db1_col, db2_col, similarity_col}
    missing_cols = required_cols - set(df.columns)

    if missing_cols:
        raise ValueError(
            f"Similarity file is missing required columns: {sorted(missing_cols)}. "
            f"Available columns: {list(df.columns)}"
        )

    df = df[[db1_col, db2_col, similarity_col]].copy()
    df.rename(
        columns={
            db1_col: "db1",
            db2_col: "db2",
            similarity_col: "similarity",
        },
        inplace=True,
    )

    df["db1"] = df["db1"].astype(str)
    df["db2"] = df["db2"].astype(str)
    df["similarity"] = pd.to_numeric(df["similarity"], errors="coerce")

    if df["similarity"].isna().any():
        bad_rows = df[df["similarity"].isna()]
        raise ValueError(
            f"Similarity column contains non-numeric values. "
            f"Example bad rows: {bad_rows.head(5).to_dict(orient='records')}"
        )

    return df


def build_similarity_matrix(
    pairs_df: pd.DataFrame,
) -> Tuple[List[str], pd.DataFrame]:
    """
    Build a symmetric similarity matrix from long-form pairwise results.
    """
    db_ids = sorted(set(pairs_df["db1"]) | set(pairs_df["db2"]))

    sim_matrix = pd.DataFrame(
        np.eye(len(db_ids), dtype=float),
        index=db_ids,
        columns=db_ids,
    )

    for _, row in pairs_df.iterrows():
        db1 = row["db1"]
        db2 = row["db2"]
        sim = float(row["similarity"])

        if sim < 0.0 or sim > 1.0:
            LOGGER.warning(
                "Similarity value outside [0, 1]: %s, %s, %.6f",
                db1,
                db2,
                sim,
            )

        sim_matrix.loc[db1, db2] = sim
        sim_matrix.loc[db2, db1] = sim

    return db_ids, sim_matrix


def similarity_to_distance_matrix(sim_matrix: pd.DataFrame) -> np.ndarray:
    """
    Convert similarity matrix to distance matrix.
    """
    dist_matrix = 1.0 - sim_matrix.values.astype(float)
    np.fill_diagonal(dist_matrix, 0.0)

    # Numerical guard.
    dist_matrix = np.clip(dist_matrix, 0.0, 1.0)

    return dist_matrix


def get_distance_metrics(
    indices: Sequence[int],
    dist_matrix: np.ndarray,
) -> Dict[str, float]:
    """
    Compute intra-cluster distance metrics for selected database indices.
    """
    indices = list(indices)

    if len(indices) < 2:
        return {
            "avg": 0.0,
            "std": 0.0,
            "diameter": 0.0,
            "min": 0.0,
            "max": 0.0,
        }

    sub_matrix = dist_matrix[np.ix_(indices, indices)]
    triu_idx = np.triu_indices(len(indices), k=1)
    distances = sub_matrix[triu_idx]

    return {
        "avg": float(distances.mean()),
        "std": float(distances.std()),
        "diameter": float(distances.max()),
        "min": float(distances.min()),
        "max": float(distances.max()),
    }


def distribution_aware_prune(
    indices: Sequence[int],
    dist_matrix: np.ndarray,
    target_size: int,
    target_distance: float,
    alpha: float = 1.5,
) -> List[int]:
    """
    Prune a candidate cluster until target_size is reached.

    At each step, remove the database whose removal gives the lowest penalty:

        |AvgDist(C) - target_distance| + alpha * StdDist(C)
    """
    current_indices = list(indices)

    if len(current_indices) < target_size:
        raise ValueError(
            f"Cannot prune cluster of size {len(current_indices)} "
            f"to larger target size {target_size}."
        )

    while len(current_indices) > target_size:
        best_remove_position = -1
        best_penalty = float("inf")

        for pos in range(len(current_indices)):
            candidate = current_indices[:pos] + current_indices[pos + 1 :]
            metrics = get_distance_metrics(candidate, dist_matrix)

            penalty = (
                abs(metrics["avg"] - target_distance)
                + alpha * metrics["std"]
            )

            if penalty < best_penalty:
                best_penalty = penalty
                best_remove_position = pos

        if best_remove_position < 0:
            raise RuntimeError("Failed to identify a database to prune.")

        current_indices.pop(best_remove_position)

    return current_indices


def find_refined_tier(
    dist_matrix: np.ndarray,
    target_distance: float,
    target_size: int,
    exclude: Optional[Sequence[int]] = None,
    alpha: float = 1.5,
) -> List[int]:
    """
    Find one tier from the hierarchical clustering tree.

    The function searches hierarchy nodes with at least target_size non-excluded
    databases, ranks them by closeness to target_distance and compactness, then
    prunes the best branch to target_size.
    """
    exclude_set = set(exclude or [])

    available_count = dist_matrix.shape[0] - len(exclude_set)
    if available_count < target_size:
        raise ValueError(
            f"Not enough remaining databases. Need {target_size}, "
            f"but only {available_count} remain."
        )

    condensed_distance = squareform(dist_matrix, checks=False)
    linkage_matrix = linkage(condensed_distance, method="average")
    _, node_list = to_tree(linkage_matrix, rd=True)

    candidates: List[Dict[str, object]] = []

    for node in node_list:
        idx = [i for i in node.pre_order() if i not in exclude_set]

        if len(idx) < target_size:
            continue

        metrics = get_distance_metrics(idx, dist_matrix)
        penalty = abs(metrics["avg"] - target_distance) + alpha * metrics["std"]

        candidates.append(
            {
                "indices": idx,
                "penalty": penalty,
                "avg": metrics["avg"],
                "std": metrics["std"],
                "size": len(idx),
            }
        )

    if not candidates:
        raise ValueError(
            f"No hierarchy branch contains at least {target_size} available databases."
        )

    candidates.sort(
        key=lambda item: (
            float(item["penalty"]),
            abs(float(item["avg"]) - target_distance),
            float(item["std"]),
            int(item["size"]),
        )
    )

    best_indices = candidates[0]["indices"]

    return distribution_aware_prune(
        indices=best_indices,  # type: ignore[arg-type]
        dist_matrix=dist_matrix,
        target_size=target_size,
        target_distance=target_distance,
        alpha=alpha,
    )


def build_difficulty_tiers(
    dist_matrix: np.ndarray,
    db_ids: Sequence[str],
    tier_configs: Sequence[TierConfig],
    alpha: float = 1.5,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build difficulty tiers sequentially.

    Returns:
        difficulty_tiers_df
        difficulty_metrics_df
        selected_distance_matrix_df
    """
    total_required = sum(config.size for config in tier_configs)

    if len(db_ids) < total_required:
        raise ValueError(
            f"Not enough databases for requested tier sizes. "
            f"Need {total_required}, got {len(db_ids)}. "
            f"For smoke tests, use smaller sizes, e.g. 1/1/1."
        )

    selected_by_tier: Dict[str, List[int]] = {}
    excluded: List[int] = []

    for config in tier_configs:
        LOGGER.info(
            "Selecting tier=%s, target_distance=%.4f, size=%d",
            config.name,
            config.target_distance,
            config.size,
        )

        tier_indices = find_refined_tier(
            dist_matrix=dist_matrix,
            target_distance=config.target_distance,
            target_size=config.size,
            exclude=excluded,
            alpha=alpha,
        )

        selected_by_tier[config.name] = tier_indices
        excluded.extend(tier_indices)

    rows: List[Dict[str, object]] = []
    metrics_rows: List[Dict[str, object]] = []

    all_selected_indices: List[int] = []

    for config in tier_configs:
        tier_indices = selected_by_tier[config.name]
        all_selected_indices.extend(tier_indices)

        metrics = get_distance_metrics(tier_indices, dist_matrix)

        metrics_rows.append(
            {
                "tier": config.name,
                "size": config.size,
                "target_distance": round(config.target_distance, 6),
                "avg_intra_distance": round(metrics["avg"], 6),
                "std_distance": round(metrics["std"], 6),
                "diameter": round(metrics["diameter"], 6),
                "min_distance": round(metrics["min"], 6),
                "max_distance": round(metrics["max"], 6),
                "pruning_alpha": alpha,
            }
        )

        for idx in tier_indices:
            rows.append(
                {
                    "db_id": db_ids[idx],
                    "difficulty": config.name,
                    "target_distance": config.target_distance,
                }
            )

    selected_db_ids = [db_ids[idx] for idx in all_selected_indices]
    selected_dist_matrix = dist_matrix[np.ix_(all_selected_indices, all_selected_indices)]

    selected_dist_df = pd.DataFrame(
        selected_dist_matrix,
        index=selected_db_ids,
        columns=selected_db_ids,
    )
    selected_dist_df.index.name = "db_id"

    difficulty_tiers_df = pd.DataFrame(rows)
    difficulty_metrics_df = pd.DataFrame(metrics_rows)

    return difficulty_tiers_df, difficulty_metrics_df, selected_dist_df


def write_clustering_outputs(
    difficulty_tiers_df: pd.DataFrame,
    difficulty_metrics_df: pd.DataFrame,
    selected_distance_matrix_df: pd.DataFrame,
    output_dir: str | Path,
    tiers_filename: str = "difficulty_tiers.csv",
    metrics_filename: str = "difficulty_metrics.csv",
    selected_matrix_filename: str = "selected_distance_matrix.csv",
) -> Tuple[Path, Path, Path]:
    """
    Write clustering outputs.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tiers_path = output_dir / tiers_filename
    metrics_path = output_dir / metrics_filename
    selected_matrix_path = output_dir / selected_matrix_filename

    difficulty_tiers_df.to_csv(tiers_path, index=False, encoding="utf-8-sig")
    difficulty_metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")
    selected_distance_matrix_df.to_csv(selected_matrix_path, encoding="utf-8-sig")

    return tiers_path, metrics_path, selected_matrix_path