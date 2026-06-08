# Role

You are an expert benchmark designer for Text-to-SQL evaluation.

# Task

Given an Anchor Matrix for one database cluster, generate a set of SQL-like Semantic Query Abstractions (SQAs).

An SQA is not executable SQL. It is a database-agnostic query abstraction that preserves the semantic query structure while replacing concrete table names, column names, and values with semantic slots.

# Input

The input Anchor Matrix has the following structure:

```text
database_file -> table_tag -> col_tag -> selected column paths
```
Each selected column path follows:

```
schema.table.column
```

The Anchor Matrix shows which semantic table/column roles are available across databases in the cluster.

# Definition of SQA

An SQA should preserve:

Query intent.
SQL-like structure.
Required table roles.
Required column roles.
Filtering, aggregation, grouping, ordering, joining, subquery, or CTE structure when applicable.

An SQA should hide:

Concrete database names.
Concrete table names.
Concrete column names.
Concrete literal values.
Domain-specific entity names.

# Slot Format

Use angle-bracket semantic slots.

Examples:

SELECT <NAME_ENTITY>
FROM <REFERENCE>
ORDER BY <VAL_AMOUNT> DESC
LIMIT 5;


WITH active_entities AS (
    SELECT DISTINCT <REL_ENTITY>
    FROM <TRANSACTION>
    WHERE <STATUS_WORK> = :status_value
)
SELECT COUNT(*) AS entity_count
FROM active_entities;

# Generation Rules
Generate SQAs only from semantic slots that are supported by the Anchor Matrix.
Do not use a table tag or column tag if it does not appear with non-empty anchors in the Anchor Matrix.
Prefer SQAs that can be instantiated on multiple databases in the cluster.
Do not generate database-specific SQL.
Do not use concrete table names, column names, database names, or literal values.
Use placeholders for values, such as :start_date, :end_date, :category_value, :status_value, :threshold, or :top_k.
Keep the SQA SQL-like and structurally valid.
Include a mix of simple, medium, and complex query structures when possible.
Avoid overly generic SQAs that do not require meaningful schema grounding.
Avoid SQAs that require slots absent from most databases in the Anchor Matrix.

# Recommended Query Patterns

Generate SQAs covering diverse query structures when the required slots are available:

1. Projection and ordering:
SELECT <NAME_ENTITY>
FROM <REFERENCE>
ORDER BY <VAL_AMOUNT> DESC
LIMIT :top_k;
2. Filtering by category or status:
SELECT <NAME_ENTITY>
FROM <MASTER>
WHERE <CATEGORY_TOPIC> = :category_value;
3. Aggregation:
SELECT COUNT(*) AS record_count
FROM <TRANSACTION>
WHERE <TIME_EVENT> >= :start_date AND <TIME_EVENT> < :end_date;
4. Group-by analysis:
SELECT <CATEGORY_TOPIC>, COUNT(*) AS record_count
FROM <TRANSACTION>
GROUP BY <CATEGORY_TOPIC>
ORDER BY record_count DESC;
5. Value aggregation:
SELECT <CATEGORY_TOPIC>, SUM(<VAL_AMOUNT>) AS total_value
FROM <TRANSACTION>
GROUP BY <CATEGORY_TOPIC>
ORDER BY total_value DESC;
6. Time-window comparison:
SELECT <CATEGORY_TOPIC>, AVG(<VAL_AMOUNT>) AS avg_value
FROM <TRANSACTION>
WHERE <TIME_EVENT> >= :start_date AND <TIME_EVENT> < :end_date
GROUP BY <CATEGORY_TOPIC>;
7. Entity relationship query:
SELECT <REL_ENTITY>, COUNT(*) AS event_count
FROM <TRANSACTION>
GROUP BY <REL_ENTITY>
HAVING COUNT(*) > :threshold;
8. Retention or overlap with CTE:
WITH first_period AS (
    SELECT DISTINCT <REL_ENTITY>
    FROM <TRANSACTION>
    WHERE <TIME_EVENT> >= :start_date_1 AND <TIME_EVENT> < :end_date_1
),
second_period AS (
    SELECT DISTINCT <REL_ENTITY>
    FROM <TRANSACTION>
    WHERE <TIME_EVENT> >= :start_date_2 AND <TIME_EVENT> < :end_date_2
)
SELECT COUNT(*) AS retained_entity_count
FROM first_period
JOIN second_period USING (<REL_ENTITY>);
9. Ranking with aggregation:
SELECT <REL_ENTITY>, SUM(<VAL_AMOUNT>) AS total_value
FROM <TRANSACTION>
GROUP BY <REL_ENTITY>
ORDER BY total_value DESC
LIMIT :top_k;
10. Existence or anti-existence:
SELECT <NAME_ENTITY>
FROM <MASTER>
WHERE <ID_EXTERNAL> NOT IN (
    SELECT <REL_ENTITY>
    FROM <TRANSACTION>
    WHERE <TIME_EVENT> >= :start_date AND <TIME_EVENT> < :end_date
);

# Output Format

Return only a valid JSON object with this structure:
```JSON
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

# Output Constraints
Return JSON only.
Do not wrap the JSON in Markdown fences.
Do not include comments.
Generate sqa_id values using the tier name as prefix, for example easy_sqa_001.
Use difficulty_hint values from: simple, medium, complex.
Each required_slots.table_tags value must be a table tag used in the SQA.
Each required_slots.column_tags value must be a column tag used in the SQA.
Do not duplicate semantically identical SQAs.