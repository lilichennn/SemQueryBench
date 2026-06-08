import argparse
from pathlib import Path
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    df = pd.read_excel(args.input, dtype=object)
    for col in ["Execute Acc", "Efficient Acc"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    summary = (
        df.groupby(["Level", "method"], dropna=False)
          .agg(
              n=("id", "count"),
              EM=("Execute Acc", "mean"),
              EffM=("Efficient Acc", "mean"),
              execution_invalid=("pred-exec-status", lambda s: (pd.to_numeric(s, errors="coerce") == 0).mean() if len(s) else None),
          )
          .reset_index()
    )

    # Add overall rows by method.
    overall = (
        df.groupby(["method"], dropna=False)
          .agg(
              n=("id", "count"),
              EM=("Execute Acc", "mean"),
              EffM=("Efficient Acc", "mean"),
              execution_invalid=("pred-exec-status", lambda s: (pd.to_numeric(s, errors="coerce") == 0).mean() if len(s) else None),
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
