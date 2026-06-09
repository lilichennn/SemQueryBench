You are classifying Text-to-SQL prediction errors.

Given a user question, gold SQL, predicted SQL, Execute Match, Effective Match, and a natural-language SQL difference description, classify the main error type.

Choose exactly one label from the following five categories:

1. Schema grounding
The prediction selects the wrong table, column, or join key in the target database.

2. Slot-function mismatch
The selected field looks related on the surface, but its functional role does not match the required query intent. For example, using a birth time field when an event time field is needed, or using a display name field when an entity identifier is needed.

3. Query-structure error
The prediction has an error in aggregation, grouping, ordering, subquery, CTE, join structure, or overall SQL logic.

4. Condition error
The prediction uses an incorrect comparison operator, time window, literal value, threshold, filtering condition, or value list.

5. Execution invalidity
The predicted SQL cannot be executed due to syntax errors, schema errors, type errors, dialect errors, or invalid SQL generation.

If the prediction is correct, use:
Correct

## Important rule:
If Execute Match is 0 or Effective Match is 0, you must not return "Correct".
Only return "Correct" when both Execute Match and Effective Match are 1.

Return only valid JSON:

{
  "Diff Type": "Schema grounding | Slot-function mismatch | Query-structure error | Condition error | Execution invalidity | Correct"
}