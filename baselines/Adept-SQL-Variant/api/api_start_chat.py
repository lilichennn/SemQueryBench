
import os,sys
pythonon_path = os.path.dirname('../')
sys.path.append(pythonon_path)

from start import main

def startchat(params):

    res = main(params)


    return(res)



from flask import Flask,request,jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

@app.route('/startchat',methods=['POST'])
def start_chat_handler():

    paramJson = request.get_json()
    params = {
        'llm': paramJson['llm'],
        'db_id': paramJson['database_id'],
        'tool': paramJson['tool'],
        'user_input': paramJson['user_input'],
        'assistant_id': paramJson['assistant_id']
    }

    result = startchat(params)

    return jsonify(result)


if __name__ == '__main__':
    #app.run(host='0.0.0.0', debug=True)

    params = {
        "assistant_id": "9",
        "llm":"qwen",
        "db_id": "1",
        "tool": "SUM",
        "user_input": "How many apples were eaten in total yesterday?"
    }
    print(startchat(params))