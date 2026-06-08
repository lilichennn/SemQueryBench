# OpenSearch-SQL Reproduction

This directory contains the OpenSearch-SQL reproduction code used in the SemQueryBench experiments.

The code is preserved according to the original OpenSearch-SQL execution workflow. We do not provide a unified SemQueryBench runner for this baseline. The experiment should be run using the method-specific preprocessing script and the original main entry point.

## Directory Layout

A typical local layout is:

```text
opensearch_sql/
├── originalreadme.md
├── run/
│   └── run_preprocess.sh
├── src/
│   └── main.py
├── bird/
└── README.md
```

After preprocessing, the `bird/` directory will be organized in the format described in the original OpenSearch-SQL README.

## Dataset

The SemQueryBench dataset is not included in this baseline directory.

Before running this baseline, prepare the dataset separately and place or convert it into the expected input location used by the preprocessing script. The generated `bird/` directory should follow the layout required by the original OpenSearch-SQL implementation.

Do not commit large dataset files, database files, intermediate caches, or generated outputs into this baseline folder.

## Step 1: Preprocess Data

Run the preprocessing script first:

```bash
./run/run_preprocess.sh
```

This step prepares the data files under:

```text
./bird/
```

After this step, the `bird/` directory should match the structure described in `originalreadme.md`.

## Step 2: Run OpenSearch-SQL

After preprocessing finishes, run the main program:

```bash
python ./src/main.py
```

If your local environment uses a different Python command, use the appropriate executable, for example:

```bash
python3 ./src/main.py
```

## Configuration

Check the configuration used by `./run/run_preprocess.sh` and `./src/main.py` before running the experiment.

In particular, verify:

- dataset path
- database path
- output path
- model name
- API endpoint
- API key or authorization token
- embedding or retrieval-related paths

Sensitive information such as API keys, tokens, passwords, and private endpoints should be provided through environment variables or local configuration files that are not committed to Git.

## Notes

This folder is released for transparency and reproduction. The baseline follows the original OpenSearch-SQL workflow:

```text
preprocess with ./run/run_preprocess.sh
then run ./src/main.py
```

The benchmark dataset itself should be released separately under the main SemQueryBench dataset structure, not duplicated inside this baseline directory.
