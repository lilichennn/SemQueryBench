# DAIL-SQL Reproduction on SemQueryBench

This directory contains the localized DAIL-SQL reproduction code used in the SemQueryBench experiments.

DAIL-SQL is kept close to its original workflow. We do not provide a unified SemQueryBench runner for this baseline. Instead, this directory preserves the method-specific preprocessing, prompt generation, LLM inference, and evaluation workflow used during reproduction.

## Directory Policy

The `dataset/` directory is not included in this baseline release. Please use the released SemQueryBench dataset and place or convert it into the expected BIRD-style directory structure before running DAIL-SQL.

The `third_party/` directory may be included to preserve method-specific dependencies, patched components, or external resources required by the localized reproduction. Large datasets, generated outputs, logs, API keys, and local cache files should not be committed.

Recommended structure:

```text
baselines/dail_sql/
├── README.md
├── data_preprocess.py
├── generate_question.py
├── ask_llm.py
├── evaluate_sql.py
├── prompt/
├── llm/
├── third_party/
├── vector_cache/
└── outputs/              # optional, ignored by git
```

## Data Requirements

DAIL-SQL requires the benchmark data to be available in SQLite format. This is required by the preprocessing step and by self-consistency voting during LLM inference, where SQL candidates may be executed and compared.

The expected dataset layout follows the BIRD format:

```text
./dataset/bird/
├── train/
│   ├── train.json
│   ├── train_gold.sql
│   ├── train_tables.json
│   └── train_databases/
│       ├── database1/
│       │   └── database1.sqlite
│       └── database2/
│           └── database2.sqlite
├── dev/
│   ├── dev.json
│   ├── dev.sql
│   ├── dev_tables.json
│   └── dev_databases/
│       └── ...
└── database/             # generated or merged database directory
```

The question files should contain at least the following fields:

```text
question
SQL
db_id
```

The table metadata files, such as `train_tables.json` and `dev_tables.json`, should contain complete schema metadata, including tables, columns, column types, primary keys, and foreign keys.

## External Resources

### GloVe Vectors

Place the GloVe 6B zip file under:

```text
vector_cache/
```

When `data_preprocess.py` is executed, `torchtext` will use this cached file automatically.

### Local Embedding Model

The original DAIL-SQL implementation may try to download:

```text
sentence-transformers/all-mpnet-base-v2
```

For local reproduction, replace the selector model path in:

```text
prompt/ExampleSelectorTemplate.py
```

with a local embedding model path, for example:

```python
self.SELECT_MODEL = "/program/models/BAAI/bge-large-en-v1___5"
```

Apply this change consistently to all example selector classes that define `self.SELECT_MODEL`.

## LLM Configuration

Configure the local or API-based LLM endpoint in:

```text
llm/chatgpt.py
```

Do not hard-code API keys or bearer tokens in the repository. Use environment variables or a local configuration file ignored by git.

Recommended environment variables:

```bash
export DAIL_SQL_LLM_URL="http://your-server/v1/chat/completions"
export DAIL_SQL_LLM_API_KEY="your_api_key"
export DAIL_SQL_LLM_MODEL="qwen-72b-instruct"
```

If the local service does not require a real OpenAI key, pass a placeholder value such as `dummy_key` when required by the original command interface.

## Step 1: Data Preprocessing

Run:

```bash
python data_preprocess.py \
  --data_type bird \
  --data_dir ./dataset/bird
```

This step performs the following operations:

1. Merges train and dev databases into `./dataset/bird/database/`.
2. Processes JSON files and adds required fields such as `question_toks`.
3. Generates schema-linking information.
4. Creates preprocessed JSONL files under the dataset `enc/` directory.

Expected generated files include:

```text
./dataset/bird/enc/train_schema-linking.jsonl
./dataset/bird/enc/test_schema-linking.jsonl
```

## Step 2: Prompt Generation

Run:

```bash
python generate_question.py \
  --data_type bird \
  --split test \
  --max_seq_len 4096 \
  --prompt_repr SQL \
  --k_shot 9 \
  --example_type QA \
  --selector_type EUCDISQUESTIONMASK
```

Important parameters:

| Parameter | Description |
|---|---|
| `--data_type bird` | Uses the BIRD-style dataset format. |
| `--split test` | Uses the test split. In this localized setup, `test` corresponds to `dev.json`. |
| `--max_seq_len 4096` | Maximum prompt length. |
| `--prompt_repr SQL` | Uses SQL-style prompt representation. |
| `--k_shot 9` | Uses 9 few-shot examples. |
| `--example_type QA` | Uses question-SQL examples. |
| `--selector_type EUCDISQUESTIONMASK` | Uses the selected example retrieval strategy. |

This step generates a prompt directory under `dataset/process/`, for example:

```text
dataset/process/BIRD-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-200_ANS-4096/
```

## Step 3: LLM Inference

Run:

```bash
python ask_llm.py \
  --question dataset/process/BIRD-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-200_ANS-4096 \
  --openai_api_key dummy_key \
  --model qwen-72b-instruct \
  --n 5 \
  --db_dir ./dataset/bird/database \
  --temperature 1.0
```

Important parameters:

| Parameter | Description |
|---|---|
| `--question` | Prompt directory generated in the previous step. |
| `--openai_api_key` | API key argument retained for compatibility. Use a dummy value if the local service does not require it. |
| `--model` | LLM name used by the local or API service. |
| `--n 5` | Generates 5 SQL candidates for self-consistency voting. |
| `--db_dir` | Directory containing SQLite database files. |
| `--temperature 1.0` | Increases output diversity, which is useful for self-consistency voting. |

The generated SQL file is written under the prompt directory, typically named:

```text
RESULTS_MODEL-qwen-72b-instruct.txt
```

## Step 4: Evaluation

Run:

```bash
python evaluate_sql.py \
  --db_dir ./dataset/bird/database \
  --gold path/to/gold.sql \
  --pred path/to/RESULTS_MODEL-qwen-72b-instruct.txt
```

The evaluation output is saved as:

```text
evaluation_results.txt
```

## Notes and Known Constraints

1. Each database must have a corresponding `.sqlite` file.
2. The JSON field names must match the fields expected by the original DAIL-SQL scripts.
3. Schema-linking files are required by the prompt generation pipeline and should be produced before inference.
4. The `tables.json` files must contain complete schema metadata, including table names, column names, column types, primary keys, and foreign keys.
5. The BIRD-style `evidence` field can be retained and optionally incorporated into the question.
6. The baseline is released as method-specific reproduction code rather than a fully refactored benchmark package.

## Files Excluded from Git

The following files or directories should not be committed:

```gitignore
# Dataset and generated data
dataset/
outputs/
results/
logs/
*.log

# Local secrets
.env
*.env
config.local.json

# Local caches
__pycache__/
*.pyc
.cache/
vector_cache/*.pt
vector_cache/*.pth

# Large model files
*.bin
*.safetensors
*.ckpt
```

If you need to preserve small example outputs for documentation, place them under a dedicated `examples/` directory and ensure they do not contain private data, API keys, or local paths.
