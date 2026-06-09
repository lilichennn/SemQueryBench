import os,sys
pythonon_path = os.path.dirname('../')
sys.path.append(pythonon_path)

from op_DB import backend_db_op
from op_DB import user_db_op


def term_update(params):

    # params处理
    table_info = backend_db_op(params['assistant_id']).query_table('table_info')
    print(table_info[table_info['id'] == int(params['table_id'])])
    table_name = table_info[table_info['id'] == int(params['table_id'])]['table_name'].values[0]
    params['table_name'] = table_name

    print(params)

    saved_terms_df = backend_db_op(params['assistant_id']).query_table('term_list')
    saved_terms_set = set(saved_terms_df['term'].values) 

    try:
        additional_terms = user_db_op(params['db_id']).query_field(params['table_name'], params['term_field'])
    except Exception as e:
        return({
            "info": "Error retrieving terms from user DB: " + str(params), 
            "status": 0
            })
    received_terms = params['term_list'].split(',') + list(set(additional_terms))

    new_terms = [{'term': term, 'type': params['term_field']} for term in received_terms if term not in saved_terms_set]

    if new_terms:
        res = backend_db_op(params['assistant_id']).insert_data('term_list', new_terms)
        if 'success' in res:
            return({'info': 'success', 'status': 1})
        else:
            return({'info': 'failed to insert data into term_list', 'status': 0})
    else:
        return({'info': 'no new terms found', 'status': 1})





from flask import Flask,request,jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

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


if __name__ == '__main__':
    #app.run(host='0.0.0.0', debug=True)

    params = {
    "db_id": "2",
    "table_id":"3",
    "term_field":"indexes_code",
    "term_list":"object1,object2,object3",
    "assistant_id":"9"
    }
        
    print(term_update(params))