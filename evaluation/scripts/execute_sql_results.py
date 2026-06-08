import argparse
import os
import re
from ast import literal_eval

import pandas as pd
import pymysql
from pymysql import Error


_connections = {}


def mysql_config():
    return {
        "host": os.getenv("SEMQUERY_MYSQL_HOST", "localhost"),
        "port": int(os.getenv("SEMQUERY_MYSQL_PORT", "3306")),
        "user": os.getenv("SEMQUERY_MYSQL_USER", "root"),
        "password": os.getenv("SEMQUERY_MYSQL_PASSWORD", ""),
        "charset": "utf8mb4",
        "autocommit": True,
    }


def get_connection(db_name):
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


def close_all_connections():
    for conn in _connections.values():
        conn.close()


def execute_query(db_name, query):
    if pd.isna(query) or str(query).strip() == "":
        return 0, "Empty SQL"
    sql = str(query).replace("\n", " ").replace("\r", " ").strip()
    if sql == "PASS":
        return 0, "PASS"
    if sql == "未能生成有效的 SQL" or sql.lower() == "failed to generate valid sql":
        return 0, "Failed to generate valid SQL"

    try:
        conn = get_connection(str(db_name))
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SET SESSION MAX_EXECUTION_TIME = 60000")
            cursor.execute(sql)
            result = cursor.fetchall()
            return 1, result
    except Error as e:
        return 0, f"Query execution failed: {e}"
    except Exception as e:
        return 0, f"Query execution failed: {e}"


def normalize_sql_text(series):
    return series.astype(str).str.replace("\n", " ", regex=False).str.replace("\r", " ", regex=False).str.replace(r"\s+", " ", regex=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Long-format dev input Excel.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()

    df = pd.read_excel(args.input, dtype=object)

    required = ["Level", "id", "db_id", "question", "Gold-sql", "method", "pred-sql"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    for col in ["Gold-DATA", "Gold-DATA-LEN", "pred-data", "pred-data-len", "gold-exec-status", "pred-exec-status"]:
        if col not in df.columns:
            df[col] = None

    gold_cache = {}
    for idx, row in df.iterrows():
        print(f"Processing row {idx + 1}/{len(df)}: id={row['id']}, method={row['method']}")
        db_name = row["db_id"]

        gold_key = (db_name, row["Gold-sql"])
        if gold_key in gold_cache:
            gold_status, gold_res = gold_cache[gold_key]
        else:
            gold_status, gold_res = execute_query(db_name, row["Gold-sql"])
            gold_cache[gold_key] = (gold_status, gold_res)

        df.at[idx, "gold-exec-status"] = gold_status
        df.at[idx, "Gold-DATA"] = str(gold_res)
        df.at[idx, "Gold-DATA-LEN"] = len(gold_res) if gold_status and hasattr(gold_res, "__len__") else None

        pred_status, pred_res = execute_query(db_name, row["pred-sql"])
        df.at[idx, "pred-exec-status"] = pred_status
        df.at[idx, "pred-data"] = str(pred_res)
        df.at[idx, "pred-data-len"] = len(pred_res) if pred_status and hasattr(pred_res, "__len__") else None

        if (idx + 1) % args.batch_size == 0:
            df.to_excel(args.output, index=False)
            print(f"Saved progress: {args.output}")

    df["pred-sql"] = normalize_sql_text(df["pred-sql"])
    df.to_excel(args.output, index=False)
    close_all_connections()
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
