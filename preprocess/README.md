# SemQueryBench Preprocessing and Benchmark Construction

This directory contains the benchmark construction pipeline for **SemQueryBench**.

The pipeline starts from database metadata, assigns semantic table/column tags, computes schema-property similarity, builds difficulty tiers, generates database fingerprints, constructs Anchor Matrices, generates Semantic Query Abstractions (SQAs), and finally instantiates SQAs into concrete SQL queries and natural language questions.

## Directory Structure

```text
preprocess/
├── configs/
│   ├── db_tag_schema.json
│   └── anchor_matrix_template.json
├── prompts/
│   ├── db_tagging_prompt.md
│   ├── db_tagging_prompt_compact.md
│   ├── anchor_matrix_prompt.md
│   ├── sqa_generation_prompt.md
│   └── sql_instantiation_prompt.md
├── semquery_preprocess/
│   ├── llm_client.py
│   ├── db_tagger.py
│   ├── similarity.py
│   ├── clustering.py
│   ├── fingerprint.py
│   ├── anchor_matrix.py
│   ├── sqa_generator.py
│   └── sql_instantiator.py
├── scripts/
│   ├── build_db_tags.py
│   ├── compute_db_similarity.py
│   ├── build_difficulty_tiers.py
│   ├── build_fingerprints.py
│   ├── build_sqa.py
│   └── instantiate_sql.py
└── outputs/
    ├── db_tags/
    ├── similarity/
    ├── clustering/
    ├── fingerprints/
    ├── anchor_matrices/
    ├── sqa/
    └── sql/
```

## Input Data

The construction pipeline expects database metadata under:

```text
dataset/{tier}/all_meta/{db_id}.json
```

For example:

```text
dataset/easy/all_meta/USA_NAMES.json
dataset/mid/all_meta/ELECTRONIC_SALES.json
dataset/hard/all_meta/Refinery.json
```

Each metadata file should contain table-level and column-level information. The expected table format is:

```json
{
  "TABLE_NAME": {
    "table_tag": "TRANSACTION",
    "colname_list": [
      {
        "col_name": "COLUMN_NAME",
        "col_tag": "TIME_EVENT",
        "col_type": "TIMESTAMP",
        "sample_value": "2024-01-01"
      }
    ]
  }
}
```

The code also supports a schema-level wrapper such as:

```json
{
  "main": {
    "TABLE_NAME": {
      "table_tag": "TRANSACTION",
      "colname_list": []
    }
  }
}
```

## Environment Variables

The LLM-related scripts use an OpenAI-compatible API interface.

Set the API key and base URL before running the pipeline:

```powershell
$env:OPENAI_API_KEY="your_api_key"
$env:OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
```


## Pipeline Overview

The full construction pipeline contains six stages:

```text
1. Database semantic tagging
2. Database similarity computation
3. Difficulty-tier construction
4. Database fingerprint construction
5. Anchor Matrix and SQA generation
6. SQL and question instantiation
```

The outputs of each stage are used as inputs to the next stage.

---

# 1. Database Semantic Tagging

This stage assigns semantic table tags and column tags to each database.

## Input

```text
dataset/{tier}/all_meta/{db_id}.json
preprocess/prompts/db_tagging_prompt.md
preprocess/prompts/db_tagging_prompt_compact.md
```

## Output

```text
preprocess/outputs/db_tags/{db_id}.json
```

## Command

```powershell
python preprocess/scripts/build_db_tags.py `
  --dataset_dir dataset `
  --output_dir preprocess/outputs/db_tags `
  --detailed_prompt preprocess/prompts/db_tagging_prompt.md `
  --compact_prompt preprocess/prompts/db_tagging_prompt_compact.md `
  --model qwen-plus `
  --request_interval 2 `
  --log_file preprocess/outputs/build_db_tags.log
```

To process one database only:

```powershell
python preprocess/scripts/build_db_tags.py `
  --dataset_dir dataset `
  --output_dir preprocess/outputs/db_tags `
  --detailed_prompt preprocess/prompts/db_tagging_prompt.md `
  --compact_prompt preprocess/prompts/db_tagging_prompt_compact.md `
  --model qwen-plus `
  --db_id USA_NAMES `
  --request_interval 2
```

## Output Format

```json
{
  "main": {
    "TABLE_NAME": {
      "table_tag": "TRANSACTION",
      "colname_list": [
        {
          "col_name": "COLUMN_NAME",
          "col_tag": "TIME_EVENT",
          "col_type": "TIMESTAMP",
          "sample_value": "2024-01-01"
        }
      ]
    }
  }
}
```

---

# 2. Database Similarity Computation

This stage computes pairwise schema-property similarity between tagged databases.

The similarity score combines three components:

```text
1. Table-type composition similarity
2. Per-table property-signature similarity
3. Property co-occurrence similarity
```

Default weights:

```text
table type composition:       0.35
property signature:           0.40
property co-occurrence:       0.25
```

## Input

```text
preprocess/outputs/db_tags/*.json
preprocess/configs/db_tag_schema.json
```

## Output

```text
preprocess/outputs/similarity/db_similarity_pairs.csv
preprocess/outputs/similarity/db_similarity_matrix.csv
```

## Command

```powershell
python preprocess/scripts/compute_db_similarity.py `
  --db_tags_dir preprocess/outputs/db_tags `
  --tag_schema preprocess/configs/db_tag_schema.json `
  --output_dir preprocess/outputs/similarity `
  --log_file preprocess/outputs/similarity/compute_db_similarity.log
```

## Pairwise Output Columns

```text
db1
db2
schema_property_similarity
sim_table_types
sim_property_signature
sim_cooccurrence
lexical_similarity
```

---

# 3. Difficulty-Tier Construction

This stage constructs easy, mid, and hard database tiers.

It converts similarity to distance:

```text
distance(D_i, D_j) = 1 - similarity(D_i, D_j)
```

Then it applies average-linkage hierarchical clustering and distribution-aware pruning.

The pruning objective is:

```text
L(C) = |AvgDist(C) - target_distance| + alpha * StdDist(C)
```

Default target distances:

```text
easy: 0.10
mid:  0.20
hard: 0.30
```

Default tier sizes:

```text
easy: 20
mid:  21
hard: 21
```

## Input

```text
preprocess/outputs/similarity/db_similarity_pairs.csv
```

## Output

```text
preprocess/outputs/clustering/difficulty_tiers.csv
preprocess/outputs/clustering/difficulty_metrics.csv
preprocess/outputs/clustering/selected_distance_matrix.csv
```

## Command

```powershell
python preprocess/scripts/build_difficulty_tiers.py `
  --similarity_pairs preprocess/outputs/similarity/db_similarity_pairs.csv `
  --output_dir preprocess/outputs/clustering `
  --easy_size 20 `
  --mid_size 21 `
  --hard_size 21 `
  --easy_target_dist 0.10 `
  --mid_target_dist 0.20 `
  --hard_target_dist 0.30 `
  --alpha 1.5 `
  --log_file preprocess/outputs/clustering/build_difficulty_tiers.log
```

For a small smoke test with three databases:

```powershell
python preprocess/scripts/build_difficulty_tiers.py `
  --similarity_pairs preprocess/outputs/similarity/db_similarity_pairs.csv `
  --output_dir preprocess/outputs/clustering `
  --easy_size 1 `
  --mid_size 1 `
  --hard_size 1 `
  --easy_target_dist 0.10 `
  --mid_target_dist 0.20 `
  --hard_target_dist 0.30 `
  --alpha 1.5
```

Smoke-test tier metrics are not meaningful when each tier contains only one database.

## `difficulty_tiers.csv`

Expected format:

```csv
db_id,difficulty,target_distance
USA_NAMES,easy,0.1
ELECTRONIC_SALES,mid,0.2
Refinery,hard,0.3
```

This file is the source of truth for downstream fingerprint and SQL instantiation stages.

---

# 4. Database Fingerprint Construction

This stage converts tagged database metadata into compact database fingerprints.

A fingerprint groups candidate columns by:

```text
table_tag -> col_tag -> candidate columns
```

## Input

```text
preprocess/outputs/db_tags/{db_id}.json
preprocess/outputs/clustering/difficulty_tiers.csv
```

## Output

```text
preprocess/outputs/fingerprints/{tier}/{db_id}.json
preprocess/outputs/fingerprints/fingerprint_summary.csv
```

## Command

```powershell
python preprocess/scripts/build_fingerprints.py `
  --db_tags_dir preprocess/outputs/db_tags `
  --difficulty_tiers preprocess/outputs/clustering/difficulty_tiers.csv `
  --output_dir preprocess/outputs/fingerprints `
  --log_file preprocess/outputs/fingerprints/build_fingerprints.log
```

## Output Format

```json
{
  "TRANSACTION": {
    "TIME_EVENT": [
      {
        "path": "main.TABLE_NAME.EVENT_TIME",
        "type": "TIMESTAMP",
        "sample": "2024-01-01"
      }
    ],
    "VAL_AMOUNT": [
      {
        "path": "main.TABLE_NAME.AMOUNT",
        "type": "NUMBER",
        "sample": 123.45
      }
    ]
  }
}
```

---

# 5. Anchor Matrix and SQA Generation

This stage first generates a tier-level Anchor Matrix from database fingerprints, then generates SQL-like Semantic Query Abstractions.

## 5.1 Anchor Matrix

The Anchor Matrix is a compact, selected set of representative table/column tag anchors for each database in a tier.

The generic template is stored in:

```text
preprocess/configs/anchor_matrix_template.json
```

The template contains only the slot structure:

```json
{
  "REFERENCE": {
    "TIME_EVENT": [],
    "ID_MAIN": [],
    "NAME_ENTITY": []
  },
  "MASTER": {
    "ID_MAIN": [],
    "NAME_ENTITY": []
  }
}
```

The script automatically expands this template to:

```text
db_file -> table_tag -> col_tag -> selected column paths
```

Example:

```json
{
  "USA_NAMES.json": {
    "REFERENCE": {
      "TIME_EVENT": [],
      "ID_MAIN": [],
      "NAME_ENTITY": [
        "main.NAMES.name"
      ]
    }
  }
}
```

## 5.2 SQA

An SQA is a SQL-like semantic abstraction. It preserves query structure while replacing concrete database elements with semantic slots.

Example:

```sql
SELECT <NAME_ENTITY>
FROM <REFERENCE>
ORDER BY <VAL_AMOUNT> DESC
LIMIT :top_k;
```

## Input

```text
preprocess/outputs/fingerprints/{tier}/*.json
preprocess/configs/anchor_matrix_template.json
preprocess/prompts/anchor_matrix_prompt.md
preprocess/prompts/sqa_generation_prompt.md
```

## Output

```text
preprocess/outputs/anchor_matrices/{tier}_anchor_matrix.json
preprocess/outputs/sqa/{tier}_sqa.json
```

## Command

```powershell
python preprocess/scripts/build_sqa.py `
  --fingerprints_dir preprocess/outputs/fingerprints `
  --anchor_template preprocess/configs/anchor_matrix_template.json `
  --anchor_prompt preprocess/prompts/anchor_matrix_prompt.md `
  --sqa_prompt preprocess/prompts/sqa_generation_prompt.md `
  --output_anchor_dir preprocess/outputs/anchor_matrices `
  --output_sqa_dir preprocess/outputs/sqa `
  --model qwen-plus `
  --tiers easy mid hard `
  --num_sqa 20 `
  --log_file preprocess/outputs/sqa/build_sqa.log
```

To process only the easy tier:

```powershell
python preprocess/scripts/build_sqa.py `
  --fingerprints_dir preprocess/outputs/fingerprints `
  --anchor_template preprocess/configs/anchor_matrix_template.json `
  --anchor_prompt preprocess/prompts/anchor_matrix_prompt.md `
  --sqa_prompt preprocess/prompts/sqa_generation_prompt.md `
  --output_anchor_dir preprocess/outputs/anchor_matrices `
  --output_sqa_dir preprocess/outputs/sqa `
  --model qwen-plus `
  --tiers easy `
  --num_sqa 5 `
  --log_file preprocess/outputs/sqa/build_sqa_easy.log
```

If the Anchor Matrix has already been generated and only SQA generation should be rerun:

```powershell
python preprocess/scripts/build_sqa.py `
  --fingerprints_dir preprocess/outputs/fingerprints `
  --anchor_template preprocess/configs/anchor_matrix_template.json `
  --anchor_prompt preprocess/prompts/anchor_matrix_prompt.md `
  --sqa_prompt preprocess/prompts/sqa_generation_prompt.md `
  --output_anchor_dir preprocess/outputs/anchor_matrices `
  --output_sqa_dir preprocess/outputs/sqa `
  --model qwen-plus `
  --tiers easy `
  --num_sqa 5 `
  --skip_anchor
```

## SQA Output Format

```json
{
  "tier": "easy",
  "sqa_templates": [
    {
      "sqa_id": "easy_sqa_001",
      "sqa": "SELECT <NAME_ENTITY> FROM <REFERENCE> ORDER BY <VAL_AMOUNT> DESC LIMIT :top_k;",
      "intent": "Find the top entities ranked by a measurable value.",
      "difficulty_hint": "simple",
      "required_slots": {
        "table_tags": ["REFERENCE"],
        "column_tags": ["NAME_ENTITY", "VAL_AMOUNT"]
      }
    }
  ]
}
```

---

# 6. SQL and Question Instantiation

This stage instantiates tier-level SQAs on concrete databases.

For each database, the script sends:

```text
SQA templates + database metadata
```

to the LLM and obtains:

```text
concrete SQL + natural language question
```

The natural language question is generated in this stage because it depends on the concrete database domain.

## Input

```text
preprocess/outputs/sqa/{tier}_sqa.json
dataset/{tier}/all_meta/{db_id}.json
preprocess/outputs/clustering/difficulty_tiers.csv
preprocess/prompts/sql_instantiation_prompt.md
```

## Output

```text
preprocess/outputs/sql/{tier}/{db_id}.json
```

## Command

```powershell
python preprocess/scripts/instantiate_sql.py `
  --tier easy `
  --difficulty_tiers preprocess/outputs/clustering/difficulty_tiers.csv `
  --sqa_file preprocess/outputs/sqa/easy_sqa.json `
  --meta_dir dataset/easy/all_meta `
  --prompt preprocess/prompts/sql_instantiation_prompt.md `
  --output_dir preprocess/outputs/sql/easy `
  --model qwen-plus `
  --log_file preprocess/outputs/sql/easy/instantiate_sql_easy.log
```

To process only the first two databases in the selected tier:

```powershell
python preprocess/scripts/instantiate_sql.py `
  --tier easy `
  --difficulty_tiers preprocess/outputs/clustering/difficulty_tiers.csv `
  --sqa_file preprocess/outputs/sqa/easy_sqa.json `
  --meta_dir dataset/easy/all_meta `
  --prompt preprocess/prompts/sql_instantiation_prompt.md `
  --output_dir preprocess/outputs/sql/easy `
  --model qwen-plus `
  --limit 2 `
  --log_file preprocess/outputs/sql/easy/instantiate_sql_easy.log
```

To process selected databases:

```powershell
python preprocess/scripts/instantiate_sql.py `
  --tier easy `
  --difficulty_tiers preprocess/outputs/clustering/difficulty_tiers.csv `
  --sqa_file preprocess/outputs/sqa/easy_sqa.json `
  --meta_dir dataset/easy/all_meta `
  --prompt preprocess/prompts/sql_instantiation_prompt.md `
  --output_dir preprocess/outputs/sql/easy `
  --model qwen-plus `
  --db_ids USA_NAMES USDA_NASS_AGRICULTURE `
  --log_file preprocess/outputs/sql/easy/instantiate_sql_easy.log
```

The selected `db_ids` must belong to the specified tier in `difficulty_tiers.csv`.

## Output Format

```json
{
  "db_id": "USA_NAMES",
  "tier": "easy",
  "status": "ok",
  "instances": [
    {
      "sqa_id": "easy_sqa_001",
      "status": "instantiated",
      "event_scope": "FROM main.NAMES n",
      "tag_mapping": {
        "NAME_ENTITY": "n.name",
        "VAL_AMOUNT": "n.count"
      },
      "sql": "SELECT n.name\nFROM main.NAMES n\nORDER BY n.count DESC\nLIMIT :top_k;",
      "question": "Which names appear most frequently in the records?",
      "notes": "Uses count as the ranking measure."
    },
    {
      "sqa_id": "easy_sqa_002",
      "status": "skip",
      "event_scope": null,
      "tag_mapping": null,
      "sql": null,
      "question": null,
      "notes": "Cannot instantiate because the database does not contain a suitable TIME_EVENT column."
    }
  ]
}
```

If no SQA can be instantiated for a database, the file is still written with `status` set to `no_instantiable_sqa`.

---

# Reproducible End-to-End Example

The following commands run the construction pipeline from tagged metadata to SQL instantiation.

```powershell
python preprocess/scripts/compute_db_similarity.py `
  --db_tags_dir preprocess/outputs/db_tags `
  --tag_schema preprocess/configs/db_tag_schema.json `
  --output_dir preprocess/outputs/similarity `
  --log_file preprocess/outputs/similarity/compute_db_similarity.log
```

```powershell
python preprocess/scripts/build_difficulty_tiers.py `
  --similarity_pairs preprocess/outputs/similarity/db_similarity_pairs.csv `
  --output_dir preprocess/outputs/clustering `
  --easy_size 20 `
  --mid_size 21 `
  --hard_size 21 `
  --easy_target_dist 0.10 `
  --mid_target_dist 0.20 `
  --hard_target_dist 0.30 `
  --alpha 1.5 `
  --log_file preprocess/outputs/clustering/build_difficulty_tiers.log
```

```powershell
python preprocess/scripts/build_fingerprints.py `
  --db_tags_dir preprocess/outputs/db_tags `
  --difficulty_tiers preprocess/outputs/clustering/difficulty_tiers.csv `
  --output_dir preprocess/outputs/fingerprints `
  --log_file preprocess/outputs/fingerprints/build_fingerprints.log
```

```powershell
python preprocess/scripts/build_sqa.py `
  --fingerprints_dir preprocess/outputs/fingerprints `
  --anchor_template preprocess/configs/anchor_matrix_template.json `
  --anchor_prompt preprocess/prompts/anchor_matrix_prompt.md `
  --sqa_prompt preprocess/prompts/sqa_generation_prompt.md `
  --output_anchor_dir preprocess/outputs/anchor_matrices `
  --output_sqa_dir preprocess/outputs/sqa `
  --model qwen-plus `
  --tiers easy mid hard `
  --num_sqa 20 `
  --log_file preprocess/outputs/sqa/build_sqa.log
```

```powershell
python preprocess/scripts/instantiate_sql.py `
  --tier easy `
  --difficulty_tiers preprocess/outputs/clustering/difficulty_tiers.csv `
  --sqa_file preprocess/outputs/sqa/easy_sqa.json `
  --meta_dir dataset/easy/all_meta `
  --prompt preprocess/prompts/sql_instantiation_prompt.md `
  --output_dir preprocess/outputs/sql/easy `
  --model qwen-plus `
  --log_file preprocess/outputs/sql/easy/instantiate_sql_easy.log
```

Repeat the last command for `mid` and `hard` by changing the tier, SQA file, metadata directory, and output directory:

```powershell
--tier mid
--sqa_file preprocess/outputs/sqa/mid_sqa.json
--meta_dir dataset/mid/all_meta
--output_dir preprocess/outputs/sql/mid
```

```powershell
--tier hard
--sqa_file preprocess/outputs/sqa/hard_sqa.json
--meta_dir dataset/hard/all_meta
--output_dir preprocess/outputs/sql/hard
```

---

# Notes

## `database/` vs `dataset/`

The `database/` directory is used for releasing and loading the full benchmark databases.

The construction pipeline in this directory uses:

```text
dataset/{tier}/all_meta/
```

as the metadata source.

## `outputs/`

The `preprocess/outputs/` directory stores intermediate construction results. In the released sample version, these outputs may be included to demonstrate the full pipeline.

For a full-scale run, outputs can be regenerated from the scripts.

## Tier Names

The code uses:

```text
easy
mid
hard
```

The paper may refer to `mid` as `medium`.

## SQA vs SQL Skeleton

The construction pipeline uses **SQA** as the main abstraction.

SQA is not a SQL skeleton in the traditional sense. It is a SQL-like semantic query abstraction that preserves query intent and structure while replacing concrete database elements with semantic table and column slots.
