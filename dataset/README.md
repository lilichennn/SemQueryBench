
# SemQueryBench Dataset

This directory contains the public dataset files of SemQueryBench.

## Structure

```text
dataset/
├── easy/
│   ├── train/
│   ├── dev/
│   └── test_public/
├── mid/
│   ├── train/
│   ├── dev/
│   └── test_public/
└── hard/
    ├── train/
    ├── dev/
    └── test_public/
```
## Train and Dev Splits

The train and dev splits include natural language questions, database IDs, and gold SQL queries. These splits are released for method development, prompt construction, and validation.

## Public Test Split

The test_public/ split includes test questions, database IDs, schema metadata, and database descriptions. Gold SQL queries are not released publicly.

The following files are intentionally not included in test_public/:

- test.sql
- gold SQL fields in test.json
- SQA IDs or full SQA mappings
- nearest training database 
- annotations
- database similarity labels
hidden error labels
- Database Metadata

Each split contains schema metadata files such as: