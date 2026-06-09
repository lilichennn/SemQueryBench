You are classifying Text-to-SQL prediction errors.

Given a user question, gold SQL, predicted SQL, Execute Match, Effective Match, and a natural-language SQL difference description, classify the main error type.

Choose all applicable labels from the following five categories:

1. Schema grounding error
The prediction fails to ground the learned query intent to the correct schema elements in the target database, including wrong tables, columns, or join keys.

2. Slot-function mismatch
The selected field looks related on the surface, but its functional role does not match the required query intent. For example, using a birth time field when an event time field is needed, or using a display name field when an entity identifier is needed.

3. General generation error
The prediction is wrong for reasons not directly attributable to schema transfer or SQA-pattern transfer, such as producing an overly generic query, omitting the main task intent, returning an irrelevant answer, or making a broad reasoning mistake not tied to schema grounding, SQL structure, or condition instantiation.

4. Condition error
The prediction fails to instantiate required constraints from the learned query pattern, including comparison operators, time windows, literals, thresholds, NULL filters, value lists, or other database-specific filtering rules.

5. Execution invalidity
The predicted SQL cannot be executed due to syntax errors, schema errors, type errors, dialect errors, or invalid SQL generation.

6. If the prediction is correct, use:
Correct
## Important rule:
If Execute Match is 0 or Effective Match is 0, you must not return "Correct".
Only return "Correct" when both Execute Match and Effective Match are 1.

Return only valid JSON:

{
  "Primary Diff Type": "Condition error",
  "Diff Type": ["Condition error", "General generation error"]
}