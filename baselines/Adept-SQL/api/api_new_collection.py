
import os,sys
pythonon_path = os.path.dirname('../')
sys.path.append(pythonon_path)

from op_DB import vecdb_op

def new_collection(params):

    try:
        res = vecdb_op(params['assistant_id']).check_collection()
        return({"info": res, "status": 1})
    except Exception as e:
        return({"info": f"{e}", "status": 0})
    

from flask import Flask,request,jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

@app.route("/newcolle",methods=["POST"])
def new_collection_handler():

    paramJson = request.get_json()
    params = {
        "assistant_id": paramJson["assistant_id"]
    }

    result = new_collection(params)

    return jsonify(result)


if __name__ == "__main__":
    # app.run(host="0.0.0.0", debug=True)
    params = {
        'assistant_id': '148'
        }
    print(new_collection(params))
