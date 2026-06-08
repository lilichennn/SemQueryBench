# Result Analysis

This directory contains the post-processing scripts for SemQueryBench result analysis.

The workflow starts from one Excel workbook with two sheets:

- sheet 1: dev
- sheet 2: test

The dev sheet may contain gold SQL and is used to demonstrate the full evaluation pipeline.
The test sheet is exported as a public prediction table without gold SQL.

## Step 1: Build evaluation tables

```bash
python result_analysis/scripts/prepare_evaluation_tables.py \
  --input "../BenchMark SOTA测试结果统计.xlsx" \
  --output-dir result_analysis
```

This generates:

```text
result_analysis/dev/dev_input_wide.xlsx
result_analysis/dev/dev_input_long.xlsx
result_analysis/test/test_predictions_public.xlsx
result_analysis/evaluation_submission_template.xlsx
```

## Step 2: Execute SQL on dev

Set MySQL credentials locally:

```powershell
$env:SEMQUERY_MYSQL_HOST="localhost"
$env:SEMQUERY_MYSQL_PORT="3306"
$env:SEMQUERY_MYSQL_USER="root"
$env:SEMQUERY_MYSQL_PASSWORD="your_password"
```

Then run:

```bash
python result_analysis/scripts/execute_sql_results.py \
  --input result_analysis/dev/dev_input_long.xlsx \
  --output result_analysis/dev/dev_executed_long.xlsx
```

## Step 3: Compare SQL on dev

Set LLM credentials locally:

```powershell
$env:SEMQUERY_LLM_API_KEY="your_api_key"
$env:SEMQUERY_LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:SEMQUERY_LLM_MODEL_EXEC="deepseek-v4-pro"
$env:SEMQUERY_LLM_MODEL_EFF="deepseek-v4-pro"
$env:SEMQUERY_LLM_MODEL_DIFF="kimi-k2.5"
```

Then run:

```bash
python result_analysis/scripts/compare_sql_results.py \
  --input result_analysis/dev/dev_executed_long.xlsx \
  --output result_analysis/dev/dev_compared_long.xlsx
```

## Step 4: Aggregate scores

```bash
python result_analysis/scripts/aggregate_scores.py \
  --input result_analysis/dev/dev_compared_long.xlsx \
  --output result_analysis/dev/dev_summary_scores.csv
```

## Public files

Recommended files to commit:

```text
result_analysis/README.md
result_analysis/scripts/
result_analysis/prompts/
result_analysis/configs/.env.example
result_analysis/evaluation_submission_template.xlsx
result_analysis/test/test_predictions_public.xlsx
```

Do not commit files containing full SQL execution outputs, passwords, API keys, private endpoints, local paths, or hidden SQA/template identifiers.
