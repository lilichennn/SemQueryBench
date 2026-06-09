import os,sys
pythonon_path = os.path.dirname('../')
sys.path.append(pythonon_path)

from op_DB import backend_db_op


def term_delete(params):

    db = backend_db_op(params["assistant_id"])
    res = db.delete_data_in_termlist(params["term"])

    if 'success' in res:
        return {"info":res, "status":1}
    else:
        return {"info":res, "status":0}




from flask import Flask,request,jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

@app.route('/termdelete',methods=['POST'])
def term_delete_handler():

    paramJson = request.get_json()
    params = {
        'term': paramJson['term'],
        'assistant_id': paramJson['assistant_id']
    }

    result = term_delete(params)

    return jsonify(result)


if __name__ == '__main__':
    #app.run(host='0.0.0.0', debug=True)

    params = {
    "term":"obiect2",
    "assistant_id":"9"
    }
        
    print(term_delete(params))