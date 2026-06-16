# SemQueryBench

SemQueryBench is a Text-to-SQL benchmark for evaluating cross-database generalization under controlled schema-property similarity. The benchmark is designed to test whether a model can transfer query understanding to unseen databases, rather than only memorizing table-specific SQL patterns.

The released repository contains the benchmark data, database loading utilities, construction pipeline code, reproduced baseline code, and evaluation tools.

<p align="center">
  <img src="assets/sql_gen.png" width="900">
</p>

<p align="center">
  <b>Figure 1. Overview of SemQueryBench construction and evaluation.</b><br>
</p>

## Overview

SemQueryBench is built around a hidden semantic query abstraction process. During benchmark construction, databases are tagged with schema-property information, clustered by database similarity, and instantiated into natural-language questions and SQL queries through controlled query abstractions.

The public release follows a leakage-aware protocol:

- the released dataset contains Q-SQL pairs and database split information;
- hidden SQA templates, anchor mappings, slot mappings, and construction-time identifiers are not included in the public dataset;
- dev data can be used for local evaluation;
- test data does not expose gold SQL and should be evaluated through the hidden evaluator or benchmark maintainers.

## Repository Structure

```text
SemQueryBench/
├── dataset/
│   ├── easy/
│   ├── medium/
│   └── hard/
├── database/
│   ├── README.md
│   ├── load_to_mysql.py
│   ├── download_database.ps1
│   ├── checksums.txt
│   └── sample/
├── preprocess/
│   ├── README.md
│   ├── configs/
│   ├── prompts/
│   ├── scripts/
│   ├── semquery_preprocess/
│   └── outputs_sample/
├── baselines/
│   ├── README.md
│   ├── DAIL-SQL/
│   ├── OpenSearch-SQL/
│   ├── mcs_sql/
│   └── adeptsql_variant/
├── evaluation/
│   ├── README.md
│   ├── RESULT_FORMAT.md
│   ├── configs/
│   ├── prompts/
│   ├── scripts/
│   └── submission/
├── results/
│   └── README.md
└── README.md
```

## Dataset

The benchmark is organized by difficulty tier:

```text
dataset/{tier}/
├── train/
├── dev/
└── test_public/
```

where `{tier}` is one of:

```text
easy
medium
hard
```

Each split contains:

```text
{split}.json
{split}.sql
{split}_tables.json
{split}_databases/
```

For example:

```text
dataset/easy/train/train.json
dataset/easy/train/train.sql
dataset/easy/train/train_tables.json
dataset/easy/train/train_databases/
```

### Data Files

`{split}.json` contains natural-language questions and SQL annotations. For train and dev splits, records use the following format:

```json
{
  "question_id": 1,
  "db_id": "USFS_FIA",
  "question": "In the forest land area estimation data, which states have the largest subplot area? Please list the top 5 states.",
  "evidence": "",
  "SQL": "SELECT state_name FROM USFS_FIA.ESTIMATED_FORESTLAND_ACRES ORDER BY subplot_acres DESC LIMIT 5;"
}
```

For `test_public`, the `SQL` field is removed:

```json
{
  "question_id": 1,
  "db_id": "IDC",
  "question": "In image data sharing platforms (IDC), which raw datasets have the largest number of samples? The top five listed companies.",
  "evidence": ""
}
```

`{split}.sql` contains one gold SQL query per line when gold SQL is public for the split.

`{split}_tables.json` contains database schema metadata following a BIRD/Spider-style table metadata format.

`{split}_databases/` contains split-specific database files organized by database ID.

## Database

The `database/` directory contains utilities for obtaining and loading the released databases.

```text
database/
├── README.md
├── load_to_mysql.py
├── download_database.ps1
├── checksums.txt
└── sample/
```

The full database package is released separately as a GitHub Release asset. After download and extraction, the expected layout is:

```text
database/full/{db_id}/{table_name}.csv
```

To load databases into MySQL, see:

```text
database/README.md
```

and run:

```bash
python database/load_to_mysql.py --data_dir database/full --host localhost --user root
```

Use command-line arguments, environment variables, or password prompt for credentials. Do not commit passwords or local credentials.

## Preprocess

The `preprocess/` directory contains the benchmark construction pipeline.

```text
preprocess/scripts/
├── build_db_tags.py
├── compute_db_similarity.py
├── build_difficulty_tiers.py
├── build_fingerprints.py
├── build_sqa.py
└── instantiate_sql.py
```

The construction stages are:

1. database semantic tagging;
2. database similarity computation;
3. difficulty tier construction;
4. database fingerprint generation;
5. anchor matrix and SQA generation;
6. SQL and question instantiation.

A small sanitized example is provided under:

```text
preprocess/outputs_sample/
```

Full construction outputs from SQA generation and downstream SQL/question instantiation are not released, because they contain hidden SQA templates, anchor mappings, slot-level mappings, and intermediate artifacts that may leak benchmark structure.

See:

```text
preprocess/README.md
```

for pipeline details.

## Baselines

The `baselines/` directory contains reproduced baseline code and running notes for representative Text-to-SQL methods.

```text
baselines/
├── DAIL-SQL/
├── OpenSearch-SQL/
├── mcs_sql/
└── adeptsql_variant/
```

The baseline code is organized according to each method's original workflow. A unified runner is not enforced because the compared methods use different dependencies, input conventions, and execution pipelines.

See:

```text
baselines/README.md
```

for method-specific notes.

## Evaluation

The `evaluation/` directory provides the evaluation scripts and submission format.

```text
evaluation/
├── README.md
├── RESULT_FORMAT.md
├── configs/
├── prompts/
├── scripts/
└── submission/
```

The evaluation pipeline computes:

- **Execute Match (EM)**: deterministic result-containment matching between gold SQL and predicted SQL execution results;
- **Effective Match (EffM)**: LLM-based judgment of whether the predicted SQL answers the user question;
- **Diff desc**: natural-language description of the SQL-level difference;
- **Diff Type**: error category assigned from the predefined taxonomy.

### Dev Evaluation

Prepare a dev submission JSON:

```text
evaluation/submission/dev_submission_example.json
```

Then run:

```powershell
python evaluation/scripts/execute_sql_results.py `
  --input evaluation/submission/dev_submission_example.json `
  --output evaluation/submission/outputs/dev_executed.json
```

Next compute EM, EffM, and SQL difference descriptions:

```powershell
python evaluation/scripts/compare_sql_results.py `
  --input evaluation/submission/outputs/dev_executed.json `
  --output evaluation/submission/outputs/dev_compared.json
```

Finally aggregate scores:

```powershell
python evaluation/scripts/aggregate_scores.py `
  --input evaluation/submission/outputs/dev_compared.json `
  --output evaluation/submission/outputs/dev_summary.csv
```

See:

```text
evaluation/README.md
evaluation/RESULT_FORMAT.md
```

for complete evaluation details.

### Test Evaluation

Public test files do not include gold SQL. Users can generate predictions for test instances, but official test EM/EffM requires hidden gold SQL. The intended workflow is:

```text
test submission
→ hidden gold SQL added by maintainers/evaluation server
→ SQL execution
→ EM/EffM/diff analysis
→ official test scores
```

## Error Taxonomy

SemQueryBench uses the following error categories for result analysis:

- **Schema grounding**: wrong table, column, or join key in the target database.
- **Slot-function mismatch**: a selected field is surface-related but does not match the functional role required by the query.
- **Query-structure error**: error in aggregation, grouping, sorting, subquery, CTE, join structure, or overall SQL logic.
- **Condition error**: wrong operator, time window, literal value, threshold, filtering condition, or value list.
- **Execution invalidity**: SQL cannot be executed because of syntax, schema, type, or dialect issues.

Correct predictions may be labeled as `Correct` in instance-level analysis files.

## Results

Public result files are placed under:

```text
results/
```

This directory is intended for cleaned public result tables and aggregate summaries. Internal execution dumps, API logs, and hidden gold SQL should not be committed.

## Security and Leakage Control

Do not commit:

```text
API keys
passwords
private endpoints
local absolute paths
hidden SQA templates
sqa_id / template_id / skeleton_id fields
anchor mappings
slot mappings
test gold SQL
full construction artifacts after SQA generation
large local caches or model files
```

Recommended local-only files include:

```text
evaluation/configs/.env
evaluation/submission/outputs/
preprocess/outputs_hidden/
```

The public repository should contain only sanitized examples and release-safe data.

## Citation

Citation information will be added after paper release.

```bibtex
@misc{semquerybench2026,
  title  = {SemQueryBench: A Benchmark for Cross-Database Text-to-SQL Generalization under Controlled Schema-Property Similarity},
  author = {Anonymous},
  year   = {2026}
}
```

## License

License information will be added before the final public release.
