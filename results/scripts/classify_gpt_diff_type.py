"""
Deduplicate GPT submit units and classify Diff Type.

Input:
  results_analysis/gpt_submit_units.json

Outputs:
  results_analysis/gpt_submit_units_dedup.json
  results_analysis/gpt_submit_units_with_diff_type.json

Dedup rule:
  keep the first record for each (Level, id).

Diff Type labels:
  - Schema grounding
  - Slot-function mismatch
  - Query-structure error
  - Condition error
  - Execution invalidity
  - Correct

Rules:
  - if pred_exec_status exists and is not 1 -> Execution invalidity
  - if Execute Match == 1 and Effective Match == 1 -> Correct
  - otherwise use LLM classifier based on question, gold SQL, pred SQL, match labels, and diff descriptions
  - if LLM returns Correct while either match is 0, fallback to a rule-based error type
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI


VALID_TYPES = {
    "Schema grounding error",
    "Query-structure error",
    "Condition error",
    "General generation error",
    "Execution invalidity",
    "Correct",
}


DEFAULT_CLASSIFY_PROMPT = """You are classifying Text-to-SQL prediction errors.

Given a user question, gold SQL, predicted SQL, Execute Match, Effective Match, and a natural-language SQL difference description, classify the main error type.

Choose all applicable labels from the following five categories:

1. Schema grounding error
The prediction fails to ground the learned query intent to the correct schema elements in the target database, including wrong tables, columns, or join keys.

2. Query-structure error
The prediction fails to reproduce the required SQL structure learned from the gold SQL pattern. This includes errors in SELECT composition, DISTINCT usage, aggregation, GROUP BY, HAVING... structure, or the overall SQL clause organization. Use this label when the predicted SQL uses broadly relevant tables/columns but the structural form of the query is wrong, missing, or over-simplified.

3. Condition error
The prediction fails to instantiate required constraints from the learned query pattern, including comparison operators, time windows, literals, thresholds, NULL filters, value lists, or other database-specific filtering rules.

4. General generation error
The prediction is wrong for reasons not directly attributable to schema transfer or SQA-pattern transfer, such as producing an overly generic query, omitting the main task intent, returning an irrelevant answer, or making a broad reasoning mistake not tied to schema grounding, SQL structure, or condition instantiation.

5. Execution invalidity
The predicted SQL cannot be executed due to syntax errors, schema errors, type errors, dialect errors, or invalid SQL generation.
6. If the prediction is correct, use:
Correct
## Important rule:
If Execute Match is 0 or Effective Match is 0, you must not return "Correct".
Only return "Correct" when both Execute Match and Effective Match are 1.

Return only valid JSON:

{
  "Primary Diff Type": "Condition error",
  "Diff Type": ["Condition error", "General generation error"]
}
"""
def canonical_diff_type(value: Any) -> str:
    s = str(value or "").strip()

    mapping = {
        "Schema grounding": "Schema grounding error",
        "Schema grounding error": "Schema grounding error",

        "Query-structure error": "Query-structure error",
        "Query structure error": "Query-structure error",

        "Condition error": "Condition error",

        "General generation error": "General generation error",
        "Non-transfer error": "General generation error",

        "Execution invalidity": "Execution invalidity",
        "Correct": "Correct",

        # Old removed label.
        "Slot-function mismatch": "General generation error",
    }

    return mapping.get(s, s)

def canonical_diff_type_list(value: Any) -> List[str]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = [value]
    else:
        raw_items = []

    out = []
    for x in raw_items:
        label = canonical_diff_type(x)
        if label in VALID_TYPES and label not in out:
            out.append(label)

    return out

def load_env_file(env_path: Path) -> None:
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


def read_json_list(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Input must be a JSON list: {path}")
    return data


def write_json_list(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def norm_level(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s == "head":
        return "hard"
    if s == "medium":
        return "mid"
    return s


def dedupe_by_level_id(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for r in records:
        key = (
            norm_level(r.get("Level")),
            str(r.get("id", "")).strip(),
            str(r.get("model", "")).strip(),
            str(r.get("method", "")).strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def as_int01(value: Any) -> int:
    s = str(value).strip().lower()
    if s in {"1", "1.0", "true", "yes", "correct"}:
        return 1
    return 0


def get_client() -> OpenAI:
    api_key = os.getenv("SEMQUERY_LLM_API_KEY")
    base_url = os.getenv("SEMQUERY_LLM_BASE_URL")
    if not api_key:
        raise ValueError("SEMQUERY_LLM_API_KEY is not set.")
    return OpenAI(api_key=api_key, base_url=base_url)


def parse_json_object(text: Any) -> Dict[str, Any]:
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("```json", "```").replace("```", "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"Cannot parse JSON from LLM response: {text[:300]}")


def call_llm(client: OpenAI, system_prompt: str, user_prompt: str, model: str, max_retries: int = 5, delay: int = 5) -> Dict[str, Any]:
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
            return parse_json_object(completion.choices[0].message.content)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"LLM call failed: {e}; retrying in {delay}s")
            time.sleep(delay)


def build_prompt(row: Dict[str, Any]) -> str:
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

Execute diff desc:
{row.get('Execute diff desc', '')}

Effective diff desc:
{row.get('Effective diff desc', '')}

Diff desc:
{row.get('Diff desc', '')}

Predicted SQL execution status:
{row.get('pred_exec_status', '')}

Predicted SQL execution error:
{row.get('pred_exec_error', '')}
"""

def fallback_type(row: Dict[str, Any]) -> str:
    """
    Rule-based fallback for the revised SemQueryBench error taxonomy.

    Taxonomy:
    1. Schema grounding error
    2. Query-structure error
    3. Condition error
    4. Non-transfer error
    5. Execution invalidity
    6. Correct

    This fallback is used when --skip-llm is enabled or when the LLM returns
    an invalid/inconsistent label.
    """
    pred_exec = row.get("pred_exec_status")
    if pred_exec not in [None, ""] and as_int01(pred_exec) != 1:
        return "Execution invalidity"

    execute_match = as_int01(row.get("Execute Match"))
    effective_match = as_int01(row.get("Effective Match"))

    if execute_match == 1 and effective_match == 1:
        return "Correct"

    text = " ".join([
        str(row.get("Execute diff desc", "")),
        str(row.get("Effective diff desc", "")),
        str(row.get("Diff desc", "")),
        str(row.get("pred_exec_error", "")),
    ]).lower()

    # 1. Execution invalidity
    # Use this only when the diff/error explicitly indicates executable-form failure.
    if any(x in text for x in [
        "cannot be executed", "execution failed", "query execution failed",
        "syntax error", "sql syntax", "invalid sql", "failed to generate valid sql",
        "unknown column", "unknown table", "doesn't exist", "does not exist",
        "type error", "data type", "dialect error", "mysql error"
    ]):
        return "Execution invalidity"

    # 2. Schema grounding error
    # Wrong target DB understanding: table, column, join key, schema element.
    # Put before query-structure because join-key mistakes may contain "join/连接".
    if any(x in text for x in [
        "wrong table", "incorrect table", "different table", "uses a different table",
        "uses the wrong table", "table mismatch", "target table",
        "wrong column", "incorrect column", "different column", "uses the wrong column",
        "wrong field", "incorrect field", "field mismatch", "column mismatch",
        "target column", "schema grounding", "schema element",
        "wrong join key", "incorrect join key", "join key mismatch",
        "wrong key", "incorrect key", "wrong relation", "incorrect relation"
    ]):
        return "Schema grounding error"

    # 3. Condition error
    # Wrong learned constraint/rule: operators, literals, thresholds, date/time windows,
    # NULL filters, value lists, extra/missing WHERE predicates.
    if any(x in text for x in [
        "where", "where clause", "predicate", "constraint",
        "filter", "filtered", "filtering", "condition", "extra condition",
        "missing condition", "incorrect condition", "wrong condition",
        "comparison operator", "operator", "threshold", "literal",
        "value list", "time window", "date range", "range condition",
        "between", "greater than", "less than",
        "is null", "is not null", "not null", "null filter",
        "extra filter", "missing filter", "incorrect filter", "wrong filter"
    ]):
        return "Condition error"

    # 4. Query-structure error
    # Learned SQL form is wrong: aggregation, grouping, ordering, DISTINCT, subquery,
    # CTE, joins as structure, window functions, SELECT composition, overall logic.
    if any(x in text for x in [
        "select missing", "missing selected column", "extra selected column",
        "selects extra", "selects fewer", "missing column in select",
        "aggregation", "aggregate", "group by", "having", "ordering", "order by",
        "limit", "top-k", "top k", "distinct", "missing distinct", "lacks distinct",
        "duplicate", "duplicates", "deduplicate", "row count mismatch",
        "subquery", "nested query", "cte", "common table expression",
        "join structure", "inner join", "left join", "right join", "full join",
        "join produces duplicate", "window function", "over partition",
        "percentile", "rank", "row_number", "dense_rank",
        "query structure", "sql structure", "sql logic", "overall logic",
        "wrong logic", "incorrect logic"
    ]):
        return "Query-structure error"

    # 5. Non-transfer error
    # Executable but wrong, and the diff does not clearly indicate schema grounding,
    # SQL structure transfer, or condition/rule transfer failure.
    return "Non-transfer error"

def fallback_types(row: Dict[str, Any]) -> Tuple[str, List[str]]:
    primary = fallback_type(row)
    return primary, [primary]

def classify_row(row: Dict[str, Any], client: OpenAI, prompt: str, model: str) -> Tuple[str, List[str]]:
    execute_match = as_int01(row.get("Execute Match"))
    effective_match = as_int01(row.get("Effective Match"))

    pred_exec = row.get("pred_exec_status")
    if pred_exec not in [None, ""] and as_int01(pred_exec) != 1:
        row["Diff Type source"] = "rule_execution_invalidity"
        row["LLM Primary Diff Type raw"] = ""
        row["LLM Diff Type raw"] = ""
        return "Execution invalidity", ["Execution invalidity"]

    if execute_match == 1 and effective_match == 1:
        row["Diff Type source"] = "rule_correct"
        row["LLM Primary Diff Type raw"] = ""
        row["LLM Diff Type raw"] = ""
        return "Correct", ["Correct"]

    result = call_llm(client, prompt, build_prompt(row), model)

    raw_primary = result.get("Primary Diff Type", "")
    raw_types = result.get("Diff Type", [])

    primary = canonical_diff_type(raw_primary)
    diff_types = canonical_diff_type_list(raw_types)

    row["LLM Primary Diff Type raw"] = raw_primary
    row["LLM Diff Type raw"] = raw_types

    if primary not in VALID_TYPES:
        row["Diff Type source"] = "fallback_invalid_primary_label"
        return fallback_types(row)

    if not diff_types:
        row["Diff Type source"] = "fallback_empty_diff_type_list"
        return fallback_types(row)

    if primary not in diff_types:
        diff_types.insert(0, primary)

    # Incorrect samples cannot be labeled only as Correct.
    if (execute_match == 0 or effective_match == 0) and "Correct" in diff_types:
        diff_types = [x for x in diff_types if x != "Correct"]

    if primary == "Correct" and (execute_match == 0 or effective_match == 0):
        row["Diff Type source"] = "fallback_inconsistent_correct"
        return fallback_types(row)

    if not diff_types:
        row["Diff Type source"] = "fallback_only_correct_removed"
        return fallback_types(row)

    row["Diff Type source"] = "llm"
    return primary, diff_types


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="results_analysis/gpt_submit_units.json")
    parser.add_argument("--dedup-output", default="results_analysis/gpt_submit_units_dedup.json")
    parser.add_argument("--output", default="results_analysis/gpt_submit_units_with_diff_type.json")
    parser.add_argument("--env-file", default="SemQueryBench/evaluation/configs/.env")
    parser.add_argument("--prompt-file", default="SemQueryBench/evaluation/prompts/classify_diff_type.md")
    parser.add_argument("--model", default=None)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--start-row", type=int, default=1)
    parser.add_argument("--skip-llm", action="store_true", help="Only apply deterministic Correct/Execution invalidity/fallback rules.")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel LLM calls.")
    args = parser.parse_args()

    records = read_json_list(Path(args.input))
    deduped = dedupe_by_level_id(records)
    write_json_list(Path(args.dedup_output), deduped)

    print(f"[INFO] input records: {len(records)}")
    print(f"[INFO] deduped records by (Level, id, model, method): {len(deduped)}")
    print(f"[INFO] saved deduped: {args.dedup_output}")

    prompt_path = Path(args.prompt_file)
    if prompt_path.exists():
        print(f"[INFO] Using prompt file: {prompt_path.resolve()}")
        prompt = prompt_path.read_text(encoding="utf-8")
    else:
        print("[WARN] Prompt file not found. Using DEFAULT_CLASSIFY_PROMPT embedded in script.")
        prompt = DEFAULT_CLASSIFY_PROMPT

    load_env_file(Path(args.env_file))
    model = args.model or os.getenv("SEMQUERY_LLM_MODEL_DIFF_TYPE") or os.getenv("SEMQUERY_LLM_MODEL_DIFF") or "kimi-k2.5"

    client = None if args.skip_llm else get_client()

    def classify_one(idx_row):
        idx, row = idx_row

        if args.skip_llm:
            em = as_int01(row.get("Execute Match"))
            effm = as_int01(row.get("Effective Match"))

            if em == 1 and effm == 1:
                primary_type, diff_types = "Correct", ["Correct"]
                row["Diff Type source"] = "rule_correct"
            else:
                primary_type, diff_types = fallback_types(row)
                row["Diff Type source"] = "fallback_skip_llm"
        else:
            primary_type, diff_types = classify_row(row, client, prompt, model)

        return idx, primary_type, diff_types


    items = [
        (idx, row)
        for idx, row in enumerate(deduped)
        if idx + 1 >= args.start_row
    ]

    completed = 0

    if args.skip_llm or args.workers <= 1:
        for idx, row in items:
            print(
                f"Classifying {idx + 1}/{len(deduped)}: "
                f"Level={row.get('Level')}, id={row.get('id')}, "
                f"method={row.get('method')}, model={row.get('model')}"
            )

            _, primary_type, diff_types = classify_one((idx, row))
            deduped[idx]["Primary Diff Type"] = primary_type
            deduped[idx]["Diff Type"] = diff_types
            completed += 1

            if completed % args.batch_size == 0:
                write_json_list(Path(args.output), deduped)
                print(f"[INFO] saved progress: {args.output}")

    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(classify_one, item): item[0]
                for item in items
            }

            for future in as_completed(futures):
                idx = futures[future]
                row = deduped[idx]

                try:
                    _, primary_type, diff_types = future.result()
                    deduped[idx]["Primary Diff Type"] = primary_type
                    deduped[idx]["Diff Type"] = diff_types
                    print(
                        f"[DONE] {idx + 1}/{len(deduped)}: "
                        f"Level={row.get('Level')}, id={row.get('id')}, "
                        f"method={row.get('method')}, model={row.get('model')} "
                        f"-> {primary_type} / {diff_types}"
                    )
                except Exception as e:
                    primary_type, diff_types = fallback_types(row)
                    deduped[idx]["Primary Diff Type"] = primary_type
                    deduped[idx]["Diff Type"] = diff_types
                    deduped[idx]["Diff Type error"] = str(e)
                    print(
                        f"[ERROR] {idx + 1}/{len(deduped)}: "
                        f"fallback -> {primary_type} / {diff_types}; error={e}"
                    )

                completed += 1

                if completed % args.batch_size == 0:
                    write_json_list(Path(args.output), deduped)
                    print(f"[INFO] saved progress: {args.output}")

    write_json_list(Path(args.output), deduped)
    print(f"[DONE] saved: {args.output}")


if __name__ == "__main__":
    main()
