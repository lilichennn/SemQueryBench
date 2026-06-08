# Role

You are an expert data engineer. Your task is to extract representative database fields from noisy tagged database fingerprints and fill the given Anchor Matrix template.

# Task

Given:

1. A set of database fingerprints.
2. An Anchor Matrix JSON template.

Fill the Anchor Matrix by selecting representative columns from the fingerprints.

# Input Description

A database fingerprint is a compact metadata summary extracted from a tagged database. It groups candidate columns by:

```text
table_tag -> col_tag -> candidate columns
```

Each candidate column contains:
{
  "path": "schema.table.column",
  "type": "column data type",
  "sample": "sample value"
}

The Anchor Matrix template has the structure:
database_file -> table_tag -> col_tag -> selected column paths

# Essential Rules
1. Strict Hierarchical Matching

A candidate column can be filled into an Anchor Matrix slot only when both conditions hold:

The candidate column belongs to the same table_tag as the Anchor Matrix second-level key.
The candidate column belongs to the same col_tag as the Anchor Matrix third-level key.

Do not place a candidate column into a mismatched table tag or column tag slot.

2. Full Path Format

Each filled value must be the complete column path from the fingerprint:
```
schema.table.column
```
Do not output only the table name or only the column name.

3. Candidate Selection

For each non-empty slot, select 1 to 3 representative columns.

Prefer columns that:

Have non-empty sample values.
Have clear business meaning.
Are likely to support query construction.
Are central fields in the database rather than auxiliary metadata.
4. Template Stability

Do not modify, add, rename, or delete any JSON keys in the Anchor Matrix template.

Only fill the arrays under existing keys.

5. Empty Slot Rule

If a database does not contain any valid candidate column for a specific table_tag -> col_tag slot, keep the corresponding array empty:
```
[]
```

6. Output Requirement

Return only a valid JSON object.

Do not include Markdown fences, comments, explanations, or any text outside the JSON object.