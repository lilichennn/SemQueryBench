"""
Extract GPT prediction records from compared-style JSON files under by_sheet.

Default input:
  results_analysis/by_sheet/

Default output:
  results_analysis/gpt_submit_units_easy_to_hard.json

The script reads per-sheet JSON files such as:
  easy_compared_style.json
  mid_compared_style.json
  hard_compared_style.json
or:
  easy_submission.json
  mid_submission.json
  hard_submission.json

It filters records where:
  model contains "GPT" (case-insensitive)

By default, only test sheets are included:
  easy, mid, hard, head

Dev sheets such as easy-dev, mid-dev, hard-dev are skipped unless --include-dev is passed.

The output record format is preserved exactly, except method names are normalized:
  Opensearch / OpenSearch-SQL / open_search -> OpenSearch
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List


TEST_SHEETS = {"easy", "mid", "medium", "hard", "head"}
DEV_SHEET_PATTERNS = {"easy-dev", "mid-dev", "medium-dev", "hard-dev", "head-dev"}


METHOD_CANONICAL = {
    "opensearch": "OpenSearch",
    "open-search": "OpenSearch",
    "open_search": "OpenSearch",
    "opensearch-sql": "OpenSearch",
    "open-search-sql": "OpenSearch",
    "open_search_sql": "OpenSearch",
    "dail-sql": "DAIL-SQL",
    "dail_sql": "DAIL-SQL",
    "mcs": "MCS",
    "mcs-sql": "MCS",
    "sdk": "SDK",
    "adeptsql": "AdeptSQL",
    "adeptsql-variant": "AdeptSQL-Variant",
}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def canonical_method(method: Any) -> str:
    raw = clean_text(method)
    key = raw.lower().replace(" ", "")
    key = key.replace("_", "-")
    return METHOD_CANONICAL.get(key, raw)


def infer_sheet_key(path: Path) -> str:
    name = path.stem
    name = re.sub(r"_compared_style$", "", name, flags=re.I)
    name = re.sub(r"_submission$", "", name, flags=re.I)
    name = re.sub(r"_compared_style_from_excel$", "", name, flags=re.I)
    return name.lower()


def is_dev_sheet(sheet_key: str) -> bool:
    return sheet_key.endswith("-dev") or sheet_key in DEV_SHEET_PATTERNS


def normalize_level(level: Any, sheet_key: str) -> str:
    value = clean_text(level).lower()
    if not value:
        value = sheet_key.replace("-dev", "")

    if value == "head":
        return "hard"
    if value == "medium":
        return "mid"
    return value


def is_gpt_model(model: Any, pattern: str) -> bool:
    return re.search(pattern, clean_text(model), flags=re.I) is not None


def collect_json_files(input_dir: Path) -> List[Path]:
    files = sorted(input_dir.glob("*.json"))
    return [
        p for p in files
        if p.is_file()
        and not p.name.lower().startswith("all_")
        and not p.name.lower().startswith("dev_")
        and not p.name.lower().startswith("test_")
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        default="results_analysis/by_sheet",
        help="Directory containing per-sheet compared-style JSON files.",
    )
    parser.add_argument(
        "--output",
        default="results_analysis/gpt_submit_units_easy_to_hard.json",
        help="Output JSON path.",
    )
    parser.add_argument(
        "--model-pattern",
        default=r"gpt",
        help="Regex used to select GPT models. Default: gpt",
    )
    parser.add_argument(
        "--include-dev",
        action="store_true",
        help="Include dev sheets such as easy-dev/mid-dev/hard-dev.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_path = Path(args.output)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    files = collect_json_files(input_dir)
    if not files:
        raise FileNotFoundError(f"No JSON files found in input directory: {input_dir}")

    selected: List[Dict[str, Any]] = []

    for path in files:
        sheet_key = infer_sheet_key(path)

        if is_dev_sheet(sheet_key) and not args.include_dev:
            print(f"[SKIP] dev sheet: {path.name}")
            continue

        base_sheet = sheet_key.replace("-dev", "")
        if base_sheet not in TEST_SHEETS and sheet_key not in TEST_SHEETS and not args.include_dev:
            print(f"[SKIP] unrecognized sheet: {path.name}")
            continue

        data = read_json(path)
        if not isinstance(data, list):
            print(f"[WARN] skipped non-list JSON: {path}")
            continue

        count = 0
        for item in data:
            if not isinstance(item, dict):
                continue

            if not is_gpt_model(item.get("model"), args.model_pattern):
                continue

            out = dict(item)
            out["Level"] = normalize_level(out.get("Level"), sheet_key)
            out["method"] = canonical_method(out.get("method"))
            selected.append(out)
            count += 1

        print(f"[INFO] {path.name}: selected {count} GPT records")

    write_json(output_path, selected)

    print()
    print("[DONE]")
    print(f"Total GPT records: {len(selected)}")
    print(f"Saved: {output_path}")

    by_level_method = {}
    for item in selected:
        key = (item.get("Level"), item.get("model"), item.get("method"))
        by_level_method[key] = by_level_method.get(key, 0) + 1

    print()
    print("Counts by Level / model / method:")
    for (level, model, method), n in sorted(by_level_method.items()):
        print(f"  {level} | {model} | {method}: {n}")


if __name__ == "__main__":
    main()
