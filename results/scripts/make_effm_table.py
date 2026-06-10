import argparse
import json
import re
from pathlib import Path

import pandas as pd


TIER_ORDER = ["easy", "mid", "hard"]
SPLIT_ORDER = ["dev", "test"]

MODEL_ORDER = [
    "qwen-max",
    "deepseek-r1",
    "GPT-5.4",
    "Claude-OPU-4.6",
]

METHOD_ORDER = [
    "MCS",
    "DAIL",
    "OpenSearch",
    "Adept-V",
]


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON list: {path}")
    return data


def infer_sheet_name(path: Path) -> str:
    name = path.stem
    name = re.sub(r"_compared_style$", "", name, flags=re.I)
    name = re.sub(r"_submission$", "", name, flags=re.I)
    name = re.sub(r"_compared_style_from_excel$", "", name, flags=re.I)
    return name.lower()


def infer_tier_split(path: Path):
    sheet = infer_sheet_name(path)

    split = "dev" if sheet.endswith("-dev") else "test"
    tier = sheet.replace("-dev", "")

    if tier == "head":
        tier = "hard"
    if tier == "medium":
        tier = "mid"

    return tier, split


def canonical_method(method):
    s = str(method or "").strip()
    key = s.lower().replace("_", "-").replace(" ", "")

    mapping = {
        "mcs": "MCS",
        "mcs-sql": "MCS",
        "dail": "DAIL",
        "dail-sql": "DAIL",
        "opensearch": "OpenSearch",
        "open-search": "OpenSearch",
        "opensearch-sql": "OpenSearch",
        "open-search-sql": "OpenSearch",
        "sdk": "Adept-V",
        "adept-v": "Adept-V",
        "adeptsql": "Adept-V",
        "adeptsql-variant": "Adept-V",
    }

    return mapping.get(key, s)


def canonical_model(model):
    s = str(model or "").strip()
    key = s.lower().replace("_", "-").replace(" ", "")

    if key in {"qwen-max", "qwenmax", "qwen-72b", "qwen72b"}:
        return "qwen-max"

    if key in {"deepseek-r1", "deepseekr1"}:
        return "deepseek-r1"

    if "gpt" in key and "5.4" in key:
        return "GPT-5.4"

    if "claude" in key and ("opu" in key or "opus" in key):
        return "Claude-OPU-4.6"

    return s


def to_number(x):
    try:
        return float(x)
    except Exception:
        return None


def collect_records(input_dir: Path):
    rows = []

    for path in sorted(input_dir.glob("*.json")):
        tier, split = infer_tier_split(path)

        if tier not in TIER_ORDER:
            print(f"[SKIP] unknown tier file: {path.name}")
            continue

        data = read_json(path)

        for item in data:
            if not isinstance(item, dict):
                continue

            effm = to_number(item.get("Effective Match"))
            if effm is None:
                continue

            rows.append({
                "tier": tier,
                "split": split,
                "model": canonical_model(item.get("model")),
                "method": canonical_method(item.get("method")),
                "Effective Match": effm,
            })

        print(f"[INFO] loaded {path.name}: tier={tier}, split={split}, records={len(data)}")

    return pd.DataFrame(rows)


def build_table(df: pd.DataFrame):
    columns = pd.MultiIndex.from_product(
        [TIER_ORDER, SPLIT_ORDER],
        names=["tier", "split"]
    )

    index = pd.MultiIndex.from_product(
        [MODEL_ORDER, METHOD_ORDER],
        names=["model", "method"]
    )

    table = pd.DataFrame(index=index, columns=columns, dtype=object)

    grouped = (
        df.groupby(["model", "method", "tier", "split"], dropna=False)["Effective Match"]
          .mean()
          .reset_index()
    )

    for _, row in grouped.iterrows():
        model = row["model"]
        method = row["method"]
        tier = row["tier"]
        split = row["split"]
        value = row["Effective Match"]

        if model in MODEL_ORDER and method in METHOD_ORDER and tier in TIER_ORDER and split in SPLIT_ORDER:
            table.loc[(model, method), (tier, split)] = round(value, 4)

    return table


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="results_analysis/by_sheet")
    parser.add_argument("--output", default="results_analysis/effm_table_by_model_method_tier_split.csv")
    parser.add_argument("--output-xlsx", default="results_analysis/effm_table_by_model_method_tier_split.xlsx")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    df = collect_records(input_dir)

    if df.empty:
        raise ValueError("No records with Effective Match found.")

    table = build_table(df)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, encoding="utf-8-sig")

    with pd.ExcelWriter(args.output_xlsx) as writer:
        table.to_excel(writer, sheet_name="EffM")

    print("[DONE]")
    print(f"Records used: {len(df)}")
    print(f"Saved CSV:  {args.output}")
    print(f"Saved XLSX: {args.output_xlsx}")
    print()
    print(table)


if __name__ == "__main__":
    main()