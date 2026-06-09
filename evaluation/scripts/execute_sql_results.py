"""
Execute gold SQL and predicted SQL for SemQueryBench evaluation submissions.

Input:
  JSON list in long-format submission style.

Output:
  JSON list with execution results appended:
  - gold_exec_status
  - gold_result
  - gold_result_len
  - pred_exec_status
  - pred_result
  - pred_result_len
  - pred_exec_error

Notes:
  - This script only executes SQL and records results.
  - EM / EffM / diff desc should be computed in compare_sql_results.py.
  - A predicted SQL is considered invalid if it does not contain both SELECT and FROM.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pymysql
from pymysql import Error


_connections: Dict[str, pymysql.connections.Connection] = {}


def load_env_file(env_path: Path) -> None:
    """
    Load KEY=VALUE pairs from a local .env file.

    Existing environment variables take precedence.
    Lines starting with # are ignored.
    """
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def mysql_config() -> Dict[str, Any]:
    return {
        "host": os.getenv("SEMQUERY_MYSQL_HOST", "localhost"),
        "port": int(os.getenv("SEMQUERY_MYSQL_PORT", "3306")),
        "user": os.getenv("SEMQUERY_MYSQL_USER", "root"),
        "password": os.getenv("SEMQUERY_MYSQL_PASSWORD", ""),
        "charset": "utf8mb4",
        "autocommit": True,
    }


def get_connection(db_name: str):
    if db_name in _connections:
        try:
            _connections[db_name].ping(reconnect=False)
            return _connections[db_name]
        except Exception:
            del _connections[db_name]

    cfg = mysql_config()
    if not cfg["password"]:
        raise ValueError("SEMQUERY_MYSQL_PASSWORD is not set.")

    conn = pymysql.connect(database=db_name, **cfg)
    _connections[db_name] = conn
    return conn


def close_all_connections() -> None:
    for conn in _connections.values():
        conn.close()
    _connections.clear()


def normalize_sql_text(query: Any) -> str:
    return str(query or "").replace("\n", " ").replace("\r", " ").strip()


def is_valid_select_sql(query: Any) -> bool:
    sql = normalize_sql_text(query)
    if not sql:
        return False

    has_select = re.search(r"\bselect\b", sql, flags=re.IGNORECASE) is not None
    has_from = re.search(r"\bfrom\b", sql, flags=re.IGNORECASE) is not None
    return has_select and has_from


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def make_json_safe_rows(rows: Any) -> Any:
    if isinstance(rows, list):
        return [make_json_safe_rows(x) for x in rows]
    if isinstance(rows, tuple):
        return [make_json_safe_rows(x) for x in rows]
    if isinstance(rows, dict):
        return {str(k): make_json_safe_rows(v) for k, v in rows.items()}
    if rows is None or isinstance(rows, (str, int, float, bool)):
        return rows
    return json_safe(rows)


def execute_query(db_name: str, query: Any) -> Tuple[int, Any, str]:
    """
    Execute a SELECT-FROM SQL query.

    Returns:
      (status, result, error)
      status = 1 means execution succeeded.
      status = 0 means invalid SQL or execution failed.
    """
    if not is_valid_select_sql(query):
        return 0, None, "Failed to generate valid SQL"

    sql = normalize_sql_text(query)

    try:
        conn = get_connection(str(db_name))
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SET SESSION MAX_EXECUTION_TIME = 60000")
            cursor.execute(sql)
            result = cursor.fetchall()
            return 1, make_json_safe_rows(list(result)), ""
    except Error as e:
        return 0, None, f"Query execution failed: {e}"
    except Exception as e:
        return 0, None, f"Query execution failed: {e}"


def read_json_list(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Input JSON must be a list of records: {path}")

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Input record at index {i} is not an object.")

    return data


def write_json_list(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def require_columns(records: List[Dict[str, Any]], required: List[str]) -> None:
    missing_report = []
    for i, item in enumerate(records):
        missing = [c for c in required if c not in item]
        if missing:
            missing_report.append((i, missing))
        if len(missing_report) >= 5:
            break

    if missing_report:
        raise ValueError(f"Missing required fields in input records: {missing_report}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Submission JSON file.")
    parser.add_argument("--output", required=True, help="Output JSON file with execution results.")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--env-file", default="evaluation/configs/.env", help="Local .env file. Existing OS environment variables take precedence.")
    args = parser.parse_args()

    load_env_file(Path(args.env_file))

    input_path = Path(args.input)
    output_path = Path(args.output)

    records = read_json_list(input_path)

    required = ["Level", "id", "db_id", "Gold-sql", "model", "method", "pred-sql"]
    require_columns(records, required)

    gold_cache: Dict[Tuple[str, str], Tuple[int, Any, str]] = {}

    for idx, row in enumerate(records):
        print(
            f"Processing row {idx + 1}/{len(records)}: "
            f"id={row.get('id')}, model={row.get('model')}, method={row.get('method')}"
        )

        db_name = str(row["db_id"])
        gold_sql = row["Gold-sql"]
        pred_sql = row["pred-sql"]

        gold_key = (db_name, normalize_sql_text(gold_sql))
        if gold_key in gold_cache:
            gold_status, gold_result, gold_error = gold_cache[gold_key]
        else:
            gold_status, gold_result, gold_error = execute_query(db_name, gold_sql)
            gold_cache[gold_key] = (gold_status, gold_result, gold_error)

        row["gold_exec_status"] = gold_status
        row["gold_result"] = gold_result
        row["gold_result_len"] = len(gold_result) if gold_status and isinstance(gold_result, list) else None
        row["gold_exec_error"] = gold_error

        pred_status, pred_result, pred_error = execute_query(db_name, pred_sql)
        row["pred_exec_status"] = pred_status
        row["pred_result"] = pred_result
        row["pred_result_len"] = len(pred_result) if pred_status and isinstance(pred_result, list) else None
        row["pred_exec_error"] = pred_error
        row["pred-sql"] = normalize_sql_text(pred_sql)

        if (idx + 1) % args.batch_size == 0:
            write_json_list(output_path, records)
            print(f"Saved progress: {output_path}")

    write_json_list(output_path, records)
    close_all_connections()
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
