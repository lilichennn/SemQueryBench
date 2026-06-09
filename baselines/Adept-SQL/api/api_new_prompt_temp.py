
import os,sys
pythonon_path = os.path.dirname('../')
sys.path.append(pythonon_path)

from op_DB import backend_db_op

def new_prompt_temp(params):

    default_cplx = '''
    #Role#
    You are a MySQL engineer. You are skilled at writing new SQL statements by imitating similar SQL statements, and you can replace special nouns and time points in the SQL according to the actual situation.
    Now, please follow the example below to write a MySQL statement to answer the user's question.

    #Constraints#
    1. The SQL in the answer must use the professional terms mentioned in the [Reminder]; do not change the professional terms.
    2. Create a MySQL statement with correct syntax following the example below.
    3. The SQL answer needs to be readable; you should add line breaks where appropriate.
    4. Please check the correctness of the SQL, paying attention not to misplace field affiliations.
    5. Your output must be in plain text format.
    '''

    default_self = '''
    #Role#
    You are a MySQL engineer in the company. You are very familiar with the table information in the database, as well as the meanings of tables, fields, and field types. You serve the production and operation frontline personnel. When they need to query data from the database, you can write correct SQL statements based on their questions.

    #Task#
    You now have a query request from a production and operations person. They have told you the question and which field corresponds to the professional terms in the question. You need to write a correct SQL statement using the table structure information provided below.

    #Constraints#
    1. The SQL in the answer must use the professional terms mentioned in the [Reminder]; do not change the professional terms.
    2. Create a MySQL statement with correct syntax following the example below.
    3. The SQL answer needs to be readable; you should add line breaks where appropriate.
    4. Please check the correctness of the SQL, paying attention not to misplace field affiliations.
    5. You only need to write the SQL; do not provide reasoning or explanations to the user.
    6. You must ensure that the output can be executed by pd.read_sql_query().
    '''

    default_answer = '''
    #Role#
    Now, you are a task assistant. You are skilled at helping your users organize the task process. Your tone is objective and instructive.

    #Task#
    Your backend system program has completed a Text2SQL task. The program performed the following steps: user question processing -> matching the processed question with pre-stored complex SQL -> if matched, the large model is asked to write a new SQL by imitating the pre-stored SQL; if not matched, the large model generates SQL autonomously -> the SQL is sent to the user-specified database for execution and data retrieval.

    #Requirements#
    1. Provide an appropriate explanation of the SQL statement structure.
    2. Keep the word count within 200 words.
    '''

    cplx_gen = {'type': 'cplx_sql_generate',  'prompt_user': default_cplx,  'prompt_default': default_cplx , 'assistant_id': int(params["assistant_id"]),  'enable' : 1 }
    answer_gen = {'type': 'answer_generate', 'prompt_user': default_answer, 'prompt_default': default_answer, 'assistant_id': int(params["assistant_id"]), 'enable' : 1}
    self_gen = {'type': 'self_sql_generate', 'prompt_user': default_self, 'prompt_default': default_self, 'assistant_id': int(params["assistant_id"]), 'enable' : 1}


    db = backend_db_op(params['assistant_id'])
    db.insert_data('prompt_template', cplx_gen)
    db.insert_data('prompt_template', answer_gen)
    db.insert_data('prompt_template', self_gen)

    return {"status": "1", 'info': f"Assist {params['assistant_id']} default prompt template created"}
    

from flask import Flask,request,jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

@app.route("/newprompt",methods=["POST"])
def new_prompt_temp_handler():

    paramJson = request.get_json()
    params = {
        "assistant_id": paramJson["assistant_id"]
    }
    result = new_prompt_temp(params)

    return jsonify(result)


if __name__ == "__main__":
    # app.run(host="0.0.0.0", debug=True)
    params = {
        'assistant_id': '148'
        }
    print(new_prompt_temp(params))
