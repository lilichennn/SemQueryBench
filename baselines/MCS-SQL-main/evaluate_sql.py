"""Release-safe MySQL execution evaluator for MCS-SQL predictions.

Database credentials and file paths are read from environment variables.
"""

import os
import pymysql
import re
import json
from datetime import datetime
MYSQL_CONFIG = {'host': os.getenv('MCS_SQL_MYSQL_HOST', 'localhost'), 'port': int(os.getenv('MCS_SQL_MYSQL_PORT', '3306')), 'user': os.getenv('MCS_SQL_MYSQL_USER', 'root'), 'password': os.getenv('MCS_SQL_MYSQL_PASSWORD', ''), 'charset': 'utf8mb4', 'autocommit': True}

def replace_cur_year(query: str) -> str:
    return re.sub('YEAR\\s*\\(\\s*CURDATE\\s*\\(\\s*\\)\\s*\\)\\s*', '2020', query, flags=re.IGNORECASE)

def exec_sql(db_name, query):
    query = replace_cur_year(query)
    if not query.strip().lower().startswith('select'):
        query = 'SELECT ' + query
    try:
        conn = pymysql.connect(database=db_name, **MYSQL_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SET SESSION MAX_EXECUTION_TIME = 10000')
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return (True, result)
    except Exception as e:
        return (False, str(e))

def compare_results(result1, result2, order_matters=False):
    if len(result1) != len(result2):
        return False
    if order_matters:
        return result1 == result2
    else:
        try:
            return set(result1) == set(result2)
        except:
            return sorted((str(r) for r in result1)) == sorted((str(r) for r in result2))

def normalize_sql(sql):
    sql = sql.strip()
    sql = re.sub('\\s+', ' ', sql)
    sql = sql.lower()
    return sql

def evaluate_sql(pred_file, questions_file, output_file=None):
    with open(questions_file, 'r', encoding='utf-8') as f:
        gold_data = json.load(f)
    gold_map = {item['question_id']: (item['SQL'], item['db_id']) for item in gold_data}
    with open(pred_file, 'r', encoding='utf-8') as f:
        pred_results = json.load(f)
    total = len(pred_results)
    exec_correct = 0
    exact_match_correct = 0
    syntax_error = 0
    gold_error = 0
    details = []
    print('=' * 60)
    print('SQL Evaluation Report (MySQL Adapted Version)')
    print('=' * 60)
    print(f"Evaluation time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f'Total samples: {total}')
    print('=' * 60)
    for i, pred_item in enumerate(pred_results):
        q_id = pred_item.get('question_id')
        pred_query = pred_item.get('predicted_sql', '')
        if q_id not in gold_map:
            print(f'⚠️ Warning: no gold item found for ID {q_id}')
            continue
        gold_query, db_name = gold_map[q_id]
        detail = {'index': i + 1, 'db_id': db_name, 'gold_query': gold_query, 'pred_query': pred_query, 'execution_match': False, 'exact_match': False, 'error': None}
        gold_success, gold_result = exec_sql(db_name, gold_query)
        if not gold_success:
            detail['error'] = f'Gold query execution failed: {gold_result}'
            gold_error += 1
            details.append(detail)
            continue
        pred_success, pred_result = exec_sql(db_name, pred_query)
        if not pred_success:
            detail['error'] = f'Predicted query execution failed: {pred_result}'
            syntax_error += 1
            details.append(detail)
            continue
        order_matters = 'order by' in gold_query.lower()
        if compare_results(gold_result, pred_result, order_matters):
            exec_correct += 1
            detail['execution_match'] = True
            print(f'✓ ID {q_id}: execution match')
        else:
            print(f'✗ ID {q_id}: execution mismatch')
        if normalize_sql(gold_query) == normalize_sql(pred_query):
            exact_match_correct += 1
            detail['exact_match'] = True
        details.append(detail)
    exec_accuracy = exec_correct / total if total > 0 else 0
    exact_match_accuracy = exact_match_correct / total if total > 0 else 0
    summary = f"\n{'=' * 60}\nMetric Summary\n{'=' * 60}\nExecution Accuracy (EX): {exec_correct}/{total} = {exec_accuracy:.4f} ({exec_accuracy * 100:.2f}%)\nExact Match Accuracy (EM): {exact_match_correct}/{total} = {exact_match_accuracy:.4f} ({exact_match_accuracy * 100:.2f}%)\nSyntax errors: {syntax_error}\nGold SQL errors: {gold_error}\n{'=' * 60}\n"
    print(summary)
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(summary)
            json.dump(details, f, ensure_ascii=False, indent=2)
        print(f'Results saved to: {output_file}')
if __name__ == '__main__':
    base_path = os.getenv('MCS_SQL_BASE_DIR', '.')
    data_path = os.getenv('MCS_SQL_QUESTIONS_FILE', os.path.join('dataset', 'easy', 'dev', 'dev.json'))
    pred_file = os.getenv('MCS_SQL_PRED_FILE', os.path.join(base_path, 'predictions.json'))
    output_file = os.getenv('MCS_SQL_EVAL_OUTPUT', os.path.join(base_path, 'evaluation_results.txt'))
    evaluate_sql(pred_file, data_path, output_file)
