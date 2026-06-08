import logging
from typing import Any, Dict
from pathlib import Path
from pipeline.utils import node_decorator,get_last_node_result
from pipeline.pipeline_manager import PipelineManager
from runner.database_manager import DatabaseManager
from llm.model import model_chose
import json
from llm.prompts import *


@node_decorator(check_schema_status=False)
def extract_col_value(task: Any, execution_history: Dict[str, Any]) -> Dict[str, Any]:
    config, node_name = PipelineManager().get_model_para()
    paths = DatabaseManager()
    fewshot_path = paths.db_fewshot_path
    chat_model = model_chose(node_name, config["engine"])

    with open(fewshot_path, encoding='utf-8') as f:
        df_fewshot = json.load(f)

    # --- 逻辑更新：根据题目文本匹配 Few-shot ---
    target_question = task.question.strip()
    fewshot_prompt = None
    
    # 遍历列表寻找匹配项
    for item in df_fewshot.get("extract", []):
        if item.get("raw_question", "").strip() == target_question:
            fewshot_prompt = item.get("prompt")
            break
    
    # 如果没搜到匹配的题目，回退到默认（比如第0个）防止 pipeline 崩掉
    if fewshot_prompt is None:
        print(f"Warning: No matching few-shot found for question: {target_question}. Using default index 0.")
        fewshot_prompt = df_fewshot["extract"][0]['prompt']
    # ------------------------------------------

    hint = task.evidence if task.evidence else "None"
    all_info = get_last_node_result(execution_history, "generate_db_schema")["db_list"]
    
    key_col_des_raw = get_des_ans(chat_model,
                                db_check_prompts().extract_prompt,
                                fewshot_prompt,
                                all_info,
                                task.question,
                                hint,
                                False,
                                temperature=config["temperature"])

    return {"key_col_des_raw": key_col_des_raw}

def get_des_ans(chat_model,
                ext_prompt,
                fewshot,
                db,
                question,
                hint,
                debug,
                temperature=1.0):
    fewshot = fewshot.split("/* Answer the following:")[1:6]
    fewshot = "/* Answer the following:" + "/* Answer the following:".join(
        fewshot)
    ext_prompt = ext_prompt.format(fewshot=fewshot,
                                   db_info=db,
                                   query=question,
                                   hint=hint)

    if debug:
        print(ext_prompt)
    pre_col_values = chat_model.get_ans(ext_prompt, temperature,
                                        debug=debug).replace('```', '')

    return pre_col_values


