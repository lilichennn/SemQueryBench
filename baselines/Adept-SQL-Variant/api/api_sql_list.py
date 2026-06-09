
import os,sys
pythonon_path = os.path.dirname('../')
sys.path.append(pythonon_path)

from op_DB import vecdb_op

def sql_list(params):

    
    db = vecdb_op(params['assistant_id'])
    del params['assistant_id']
    res = db.list_sqlQA(params)
    
    if "success" in res:
        return({"info": res, "status": 1})
    else:
        return({"info": res,  "status": 0})

from flask import Flask,request,jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

@app.route("/sqllist",methods=["POST"])
def sql_list_handler():

    paramJson = request.get_json()
    params = {
        "qtype": paramJson["qtype"],
        "question": paramJson["question1"],
        "sql": paramJson["sql1"],
        "assistant_id": paramJson["assistant_id"]
    }

    result = sql_list(params)

    return jsonify(result)


if __name__ == "__main__":
    # app.run(host="0.0.0.0", debug=True)
    params = {"qtype": "Final Test",
                "question": "This is a more virtual question", 
                "sql": "SELECT 111"}
    print(sql_list(params))
