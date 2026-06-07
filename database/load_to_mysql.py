#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Load SemQueryBench CSV databases into MySQL.

Expected directory structure:

    database/full/
    ├── [db_name]/
    │   ├── [table_name].csv
    │   └── ...
    └── ...

Each subdirectory under database/full is treated as one MySQL database.
Each CSV file under a database directory is treated as one table.

Example:

    python database/load_to_mysql.py \
        --database-root database/full \
        --host localhost \
        --port 3306 \
        --user root \
        --password your_password \
        --reset

By default, the script does not delete existing databases. Use --reset only when
intentionally dropping existing user databases before importing.
"""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import pymysql
from pymysql import Error


SYSTEM_DATABASES = {"information_schema", "mysql", "performance_schema", "sys"}

TEXT_THRESHOLD = 255
MEDIUMTEXT_THRESHOLD = 65_535
LONGTEXT_THRESHOLD = 16_777_215


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load SemQueryBench CSV databases into MySQL."
    )
    parser.add_argument(
        "--database-root",
        default="database/full",
        help="Root directory containing database folders. Default: database/full",
    )
    parser.add_argument("--host", default="localhost", help="MySQL host.")
    parser.add_argument("--port", type=int, default=3306, help="MySQL port.")
    parser.add_argument("--user", required=True, help="MySQL user.")
    parser.add_argument(
        "--password",
        default=None,
        help=(
            "MySQL password. If omitted, the script reads MYSQL_PASSWORD "
            "from the environment or prompts for input."
        ),
    )
    parser.add_argument(
        "--charset",
        default="utf8mb4",
        help="MySQL charset. Default: utf8mb4",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all non-system databases before importing.",
    )
    parser.add_argument(
        "--fail-log",
        default="import_failures.txt",
        help="Path for the failure log. Default: import_failures.txt",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=1000,
        help="Batch size for inserting rows. Default: 1000",
    )
    return parser.parse_args()


def get_password(password_arg: Optional[str]) -> str:
    if password_arg is not None:
        return password_arg

    env_password = os.environ.get("MYSQL_PASSWORD")
    if env_password:
        return env_password

    return getpass.getpass("MySQL password: ")


def connect_mysql(
    host: str,
    port: int,
    user: str,
    password: str,
    charset: str,
    database: Optional[str] = None,
):
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset=charset,
        autocommit=False,
    )


def quote_identifier(identifier: str) -> str:
    return "`" + identifier.replace("`", "``") + "`"


def get_mysql_type_for_series(series: pd.Series, max_len: Optional[int] = None) -> str:
    if pd.api.types.is_integer_dtype(series):
        non_null = series.dropna()
        if len(non_null) == 0:
            return "BIGINT"

        min_value = non_null.min()
        max_value = non_null.max()

        if min_value >= 0 and max_value > 2**63 - 1:
            return "DECIMAL(20,0)"
        return "BIGINT"

    if pd.api.types.is_float_dtype(series):
        return "DOUBLE"

    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "DATETIME"

    if max_len is None:
        non_null = series.dropna()
        max_len = 1 if len(non_null) == 0 else int(non_null.astype(str).map(len).max())

    if max_len > LONGTEXT_THRESHOLD:
        return "LONGTEXT"
    if max_len > MEDIUMTEXT_THRESHOLD:
        return "MEDIUMTEXT"
    if max_len > TEXT_THRESHOLD:
        return "TEXT"
    return f"VARCHAR({max(1, int(max_len))})"


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace([np.inf, -np.inf], np.nan)

    for col in df.columns:
        if pd.api.types.is_unsigned_integer_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], downcast="integer")

    return df


def read_csv_file(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue

    return pd.read_csv(path)


def create_table(connection, table_name: str, df: pd.DataFrame) -> bool:
    if len(df.columns) == 0:
        print(f"    Warning: {table_name} has no columns. Skipped.")
        return False

    dtype_defs = []
    for col in df.columns:
        series = df[col]

        if series.dtype == "object":
            non_null = series.dropna()
            max_len = 1 if len(non_null) == 0 else int(non_null.astype(str).map(len).max())
        else:
            max_len = None

        mysql_type = get_mysql_type_for_series(series, max_len)
        dtype_defs.append(f"{quote_identifier(str(col))} {mysql_type}")

    create_sql = (
        f"CREATE TABLE {quote_identifier(table_name)} (\n  "
        + ",\n  ".join(dtype_defs)
        + "\n)"
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {quote_identifier(table_name)}")
            cursor.execute(create_sql)
        connection.commit()
        print(f"    Created table: {table_name} ({len(df.columns)} columns)")
        return True
    except Error as exc:
        print(f"    Failed to create table: {exc}")
        connection.rollback()
        return False


def dataframe_to_rows(df: pd.DataFrame) -> List[Tuple]:
    df_clean = df.replace({np.nan: None, pd.NaT: None})
    return [tuple(row) for row in df_clean.to_numpy()]


def insert_data(connection, table_name: str, df: pd.DataFrame, chunksize: int) -> bool:
    if len(df) == 0:
        print(f"    Warning: {table_name} has no rows.")
        return True

    columns = [quote_identifier(str(col)) for col in df.columns]
    placeholders = ", ".join(["%s"] * len(df.columns))
    insert_sql = (
        f"INSERT INTO {quote_identifier(table_name)} "
        f"({', '.join(columns)}) VALUES ({placeholders})"
    )

    rows = dataframe_to_rows(df)

    try:
        with connection.cursor() as cursor:
            for start in range(0, len(rows), chunksize):
                cursor.executemany(insert_sql, rows[start : start + chunksize])
        connection.commit()
        print(f"    Inserted {len(rows)} rows")
        return True
    except Error as exc:
        print(f"    Failed to insert data: {exc}")
        connection.rollback()
        return False


def drop_all_user_databases(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SHOW DATABASES")
        databases = [row[0] for row in cursor.fetchall()]

        dropped_count = 0
        for db_name in databases:
            if db_name not in SYSTEM_DATABASES:
                print(f"  Dropping database: {db_name}")
                cursor.execute(f"DROP DATABASE IF EXISTS {quote_identifier(db_name)}")
                dropped_count += 1

    connection.commit()
    print(f"Dropped {dropped_count} user databases")


def iter_database_dirs(database_root: Path) -> Iterable[Path]:
    for path in sorted(database_root.iterdir()):
        if path.is_dir():
            yield path


def iter_csv_files(db_path: Path) -> Iterable[Path]:
    for path in sorted(db_path.iterdir()):
        if path.is_file() and path.suffix.lower() == ".csv":
            yield path


def import_database(
    root_connection,
    db_path: Path,
    host: str,
    port: int,
    user: str,
    password: str,
    charset: str,
    chunksize: int,
) -> Tuple[int, int, List[str]]:
    db_name = db_path.name
    print(f"\n===== Importing database: {db_name} =====")

    failed_files: List[str] = []
    total_files = 0
    total_success = 0

    try:
        with root_connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {quote_identifier(db_name)} "
                f"CHARACTER SET {charset}"
            )
        root_connection.commit()
        print(f"Created database: {db_name}")
    except Error as exc:
        root_connection.rollback()
        print(f"Failed to create database {db_name}: {exc}")
        return total_files, total_success, [f"{db_name}: failed to create database - {exc}"]

    try:
        db_connection = connect_mysql(host, port, user, password, charset, database=db_name)
    except Error as exc:
        print(f"Failed to connect to database {db_name}: {exc}")
        return total_files, total_success, [f"{db_name}: failed to connect - {exc}"]

    csv_files = list(iter_csv_files(db_path))
    if not csv_files:
        print("  No CSV files found. Skipped.")
        db_connection.close()
        return total_files, total_success, failed_files

    print(f"  Found {len(csv_files)} CSV files")

    for csv_path in csv_files:
        total_files += 1
        relative_path = f"{db_name}/{csv_path.name}"
        table_name = csv_path.stem

        print(f"\n  Importing table: {table_name}")
        print(f"    Source file: {relative_path}")
        print(f"    File size: {csv_path.stat().st_size} bytes")

        try:
            df = read_csv_file(csv_path)
            print(f"    Loaded CSV: {len(df)} rows, {len(df.columns)} columns")
        except Exception as exc:
            print(f"    Failed to read CSV: {exc}")
            failed_files.append(f"{relative_path}: failed to read CSV - {exc}")
            continue

        try:
            df = prepare_dataframe(df)

            if not create_table(db_connection, table_name, df):
                failed_files.append(f"{relative_path}: failed to create table")
                continue

            if insert_data(db_connection, table_name, df, chunksize):
                total_success += 1
                print("    Success")
            else:
                failed_files.append(f"{relative_path}: failed to insert data")
        except Exception as exc:
            print(f"    Unexpected error: {exc}")
            failed_files.append(f"{relative_path}: unexpected error - {exc}")

    db_connection.close()
    return total_files, total_success, failed_files


def write_failure_log(path: Path, failed_files: List[str]) -> None:
    with path.open("w", encoding="utf-8") as file:
        file.write(f"Failed CSV files: {len(failed_files)}\n")
        file.write("=" * 80 + "\n")
        for item in failed_files:
            file.write(item + "\n")


def main() -> None:
    args = parse_args()
    database_root = Path(args.database_root)

    print("=" * 80)
    print("Loading SemQueryBench CSV databases into MySQL")
    print("=" * 80)
    print(f"Working directory: {Path.cwd()}")
    print(f"Database root: {database_root.resolve()}")

    if not database_root.is_dir():
        raise FileNotFoundError(
            f"Database root not found: {database_root.resolve()}\n"
            "Expected structure: database/full/[db_name]/[table_name].csv"
        )

    db_dirs = list(iter_database_dirs(database_root))
    print(f"Found {len(db_dirs)} database directories")

    password = get_password(args.password)

    try:
        root_connection = connect_mysql(
            args.host, args.port, args.user, password, args.charset
        )
        print("Connected to MySQL server")
    except Error as exc:
        raise RuntimeError(f"Failed to connect to MySQL server: {exc}") from exc

    if args.reset:
        print("\nReset mode enabled. Dropping all non-system databases.")
        confirm = input("Type 'RESET' to continue: ")
        if confirm != "RESET":
            print("Operation cancelled.")
            root_connection.close()
            return
        drop_all_user_databases(root_connection)

    total_files = 0
    total_success = 0
    all_failed_files: List[str] = []

    for db_path in db_dirs:
        db_total, db_success, db_failed = import_database(
            root_connection=root_connection,
            db_path=db_path,
            host=args.host,
            port=args.port,
            user=args.user,
            password=password,
            charset=args.charset,
            chunksize=args.chunksize,
        )
        total_files += db_total
        total_success += db_success
        all_failed_files.extend(db_failed)

    root_connection.close()

    print("\n" + "=" * 80)
    print("Import summary")
    print("=" * 80)
    print(f"Total CSV files: {total_files}")
    print(f"Successfully imported: {total_success}")
    print(f"Failed files: {len(all_failed_files)}")

    if all_failed_files:
        fail_log = Path(args.fail_log)
        write_failure_log(fail_log, all_failed_files)
        print(f"Failure details saved to: {fail_log.resolve()}")
    else:
        print("All CSV files were imported successfully.")

    print("Done.")


if __name__ == "__main__":
    main()
