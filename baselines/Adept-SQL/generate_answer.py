from call_llm import callLLM
from op_DB import backend_db_op
from utils import *
def get_prompts():
    
    prompt = '''
    #Role#
    Now, you are a task assistant. You are skilled at helping your users organize the task process. Your tone is objective and instructive.

    #Task#
    Your backend system program has completed a Text2SQL task. The program performed the following steps: user question processing -> matching the processed question with pre-stored complex SQL -> if matched, the large model is asked to write a new SQL by imitating the pre-stored SQL; if not matched, the large model generates SQL autonomously -> the SQL is sent to the user-specified database for execution and data retrieval.

    #Requirements#
    1. Provide an appropriate explanation of the SQL statement structure.
    2. Keep the word count within 200 words.
    '''

    return prompt
def generate_answer(prams,modelname):

    prompt = get_prompts()

    prompt += '\n\n# Results of Each Step #\n'
    prompt += '\n\nUser Question:\n' + prams['user_input']
    prompt += '\n\nPre-stored SQL Search:\n' + prams['qtype_search_res']
    prompt += '\n\nGenerated SQL:\n' + prams['sql']
    prompt += '\n\nSQL Execution Result:\n' + prams['sql_exe_info']

    prompt += '\n\n# Commencing Summary #\n'


    print_blue(prompt)

    res = callLLM(modelname).init_prompt('You are a assistant。',prompt).call().get_response_content()
    print_green(res)
    
    return res




if __name__ == "__main__":
    params = {
    'assistant_id': '9',

    'user_input': 'What is the planned recovery rate of atmospheric non-condensable gas in February 2024 for Atmospheric Distillation Unit I?',

    'qtype_search': 'The most similar question is: [0.4468703269958496] A certain indicator for a certain month within a certain assessment scope\nNo similar issue found in the pre-stored complex SQL list. SQL will be generated autonomously.',

    'sql': '''SELECT
    p.unit_name,
    r.daily_amount,
    r.plan_total_amount,
    r.daily_amount / r.plan_total_amount * 100 AS plan_recovery_rate
FROM
    rpt_t_daily_refinery_unit r
JOIN
    pm_unit_t p ON r.node_code = p.unit_code
WHERE
    p.unit_alias = 'Atmospheric Distillation Unit I'
    AND r.mtrl_alias_show = 'atmospheric non-condensable gas'
    AND YEAR(r.r_date) = 2024
    AND MONTH(r.r_date) = 2;''',

    'sql_exe_info': 'SQL executed successfully! 29 row(s) returned.'
}
    answer = generate_answer(params)
    print(answer)