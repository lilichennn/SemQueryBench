import logging
from typing import Any, Dict, List
from pipeline.utils import node_decorator,get_last_node_result
from pipeline.pipeline_manager import PipelineManager
from runner.database_manager import DatabaseManager
from pipeline.utils import make_newprompt
from llm.model import model_chose
from llm.db_conclusion import *
import json
from llm.prompts import *
from runner.check_and_correct import get_sql
import random

def random_reduce_column_lines(
    column: str,
    max_column_chars: int = 55000,
    seed: int = 42
) -> str:
    """
    随机删除 column schema 中的部分字段行，使 column 字符长度不超过 max_column_chars。
    每一行格式类似：
    ghcnd_1764.qflag: varchar(3), Include Null.
    """
    if len(column) <= max_column_chars:
        return column

    lines = [line for line in column.splitlines() if line.strip()]

    if not lines:
        return column[:max_column_chars]

    keep_ratio = max_column_chars / len(column)
    keep_ratio = max(0.05, min(1.0, keep_ratio))

    keep_num = max(1, int(len(lines) * keep_ratio))

    rng = random.Random(seed)
    kept_indices = sorted(rng.sample(range(len(lines)), keep_num))

    reduced_lines = [lines[i] for i in kept_indices]
    reduced_column = "\n".join(reduced_lines)

    # 如果按比例保留后仍然超过目标长度，继续随机删
    while len(reduced_column) > max_column_chars and len(reduced_lines) > 1:
        remove_num = max(1, int(len(reduced_lines) * 0.05))
        remove_indices = set(rng.sample(range(len(reduced_lines)), remove_num))
        reduced_lines = [
            line for i, line in enumerate(reduced_lines)
            if i not in remove_indices
        ]
        reduced_column = "\n".join(reduced_lines)

    return reduced_column

@node_decorator(check_schema_status=False)
def candidate_generate(task: Any, execution_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    config,node_name=PipelineManager().get_model_para()
    paths=DatabaseManager()
    fewshot_path=paths.db_fewshot_path

    with open(fewshot_path, encoding='utf-8') as f:## fewshot
        df_fewshot = json.load(f)

    chat_model = model_chose(node_name,config["engine"])  # deepseek qwen-max gpt qwen-max-longcontext
    column = get_last_node_result(execution_history, "column_retrieve_and_other_info")["column"]
    
    # 临时代码，缩短 prompt 长度
    column = column.replace(', Non-Null, Non-Unique', '') \
                .replace(', Non-Unique.', '.') \
                .replace('Type:', '')

    column = random_reduce_column_lines(
        column,
        max_column_chars=55000,
        seed=42
    )

    foreign_keys= get_last_node_result(execution_history, "column_retrieve_and_other_info")["foreign_keys"]
    L_values = get_last_node_result(execution_history, "column_retrieve_and_other_info")["L_values"]
    q_order = get_last_node_result(execution_history, "column_retrieve_and_other_info")["q_order"]
    values = [f"{x[0]}: '{x[1]}'" for x in L_values]
    db=task.db_id

    key_col_des = "#Values in Database:\n" + '\n'.join(values)
    # key_col_des = ""
    
    new_db_info = f"Database Management System: MySQL\n#Database name: {db} \n{column}\n\n#Forigen keys:\n{foreign_keys}\n"
    # new_db_info=get_last_node_result(execution_history, "generate_db_schema")["db_list"]

    # question=rewrite_question(task.question)
    question=task.question
    print(question)
    target_question = task.question.strip()
    fewshot = None
    for item in df_fewshot.get("questions", []):
        if item.get("raw_question", "").strip() == target_question:
            fewshot = item.get("prompt")
            break
    # fewshot=""
    # fewshot=fewshot.split("\n/* Given the following database schema: */")[0]
    new_prompt = make_newprompt(db_check_prompts().new_prompt, fewshot,
                            key_col_des, new_db_info, question,
                            task.evidence,q_order)

    single = config['single'].lower() == 'true'  # 将字符串转换为布尔值
    return_question=config['return_question']== 'true' 

    # print("=" * 80)
    # print("[candidate_generate] prompt length debug")
    # print("len(fewshot):", len(fewshot) if fewshot else 0)
    # print("len(key_col_des):", len(key_col_des))
    # print("len(new_db_info):", len(new_db_info))
    # print("len(question):", len(question))
    # print("len(task.evidence):", len(task.evidence) if task.evidence else 0)
    # print("len(q_order):", len(str(q_order)) if q_order else 0)
    # print("len(new_prompt):", len(new_prompt))
    # print("L_values count:", len(L_values))
    # print("column length:", len(column))
    # print("foreign_keys length:", len(foreign_keys))
    # print("=" * 80)

    SQL,_ = get_sql(chat_model, new_prompt, config['temperature'], return_question=return_question,n=config['n'],single=single)

    
    response = {
        "rewrite_question":question,
        "SQL": SQL
        # "new_prompt":new_prompt
    }

    return response




def rewrite_question(question):
    if question.find(" / ")!=-1:
        question+=". For division operations, use CAST xxx AS REAL to ensure precise decimal results"
    return question
