
import os,sys
pythonon_path = os.path.dirname('../')
sys.path.append(pythonon_path)

from op_DB import vecdb_op
from user_input_process import user_input_init


def sql_upload(params):

        
    db = vecdb_op(params['assistant_id'])
    del params['assistant_id']
    try:
        params["qtype"]= user_input_init(params['question']).full_process().trans
    except:
        params["qtype"]=params['question']

    res = db.insert_sqlQA(params)
    if "success" in res:
        return({"info": res, "status": 1})
    else:
        return({ "info": res, "status": 0 })




from flask import Flask,request,jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

@app.route("/sqlupload",methods=["POST"])
def sql_upload_handler():

    paramJson = request.get_json()
    params = {
        "assistant_id": paramJson["assistant_id"],
        "qtype": paramJson["qtype"],
        "question": paramJson["question1"],
        "sql": paramJson["sql1"]
    }

    result = sql_upload(params)

    return jsonify(result)


if __name__ == "__main__":
    #app.run(host="0.0.0.0", debug=True)

    params = {"assistant_id":"149",
            "question": "In this match sample, how many unique home teams have appeared? I would like to first understand the scale of teams covered by the league.", 
            "sql": "SELECT COUNT(DISTINCT m.home_team_api_id) AS distinct_entity_cnt FROM EU_SOCCER.MATCH m;",
            "skeleton_type":"skeleton2"}
    print(sql_upload(params))
