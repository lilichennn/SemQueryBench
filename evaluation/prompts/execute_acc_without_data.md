You are evaluating whether a predicted SQL query is execution-equivalent to the gold SQL query.

The gold execution result is empty or unavailable. Judge based on SQL semantics and the user question.

Return only JSON:
{
  "Execute Acc": 0 or 1,
  "Execute diff desc": "brief reason"
}
