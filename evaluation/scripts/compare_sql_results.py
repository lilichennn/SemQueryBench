"""
Compare executed SemQueryBench predictions and compute:
- Execute Acc (EM) with deterministic result-containment matching
- Effective Acc (EffM) with LLM-as-judge
- SQL difference description with LLM-as-judge

Input:
  evaluation/submission/outputs/dev_executed.json

Output:
  evaluation/submission/outputs/dev_compared.json

EM rule:
  - gold SQL and predicted SQL must both execute successfully.
  - gold_result and pred_result must have the same number of rows.
  - For each gold row, there must be one predicted row that contains all gold row values.
  - Predicted rows may contain extra columns.
  - Column names are ignored.
  - If gold SQL contains ORDER BY, row order is respected; otherwise rows are matched unordered.

EffM rule:
  - pred SQL must execute successfully.
  - LLM judges whether pred SQL answers the user question, not whether it follows the gold SQL's exact reasoning.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI


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


def read_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def get_client() -> OpenAI:
    api_key = os.getenv("SEMQUERY_LLM_API_KEY")
    base_url = os.getenv("SEMQUERY_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    if not api_key:
        raise ValueError("SEMQUERY_LLM_API_KEY is not set.")

    return OpenAI(api_key=api_key, base_url=base_url)


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


def parse_json_object(text: Any) -> Dict[str, Any]:
    if not isinstance(text, str):
        text = str(text)

    text = text.replace("```json", "```").replace("```", "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Cannot parse JSON from LLM response: {text[:500]}")


def call_llm(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    model: str,
    max_retries: int = 5,
    delay: int = 5,
) -> Dict[str, Any]:
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                extra_body={"enable_thinking": False},
                stream=False,
            )
            content = completion.choices[0].message.content
            return parse_json_object(content)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"LLM call failed: {e}; retrying in {delay}s")
            time.sleep(delay)


def normalize_sql_text(sql: Any) -> str:
    return str(sql or "").replace("\n", " ").replace("\r", " ").strip()


def normalize_cell(value: Any) -> Any:
    """
    Normalize one SQL result cell for value-level comparison.

    Column names are intentionally ignored by the caller.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if math.isnan(value):
            return None
        return round(value, 6)

    # Numeric strings should compare with numeric values when possible.
    s = str(value).strip()
    if s == "":
        return ""

    try:
        f = float(s)
        if f.is_integer():
            return int(f)
        return round(f, 6)
    except Exception:
        return s.lower()


def row_values(row: Any) -> List[Any]:
    """
    Convert one SQL result row into normalized values.

    Supports:
    - DictCursor rows: {"col": value}
    - tuple/list rows
    - scalar fallback
    """
    if isinstance(row, dict):
        return [normalize_cell(v) for v in row.values()]

    if isinstance(row, (list, tuple)):
        return [normalize_cell(v) for v in row]

    return [normalize_cell(row)]


def gold_row_contained_in_pred_row(gold_row: Any, pred_row: Any) -> bool:
    """
    True if every value in gold_row appears in pred_row.

    This allows pred_row to contain extra selected columns.
    Duplicate values are handled as multiset values.
    """
    gold_values = row_values(gold_row)
    pred_unused = row_values(pred_row)

    for gv in gold_values:
        found = False
        for i, pv in enumerate(pred_unused):
            if gv == pv:
                pred_unused.pop(i)
                found = True
                break
        if not found:
            return False

    return True


def order_matters(gold_sql: Any) -> bool:
    return re.search(r"\border\s+by\b", normalize_sql_text(gold_sql), flags=re.IGNORECASE) is not None


def execution_match_by_containment(gold_result: Any, pred_result: Any, ordered: bool) -> Tuple[int, str]:
    """
    Deterministic EM rule.

    The predicted result is accepted when:
    - row count is identical;
    - each gold row is contained in a predicted row by values;
    - predicted rows may have extra columns;
    - column names are ignored.
    """
    if not isinstance(gold_result, list) or not isinstance(pred_result, list):
        return 0, "Gold or predicted execution result is not a list."

    if len(gold_result) != len(pred_result):
        return 0, f"Row count mismatch: gold={len(gold_result)}, pred={len(pred_result)}."

    if ordered:
        for idx, (g_row, p_row) in enumerate(zip(gold_result, pred_result), start=1):
            if not gold_row_contained_in_pred_row(g_row, p_row):
                return 0, f"Ordered row {idx} does not contain all gold values."
        return 1, "Predicted result contains all gold values with the same row order."

    pred_remaining = list(pred_result)

    for g_row in gold_result:
        matched_idx: Optional[int] = None
        for i, p_row in enumerate(pred_remaining):
            if gold_row_contained_in_pred_row(g_row, p_row):
                matched_idx = i
                break

        if matched_idx is None:
            return 0, "No predicted row contains all values from one gold row."

        pred_remaining.pop(matched_idx)

    return 1, "Predicted result contains all gold rows by value; extra predicted columns are ignored."


def build_eff_prompt(row: Dict[str, Any]) -> str:
    """
    EffM asks whether pred SQL answers the question, not whether it follows the gold SQL path.
    """
    return f"""User question:
{row.get('question', '')}

Gold SQL:
{row.get('Gold-sql', '')}

Predicted SQL:
{row.get('pred-sql', '')}

Predicted SQL execution status:
{row.get('pred_exec_status')}

Predicted SQL result length:
{row.get('pred_result_len')}

Predicted SQL result sample:
{str(row.get('pred_result'))[:3000]}

Judge whether the predicted SQL answers the user question. It does not need to follow the same reasoning path as the gold SQL. It must be executable and semantically sufficient for the question."""


def build_diff_prompt(row: Dict[str, Any]) -> str:
    return f"""User question:
{row.get('question', '')}

Gold SQL:
{row.get('Gold-sql', '')}

Predicted SQL:
{row.get('pred-sql', '')}
"""

def build_diff_type_prompt(row: Dict[str, Any]) -> str:
    return f"""User question:
{row.get('question', '')}

Gold SQL:
{row.get('Gold-sql', '')}

Predicted SQL:
{row.get('pred-sql', '')}

Execute Match:
{row.get('Execute Match')}

Effective Match:
{row.get('Effective Match')}

Diff desc:
{row.get('Diff desc', '')}

Predicted SQL execution status:
{row.get('pred_exec_status')}

Predicted SQL execution error:
{row.get('pred_exec_error', '')}
"""

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="evaluation/submission/outputs/dev_executed.json",
        help="Executed JSON file.",
    )
    parser.add_argument(
        "--output",
        default="evaluation/submission/outputs/dev_compared.json",
        help="Compared output JSON file.",
    )
    parser.add_argument("--prompt-dir", default="evaluation/prompts")
    parser.add_argument("--env-file", default="evaluation/configs/.env")
    parser.add_argument("--start-row", type=int, default=1, help="1-based row index for resume.")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--skip-effm", action="store_true", help="Skip LLM-based EffM.")
    parser.add_argument("--skip-diff", action="store_true", help="Skip LLM-based SQL diff description.")
    args = parser.parse_args()

    load_env_file(Path(args.env_file))

    prompt_dir = Path(args.prompt_dir)
    p_eff = read_prompt(prompt_dir / "efficient_acc.md")
    p_diff = read_prompt(prompt_dir / "compare_two_sql.md")
    p_diff_type = read_prompt(prompt_dir / "classify_diff_type.md")

    model_eff = os.getenv("SEMQUERY_LLM_MODEL_EFF", "deepseek-v4-pro")
    model_diff = os.getenv("SEMQUERY_LLM_MODEL_DIFF", "kimi-k2.5")
    model_diff_type = os.getenv("SEMQUERY_LLM_MODEL_DIFF_TYPE", model_diff)

    client = None
    if not args.skip_effm or not args.skip_diff:
        client = get_client()

    records = read_json_list(Path(args.input))

    for idx, row in enumerate(records):
        if idx + 1 < args.start_row:
            continue

        print(
            f"Comparing row {idx + 1}/{len(records)}: "
            f"id={row.get('id')}, model={row.get('model')}, method={row.get('method')}"
        )

        pred_sql = normalize_sql_text(row.get("pred-sql"))

        if not pred_sql:
            row["Execute Match"] = 0
            row["Execute diff desc"] = "Empty predicted SQL."
            row["Effective Match"] = 0
            row["Effective diff desc"] = "Empty predicted SQL."
            row["Diff desc"] = "Empty predicted SQL."
            continue

        if row.get("gold_exec_status") != 1:
            row["Execute Match"] = 0
            row["Execute diff desc"] = f"Gold SQL execution failed: {row.get('gold_exec_error', '')}"
        elif row.get("pred_exec_status") != 1:
            row["Execute Match"] = 0
            row["Execute diff desc"] = f"Predicted SQL cannot be executed: {row.get('pred_exec_error', '')}"
        else:
            em, em_desc = execution_match_by_containment(
                gold_result=row.get("gold_result"),
                pred_result=row.get("pred_result"),
                ordered=order_matters(row.get("Gold-sql")),
            )
            row["Execute Match"] = em
            row["Execute diff desc"] = em_desc

        # EffM prerequisite: predicted SQL must be executable.
        if row.get("pred_exec_status") != 1:
            row["Effective Match"] = 0
            row["Effective diff desc"] = f"Predicted SQL cannot be executed: {row.get('pred_exec_error', '')}"
        elif not args.skip_effm:
            eff_result = call_llm(client, p_eff, build_eff_prompt(row), model_eff)
            row["Effective Match"] = eff_result.get("Effective Match")
            row["Effective diff desc"] = eff_result.get("Effective diff desc")

        if not args.skip_diff:
            diff_result = call_llm(client, p_diff, build_diff_prompt(row), model_diff)
            row["Diff desc"] = diff_result.get("diff desc")
        elif "Diff desc" not in row:
            row["Diff desc"] = None

        if row.get("pred_exec_status") != 1:
            row["Diff Type"] = "Execution invalidity"
        elif row.get("Execute Match") == 1 and row.get("Effective Match") == 1:
            row["Diff Type"] = "Correct"
        else:
            diff_type_result = call_llm(client,p_diff_type, build_diff_type_prompt(row), model_diff_type)
            row["Diff Type"] = diff_type_result.get("Diff Type")

        if (idx + 1) % args.batch_size == 0:
            write_json_list(Path(args.output), records)
            print(f"Saved progress: {args.output}")

    write_json_list(Path(args.output), records)
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
