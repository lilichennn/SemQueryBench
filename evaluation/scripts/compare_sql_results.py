import argparse
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI


def read_prompt(path):
    return Path(path).read_text(encoding="utf-8")


def get_client():
    api_key = os.getenv("SEMQUERY_LLM_API_KEY")
    base_url = os.getenv("SEMQUERY_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    if not api_key:
        raise ValueError("SEMQUERY_LLM_API_KEY is not set.")
    return OpenAI(api_key=api_key, base_url=base_url)


def parse_json_object(text):
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


def call_llm(client, system_prompt, user_prompt, model, max_retries=5, delay=5):
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


def build_user_prompts(row):
    if pd.isna(row.get("Gold-DATA-LEN")) or row.get("Gold-DATA-LEN") in [0, "0"]:
        exec_user = f"""User question: {row['question']}
gold_sql: {row['Gold-sql']}
pred_sql: {row['pred-sql']}"""
        exec_kind = "without_data"
    else:
        exec_user = f"""User question: {row['question']}
gold_sql: {row['Gold-sql']}
gold_sql_data: {row.get('Gold-DATA')}
gold_sql_data_len: {row.get('Gold-DATA-LEN')}
pred_sql: {row['pred-sql']}
pred_sql_data: {row.get('pred-data')}
pred_sql_data_len: {row.get('pred-data-len')}"""
        exec_kind = "with_data"

    eff_user = f"""User question: {row['question']}
gold_sql: {row['Gold-sql']}
pred_sql: {row['pred-sql']}"""

    diff_user = f"""User question: {row['question']}
gold_sql: {row['Gold-sql']}
pred_sql: {row['pred-sql']}"""

    return exec_kind, exec_user, eff_user, diff_user


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Executed long-format Excel.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--prompt-dir", default="result_analysis/prompts")
    parser.add_argument("--start-row", type=int, default=1, help="1-based row index for resume.")
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    prompt_dir = Path(args.prompt_dir)
    p_exec_with = read_prompt(prompt_dir / "execute_acc_with_data.md")
    p_exec_without = read_prompt(prompt_dir / "execute_acc_without_data.md")
    p_eff = read_prompt(prompt_dir / "efficient_acc.md")
    p_diff = read_prompt(prompt_dir / "compare_two_sql.md")

    model_exec = os.getenv("SEMQUERY_LLM_MODEL_EXEC", "deepseek-v4-pro")
    model_eff = os.getenv("SEMQUERY_LLM_MODEL_EFF", "deepseek-v4-pro")
    model_diff = os.getenv("SEMQUERY_LLM_MODEL_DIFF", "kimi-k2.5")

    client = get_client()
    df = pd.read_excel(args.input, dtype=object)

    for col in ["Execute Acc", "Execute diff desc", "Efficient Acc", "Efficient diff desc", "Diff desc"]:
        if col not in df.columns:
            df[col] = None

    for idx, row in df.iterrows():
        if idx + 1 < args.start_row:
            continue
        print(f"Comparing row {idx + 1}/{len(df)}: id={row.get('id')}, method={row.get('method')}")

        pred_sql = str(row.get("pred-sql", "")).strip()
        pred_data = str(row.get("pred-data", ""))

        if pred_sql in ["", "nan", "None"]:
            df.at[idx, "Execute Acc"] = 0
            df.at[idx, "Efficient Acc"] = 0
            df.at[idx, "Diff desc"] = "Empty predicted SQL"
            continue

        if "Query execution failed" in pred_data or "执行查询失败" in pred_data:
            df.at[idx, "Execute Acc"] = 0
            df.at[idx, "Efficient Acc"] = 0
            df.at[idx, "Execute diff desc"] = "Predicted SQL cannot be executed"
            df.at[idx, "Efficient diff desc"] = "Predicted SQL cannot be executed"
            df.at[idx, "Diff desc"] = pred_data
            continue

        exec_kind, exec_user, eff_user, diff_user = build_user_prompts(row)

        exec_prompt = p_exec_with if exec_kind == "with_data" else p_exec_without
        exec_result = call_llm(client, exec_prompt, exec_user, model_exec)
        df.at[idx, "Execute Acc"] = exec_result.get("Execute Acc")
        df.at[idx, "Execute diff desc"] = exec_result.get("Execute diff desc")

        eff_result = call_llm(client, p_eff, eff_user, model_eff)
        df.at[idx, "Efficient Acc"] = eff_result.get("Efficient Acc")
        df.at[idx, "Efficient diff desc"] = eff_result.get("Efficient diff desc")

        diff_result = call_llm(client, p_diff, diff_user, model_diff)
        df.at[idx, "Diff desc"] = diff_result.get("diff desc")

        if (idx + 1) % args.batch_size == 0:
            df.to_excel(args.output, index=False)
            print(f"Saved progress: {args.output}")

    df.to_excel(args.output, index=False)
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
