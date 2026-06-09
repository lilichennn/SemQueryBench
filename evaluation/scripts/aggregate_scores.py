import argparse
import json
from pathlib import Path

import pandas as pd


def read_json_list(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Input must be a JSON list: {path}")

    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="evaluation/submission/outputs/dev_compared.json"
    )
    parser.add_argument(
        "--output",
        default="evaluation/submission/outputs/dev_summary.csv"
    )
    args = parser.parse_args()

    records = read_json_list(Path(args.input))
    df = pd.DataFrame(records)

    required = ["Level", "method", "id", "Execute Match", "Effective Match"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["Execute Match"] = pd.to_numeric(df["Execute Match"], errors="coerce")
    df["Effective Match"] = pd.to_numeric(df["Effective Match"], errors="coerce")

    if "pred_exec_status" in df.columns:
        df["pred_exec_status"] = pd.to_numeric(df["pred_exec_status"], errors="coerce")
    else:
        df["pred_exec_status"] = None

    group_cols = ["Level", "method"]
    if "model" in df.columns:
        group_cols = ["Level", "model", "method"]

    summary = (
        df.groupby(group_cols, dropna=False)
          .agg(
              n=("id", "count"),
              EM=("Execute Match", "mean"),
              EffM=("Effective Match", "mean"),
              execution_invalid=(
                  "pred_exec_status",
                  lambda s: (pd.to_numeric(s, errors="coerce") == 0).mean()
                  if len(s) else None
              ),
          )
          .reset_index()
    )

    overall_group_cols = ["method"]
    if "model" in df.columns:
        overall_group_cols = ["model", "method"]

    overall = (
        df.groupby(overall_group_cols, dropna=False)
          .agg(
              n=("id", "count"),
              EM=("Execute Match", "mean"),
              EffM=("Effective Match", "mean"),
              execution_invalid=(
                  "pred_exec_status",
                  lambda s: (pd.to_numeric(s, errors="coerce") == 0).mean()
                  if len(s) else None
              ),
          )
          .reset_index()
    )

    overall.insert(0, "Level", "overall")

    result = pd.concat([summary, overall], ignore_index=True)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()