
import os,sys
pythonon_path = os.path.dirname('../')
sys.path.append(pythonon_path)

from op_DB import vecdb_op


def sql_delete(params):

        
    db = vecdb_op(params['assistant_id'])
    res = db.delete_sqlQA(params['qtype'])

    if "delete_count" in res:
        return({"info": res, "status": 1})
    else:
        return({ "info": res, "status": 0 })




from flask import Flask,request,jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

@app.route("/sqldelete",methods=["POST"])
def sql_delete_handler():

    paramJson = request.get_json()
    params = {
        "assistant_id": paramJson["assistant_id"],
        "qtype": paramJson["qtype"]
    }

    result = sql_delete(params)

    return jsonify(result)


if __name__ == "__main__":
    #app.run(host="0.0.0.0", debug=True)

    params = {'assistant_id': '9',
              "qtype": "Test Description"}
    print(sql_delete(params))