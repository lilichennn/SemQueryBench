import argparse
import re
from pathlib import Path

import pandas as pd


BASE_FIELDS = {
    "level": "Level",
    "id": "id",
    "db_id": "db_id",
    "db-id": "db_id",
    "question": "question",
    "gold-sql": "Gold-sql",
    "gold_sql": "Gold-sql",
    "gold sql": "Gold-sql",
    "gold-data": "Gold-DATA",
    "gold-data-len": "Gold-DATA-LEN",
}

PUBLIC_DROP_PATTERNS = [
    r"(^|__)Gold-sql$",
    r"Gold-DATA",
    r"Gold-DATA-LEN",
    r"SQA",
    r"sqa",
    r"template",
    r"anchor",
    r"slot",
]

EXECUTION_DROP_PATTERNS = [
    r"Gold-DATA",
    r"Gold-DATA-LEN",
    r"pred-data",
    r"pred-data-len",
]


def clean(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x).strip())


def key(x):
    s = clean(x).lower()
    s = s.replace("_", "-")
    s = re.sub(r"\s+", "-", s)
    return s


def ff(values):
    out = []
    last = ""
    for x in values:
        s = clean(x)
        if s:
            last = s
        out.append(last)
    return out


def normalize_field_name(x):
    k = key(x)
    if k in BASE_FIELDS:
        return BASE_FIELDS[k]
    if re.search(r"pred[- ]?sql|predicted[- ]?sql", k):
        return "pred-sql"
    if re.search(r"execute[- ]?acc|execute[- ]?a", k):
        return "Execute Acc"
    if re.search(r"efficient[- ]?acc|efficient[- ]?a", k):
        return "Efficient Acc"
    if re.search(r"diff[- ]?desc", k):
        return "diff desc"
    return clean(x)


def flatten_columns(columns):
    # Excel has 3 header rows:
    # row 1: Bench / qwen-72b
    # row 2: method, e.g., MCS / Opensearch / DAIL-SQL / SDK
    # row 3: field, e.g., pred-sql / Execute Acc / Efficient Acc / diff desc
    row0 = ff([c[0] for c in columns])
    row1 = ff([c[1] for c in columns])
    row2 = [clean(c[2]) for c in columns]

    flat = []
    for model, method, field_raw in zip(row0, row1, row2):
        field = normalize_field_name(field_raw)
        fkey = key(field)

        if fkey in BASE_FIELDS:
            flat.append(BASE_FIELDS[fkey])
            continue

        if field in ["pred-sql", "Execute Acc", "Efficient Acc", "diff desc"]:
            m = clean(model)
            meth = clean(method)
            if not meth or meth.lower().startswith("unnamed"):
                meth = "unknown_method"
            if not m or m.lower().startswith("bench") or m.lower().startswith("unnamed"):
                m = "unknown_model"
            flat.append(f"{m}__{meth}__{field}")
            continue

        flat.append(field if field else "Unnamed")

    return dedupe(flat)


def dedupe(cols):
    seen = {}
    out = []
    for c in cols:
        if c not in seen:
            seen[c] = 0
            out.append(c)
        else:
            seen[c] += 1
            out.append(f"{c}.{seen[c]}")
    return out


def read_three_header_sheet(path, sheet):
    df = pd.read_excel(path, sheet_name=sheet, header=[0, 1, 2], dtype=object)
    df.columns = flatten_columns(df.columns)
    df = df.dropna(how="all")
    return df


def is_result_col(col):
    return bool(re.match(r".+__.+__(pred-sql|Execute Acc|Efficient Acc|diff desc)$", str(col)))


def split_result_col(col):
    parts = str(col).split("__")
    if len(parts) < 3:
        return None, None, None
    model = parts[0]
    method = parts[1]
    field = "__".join(parts[2:])
    return model, method, field


def wide_to_long(dev_wide):
    required = ["Level", "id", "db_id", "Gold-sql"]
    missing = [c for c in required if c not in dev_wide.columns]
    if missing:
        raise ValueError(f"Missing required dev columns: {missing}. Found columns: {list(dev_wide.columns)}")

    pred_cols = [c for c in dev_wide.columns if str(c).endswith("__pred-sql")]
    if not pred_cols:
        raise ValueError(f"No model__method__pred-sql columns found. Found columns: {list(dev_wide.columns)}")

    rows = []
    for _, row in dev_wide.iterrows():
        if pd.isna(row["id"]) or str(row["id"]).strip() == "":
            continue
        for pred_col in pred_cols:
            model, method, _ = split_result_col(pred_col)
            rows.append({
                "Level": row["Level"],
                "id": row["id"],
                "db_id": row["db_id"],
                "question": row["question"] if "question" in dev_wide.columns else "",
                "Gold-sql": row["Gold-sql"],
                "model": model,
                "method": method,
                "pred-sql": row[pred_col],
                "Execute Acc": row.get(f"{model}__{method}__Execute Acc"),
                "Efficient Acc": row.get(f"{model}__{method}__Efficient Acc"),
                "diff desc": row.get(f"{model}__{method}__diff desc"),
            })
    return pd.DataFrame(rows)


def drop_by_patterns(df, patterns):
    drop = [c for c in df.columns if any(re.search(p, str(c), re.I) for p in patterns)]
    return df.drop(columns=drop, errors="ignore")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Workbook with dev as sheet 1 and test as sheet 2.")
    parser.add_argument("--output-dir", default="result_analysis")
    parser.add_argument("--dev-sheet", default=0)
    parser.add_argument("--test-sheet", default=1)
    args = parser.parse_args()

    out = Path(args.output_dir)
    dev_dir = out / "dev"
    test_dir = out / "test"
    dev_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    dev_raw = read_three_header_sheet(args.input, args.dev_sheet)
    test_raw = read_three_header_sheet(args.input, args.test_sheet)

    dev_wide = drop_by_patterns(dev_raw, EXECUTION_DROP_PATTERNS)
    dev_long = wide_to_long(dev_wide)

    test_public = drop_by_patterns(test_raw, PUBLIC_DROP_PATTERNS + EXECUTION_DROP_PATTERNS)

    dev_wide_path = dev_dir / "dev_input_wide.xlsx"
    dev_long_path = dev_dir / "dev_input_long.xlsx"
    test_public_path = test_dir / "test_predictions_public.xlsx"
    template_path = out / "evaluation_submission_template.xlsx"

    dev_wide.to_excel(dev_wide_path, index=False)
    dev_long.to_excel(dev_long_path, index=False)
    test_public.to_excel(test_public_path, index=False)

    with pd.ExcelWriter(template_path, engine="openpyxl") as writer:
        dev_wide.to_excel(writer, sheet_name="dev_input_wide", index=False)
        dev_long.to_excel(writer, sheet_name="dev_input_long", index=False)
        test_public.to_excel(writer, sheet_name="test_public", index=False)

    print("Saved files:")
    print(dev_wide_path)
    print(dev_long_path)
    print(test_public_path)
    print(template_path)
    print("\nDetected dev columns:")
    for c in dev_wide.columns:
        print(c)


if __name__ == "__main__":
    main()
