import os
import pymysql
import re
import json
from datetime import datetime

def replace_cur_year(query: str) -> str:
    return re.sub(
        "YEAR\s*\(\s*CURDATE\s*\(\s*\)\s*\)\s*", "2020", query, flags=re.IGNORECASE
    )

    
def exec_sql(db_name, query): # 参数由 db_path 改为 db_name
    query = replace_cur_year(query)
    if not query.strip().lower().startswith('select'):
        query = 'SELECT ' + query
    try:
        # 请根据你的 Config 类修改 host, user, password
        conn = pymysql.connect(
            host='localhost',
            port=3306,
            user='root',
            password='YOUR DB PASSWORD', # 你的密码
            database=db_name,
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return True, result
    except Exception as e:
        return False, str(e)

def compare_results(result1, result2, order_matters=False):
    if len(result1) != len(result2):
        return False
    
    if order_matters:
        return result1 == result2
    else:
        return set(result1) == set(result2)

def normalize_sql(sql):
    """标准化SQL字符串以便比较"""
    sql = sql.strip()
    sql = re.sub(r'\s+', ' ', sql)
    sql = sql.lower()
    return sql

def evaluate_sql(pred_file, questions_file, db_dir, output_file=None):
    with open(questions_file, 'r') as f:
        questions_data = json.load(f)
    
    gold_queries = []
    for question in questions_data['questions']:
        gold_query = question['response']
        db_name = question['db_id']
        gold_queries.append((gold_query, db_name))
    
    with open(pred_file, 'r') as f:
        pred_lines = f.readlines()
    
    pred_queries = []
    for line in pred_lines:
        line = line.strip()
        if line and not line.startswith('--'):
            pred_queries.append(line)
    
    assert len(pred_queries) == len(gold_queries), f"查询数量不匹配: 生成 {len(pred_queries)} 个，黄金标准 {len(gold_queries)} 个"
    
    total = len(pred_queries)
    exec_correct = 0
    exact_match_correct = 0
    syntax_error = 0
    gold_error = 0
    
    details = []
    
    print("=" * 60)
    print("SQL评估报告")
    print("=" * 60)
    print(f"评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"预测文件: {pred_file}")
    print(f"问题文件: {questions_file}")
    print(f"数据库目录: {db_dir}")
    print("=" * 60)
    print(f"总查询数: {total}")
    print("=" * 60)
    
    for i, (pred_query, (gold_query, db_name)) in enumerate(zip(pred_queries, gold_queries)):
        db_name = db_name  # 直接使用传入的 db_name，无需路径拼接
        
        detail = {
            'index': i + 1,
            'db_id': db_name,
            'gold_query': gold_query,
            'pred_query': pred_query,
            'execution_match': False,
            'exact_match': False,
            'gold_result': None,
            'pred_result': None,
            'error': None
        }
        
        # if not os.path.exists(db_path):
        #     detail['error'] = f"数据库文件不存在: {db_path}"
        #     details.append(detail)
        #     continue
        
        gold_success, gold_result = exec_sql(db_name, gold_query)
        if not gold_success:
            detail['error'] = f"黄金查询执行失败: {gold_result}"
            details.append(detail)
            gold_error += 1
            continue
        
        detail['gold_result'] = str(gold_result)
        
        pred_success, pred_result = exec_sql(db_name, pred_query)
        if not pred_success:
            detail['error'] = f"生成查询执行失败: {pred_result}"
            details.append(detail)
            syntax_error += 1
            continue
        
        detail['pred_result'] = str(pred_result)
        
        order_matters = 'order by' in gold_query.lower()
        if compare_results(gold_result, pred_result, order_matters):
            exec_correct += 1
            detail['execution_match'] = True
            print(f"✓ 执行匹配 #{i+1}")
        else:
            print(f"✗ 执行不匹配 #{i+1}")
        
        normalized_gold = normalize_sql(gold_query)
        normalized_pred = normalize_sql(pred_query)
        if normalized_gold == normalized_pred:
            exact_match_correct += 1
            detail['exact_match'] = True
        
        details.append(detail)
    
    exec_accuracy = exec_correct / total if total > 0 else 0
    exact_match_accuracy = exact_match_correct / total if total > 0 else 0
    syntax_accuracy = (total - syntax_error - gold_error) / total if total > 0 else 0
    
    print("=" * 60)
    print("评估指标汇总")
    print("=" * 60)
    print(f"总查询数:              {total}")
    print(f"执行准确率 (EX):       {exec_correct}/{total} = {exec_accuracy:.4f} ({exec_accuracy*100:.2f}%)")
    print(f"精确匹配率 (EM):       {exact_match_correct}/{total} = {exact_match_accuracy:.4f} ({exact_match_accuracy*100:.2f}%)")
    print(f"语法正确率:            {total - syntax_error - gold_error}/{total} = {syntax_accuracy:.4f} ({syntax_accuracy*100:.2f}%)")
    print(f"  - 执行失败(语法错误): {syntax_error}")
    print(f"  - 黄金查询失败:      {gold_error}")
    print("=" * 60)
    
    output = []
    output.append("=" * 60)
    output.append("SQL评估报告 - 详细结果")
    output.append("=" * 60)
    output.append(f"评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append(f"预测文件: {pred_file}")
    output.append(f"问题文件: {questions_file}")
    output.append(f"数据库目录: {db_dir}")
    output.append("=" * 60)
    output.append("评估指标汇总")
    output.append("=" * 60)
    output.append(f"总查询数:              {total}")
    output.append(f"执行准确率 (EX):       {exec_correct}/{total} = {exec_accuracy:.4f} ({exec_accuracy*100:.2f}%)")
    output.append(f"精确匹配率 (EM):       {exact_match_correct}/{total} = {exact_match_accuracy:.4f} ({exact_match_accuracy*100:.2f}%)")
    output.append(f"语法正确率:            {total - syntax_error - gold_error}/{total} = {syntax_accuracy:.4f} ({syntax_accuracy*100:.2f}%)")
    output.append(f"  - 执行失败(语法错误): {syntax_error}")
    output.append(f"  - 黄金查询失败:      {gold_error}")
    output.append("=" * 60)
    output.append("详细结果")
    output.append("=" * 60)
    
    for detail in details:
        output.append(f"\n查询 #{detail['index']} - {detail['db_id']}")
        output.append(f"执行匹配: {'✓' if detail['execution_match'] else '✗'}")
        output.append(f"精确匹配: {'✓' if detail['exact_match'] else '✗'}")
        output.append(f"黄金SQL: {detail['gold_query']}")
        output.append(f"生成SQL: {detail['pred_query']}")
        if detail['gold_result']:
            output.append(f"黄金结果: {detail['gold_result'][:100]}...")
        if detail['pred_result']:
            output.append(f"生成结果: {detail['pred_result'][:100]}...")
        if detail['error']:
            output.append(f"错误: {detail['error']}")
    
    output_text = '\n'.join(output)
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"\n详细结果已保存到: {output_file}")
    
    print("\n" + output_text)
    
    return {
        'total': total,
        'exec_correct': exec_correct,
        'exec_accuracy': exec_accuracy,
        'exact_match_correct': exact_match_correct,
        'exact_match_accuracy': exact_match_accuracy,
        'syntax_error': syntax_error,
        'gold_error': gold_error,
        'details': details
    }

if __name__ == "__main__":
    pred_file = "./DAIL-SQL/dataset/process/BIRD-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-200_ANS-4096/RESULTS_MODEL-qwen-72b-instruct.txt"
    questions_file = "./DAIL-SQL/dataset/process/BIRD-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-200_ANS-4096/questions.json"
    db_dir = "./DAIL-SQL/dataset/bird/database"
    output_file = "./DAIL-SQL/evaluation_results.txt"
    
    result = evaluate_sql(pred_file, questions_file, db_dir, output_file)