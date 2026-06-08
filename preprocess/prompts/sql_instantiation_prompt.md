# Role

You are an expert data engineer and Text-to-SQL benchmark annotator.

# Task

You will be given:

1. A set of SQL-like Semantic Query Abstractions (SQAs).
2. The metadata of one database.

Each SQA contains semantic slots such as table tags and column tags. These tags describe the semantic role of a table or column, for example whether a column is an amount value, a count value, an event time, an external identifier, or a long description.

Your task is to instantiate each SQA on the given database when it is reasonable to do so.

For each SQA, produce:

1. A concrete SQL query over the given database.
2. A natural language question that matches the domain language of the database.
3. A mapping from SQA semantic slots to concrete database columns.
4. Notes explaining important assumptions, type casts, event scope, or why the SQA cannot be instantiated.

# Database Metadata

The database metadata contains tables and columns.

Each table includes:

```json
{
  "table_name": "TABLE_NAME",
  "table_tag": "TRANSACTION",
  "columns": [
    {
      "col_name": "COLUMN_NAME",
      "col_tag": "TIME_EVENT",
      "col_type": "TIMESTAMP",
      "sample_value": "2024-01-01"
    }
  ]
}
```

# Instantiation Rules
Do not force instantiation. Instantiate an SQA only when the database has semantically appropriate tables and columns.
Match semantic slots primarily by table_tag and col_tag.
Also use column names, data types, sample values, and table meaning to decide whether a mapping is reasonable.
Do not map a semantic slot to an unrelated column only because the tag matches.
Prefer simple, readable SQL.
Use table aliases when helpful.
Preserve the query structure of the SQA as much as possible.
Use SQL placeholders for unknown values, such as :keyword, :start_date, :end_date, :category_value, :status_value, :threshold, :top_k, or :k.
If a text search is needed over non-text or semi-structured fields, cast explicitly when appropriate.
If a timestamp or numeric field has special units, mention it in notes.
If the SQA cannot be reasonably instantiated, return "status": "skip" for that SQA.
Generate a natural language question in the domain style of the database. Do not merely translate the SQL logic mechanically.
The question should be concise and realistic.
If no SQA can be instantiated for the database, still return valid JSON with all SQA records marked as "skip".

# Output Format

Return only a valid JSON object.

Use this structure:

```json
{
  "db_id": "DATABASE_ID",
  "tier": "easy",
  "status": "ok",
  "instances": [
    {
      "sqa_id": "easy_sqa_001",
      "status": "instantiated",
      "event_scope": "FROM SCHEMA.TABLE t",
      "tag_mapping": {
        "TIME_EVENT": "t.event_time",
        "NAME_ENTITY": "t.entity_name",
        "VAL_AMOUNT": "t.amount"
      },
      "sql": "SELECT t.entity_name\nFROM SCHEMA.TABLE t\nORDER BY t.amount DESC\nLIMIT :top_k;",
      "question": "Which entities have the highest recorded amount in this dataset?",
      "notes": "Uses amount as VAL_AMOUNT and entity_name as NAME_ENTITY."
    },
    {
      "sqa_id": "easy_sqa_002",
      "status": "skip",
      "event_scope": null,
      "tag_mapping": null,
      "sql": null,
      "question": null,
      "notes": "Cannot instantiate because the database has no TIME_EVENT column under a suitable TRANSACTION table."
    }
  ]
}
```

# Output Constraints
Return JSON only.
Do not wrap the JSON in Markdown fences.
Do not include comments.
Each input SQA must have one corresponding output record.
status at the top level must be one of: "ok", "no_instantiable_sqa".
Each instance status must be one of: "instantiated", "skip".
For "instantiated" records, sql, question, tag_mapping, and event_scope must not be null.
For "skip" records, sql, question, tag_mapping, and event_scope must be null.
The SQL must use concrete table and column names from the provided database metadata.
Do not invent tables or columns.