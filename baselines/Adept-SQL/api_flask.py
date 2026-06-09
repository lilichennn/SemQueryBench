from api import sql_modify
from api import sql_upload
from api import sql_list
from api import term_update
from api import startchat
from api import term_delete
from api import sql_delete
from api import sql_list
from api import new_collection
from api import new_prompt_temp

from flask import Flask,request,jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

#-----------------------new assistant----------------------------

@app.route("/newcolle",methods=["POST"])
def new_collection_handler():

    paramJson = request.get_json()
    params = {
        "assistant_id": paramJson["assistant_id"]
    }

    result = new_collection(params)
    result = new_prompt_temp(params)

    return jsonify(result)


@app.route("/newprompt",methods=["POST"])
def new_prompt_temp_handler():

    paramJson = request.get_json()
    params = {
        "assistant_id": paramJson["assistant_id"]
    }
    result = new_prompt_temp(params)

    return jsonify(result)


#--------------------------term----------------------------

@app.route('/termupdate',methods=['POST'])
def term_update_handler():

    paramJson = request.get_json()
    params = {
        'db_id': paramJson['db_id'],
        'table_id': paramJson['table_id'],
        'term_field': paramJson['term_field'],
        'term_list': paramJson['term_list'],
        'assistant_id': paramJson['assistant_id']
    }

    result = term_update(params)

    return jsonify(result)

@app.route('/termdelete',methods=['POST'])
def term_delete_handler():

    paramJson = request.get_json()
    params = {
        'term': paramJson['term'],
        'assistant_id': paramJson['assistant_id']
    }

    result = term_delete(params)

    return jsonify(result)

#----------------------------sSQL CRUD Operations-----------------------------


@app.route('/sqlupload',methods=['POST'])
def sql_upload_handler():

    paramJson = request.get_json()
    params = {
        'qtype': paramJson['qtype'],
        'question1': paramJson['question1'],
        'sql1': paramJson['sql1'],
        'question2': paramJson['question2'],
        'sql2': paramJson['sql2'],
        'assistant_id': paramJson['assistant_id']
    }

    result = sql_upload(params)

    return jsonify(result)


@app.route('/sqlmodify',methods=['POST'])
def sql_modify_handler():

    paramJson = request.get_json()
    params = {
        'qtype': paramJson['qtype'],
        'question1': paramJson['question1'],
        'sql1': paramJson['sql1'],
        'question2': paramJson['question2'],
        'sql2': paramJson['sql2'],
        'assistant_id': paramJson['assistant_id']
    }

    result = sql_modify(params)

    return jsonify(result)

@app.route('/sqllist',methods=['POST'])
def sql_list_handler():

    paramJson = request.get_json()
    params = {
        'qtype': paramJson['qtype'],
        'assistant_id': paramJson['assistant_id'],
        'page': paramJson['page'],
        'size': paramJson['size']
    }

    result = sql_list(params)

    return jsonify(result)

@app.route("/sqldelete",methods=["POST"])
def sql_delete_handler():

    paramJson = request.get_json()
    params = {
        "assistant_id": paramJson["assistant_id"],
        "qtype": paramJson["qtype"]
    }

    result = sql_delete(params)

    return jsonify(result)


#--------------------------start chat-------------------------------


@app.route('/startchat',methods=['POST'])
def start_chat_handler():

    paramJson = request.get_json()
    params = {
        'assistant_id': paramJson['assistant_id'],
        'db_id': paramJson['db_id'],
        'llm': paramJson['llm'],
        'tool': paramJson['tool'],
        'user_input': paramJson['user_input']
    }

    result = startchat(params)

    return jsonify(result)






if __name__ == '__main__':
    app.run(host='0.0.0.0', port = 5000, debug=True)
