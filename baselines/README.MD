# Baselines

This directory contains reproduced baseline code used in the SemQueryBench experiments.

We include method-specific reproduction code and running notes for:

- DAIL-SQL
- OpenSearch-SQL
- MCS-SQL
- AdeptSQL 
- AdeptSQL Variant

The baselines are organized according to their original execution workflows. We do not enforce a unified runner across methods because the reproduced methods use different code structures, dependencies, and input conventions.

The SemQueryBench construction pipeline is provided separately under `preprocess/`. The benchmark dataset is released under `dataset/` and should not be duplicated inside individual baseline directories.

Sensitive information such as API keys, passwords, private endpoints, local absolute paths, caches, logs, and generated outputs should not be committed.