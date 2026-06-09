You are evaluating whether a predicted SQL query is execution-equivalent to the gold SQL query.

Use the user question, gold SQL, gold execution result, predicted SQL, and predicted execution result.

Return only JSON:
{
  "Execute Match": 0 or 1,
  "Execute diff desc": "brief reason"
}
