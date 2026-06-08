# MCS-SQL reproduction code for SemQueryBench

This folder contains a release-safe cleanup of the MCS-SQL reproduction scripts.

## Files

- `mcs_sql_mysql.py`: MySQL version.
- `mcs_sql_sqlite.py`: SQLite version.
- `evaluate_sql.py`: MySQL execution-based evaluator.
- `.env.example`: Example environment variables.

## Secret handling

No password, API key, private endpoint, or local Windows path is hard-coded in the scripts. Runtime configuration is read from environment variables.

## Minimal environment variables

For MySQL execution:

```bash
export MCS_SQL_MYSQL_HOST=localhost
export MCS_SQL_MYSQL_PORT=3306
export MCS_SQL_MYSQL_USER=root
export MCS_SQL_MYSQL_PASSWORD=your_password
```

For LLM calls:

```bash
export MCS_SQL_LLM_URL=https://your-llm-endpoint/v1/chat/completions
export MCS_SQL_LLM_API_KEY=your_api_key
export MCS_SQL_LLM_MODEL=qwen-max
```

For local paths:

```bash
export MCS_SQL_BASE_DIR=.
export MCS_SQL_DATASET_TYPE=mid
export MCS_SQL_DATASET_PATH=./dataset/mid
export MCS_SQL_EMBEDDING_MODEL_PATH=BAAI/bge-large-en-v1.5
```

PowerShell example:

```powershell
$env:MCS_SQL_MYSQL_PASSWORD = "your_password"
$env:MCS_SQL_LLM_API_KEY = "your_api_key"
$env:MCS_SQL_LLM_URL = "https://your-llm-endpoint/v1/chat/completions"
```

## Notes

The scripts preserve the original reproduction workflow. They are not rewritten into a unified SemQueryBench runner.
