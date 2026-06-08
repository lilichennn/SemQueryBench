import logging,re,json
from typing import Any, Dict
from pathlib import Path
from pipeline.utils import node_decorator,get_last_node_result
from pipeline.pipeline_manager import PipelineManager
from runner.database_manager import DatabaseManager
from sentence_transformers import SentenceTransformer
from llm.model import model_chose
from llm.db_conclusion import find_foreign_keys_MYSQL_like
from llm.prompts import *
from runner.extract import DES_new
from database_process.make_emb import load_emb
from runner.column_retrieve import ColumnRetriever
from runner.column_update import ColumnUpdater

@node_decorator(check_schema_status=False)
def column_retrieve_and_other_info(task: Any, execution_history: Dict[str, Any]) -> Dict[str, Any]:
    config,node_name=PipelineManager().get_model_para()
    paths=DatabaseManager()
    emb_dir=paths.emb_dir
    tables_info_dir=paths.db_tables
    chat_model = model_chose(node_name,config["engine"])
    from pipeline.utils import ModelLoader
    bert_model = ModelLoader.get_model(config["bert_model"], config["device"])

    all_db_col = get_last_node_result(execution_history, "generate_db_schema")["db_col_dic"]#返回最后面等于 参数名的结果
    origin_col = get_last_node_result(execution_history, "extract_query_noun")["col"]
    values = get_last_node_result(execution_history, "extract_query_noun")["values"]

    # hint = task.evidence
    # if hint == "":
    #     hint = "None"
    db=task.db_id

    emb_values_dic = {}
    if emb_values_dic.get(db):
        DB_emb, col_values = emb_values_dic[db]
    else:
        DB_emb, col_values = load_emb(db, emb_dir)
        emb_values_dic[db] = [DB_emb, col_values]

    db_col = {x: all_db_col[x][0] for x in all_db_col }  ## db string
    db_keys_col=all_db_col.keys()

    col_retrieve = ColumnRetriever(bert_model,tables_info_dir).get_col_retrieve(task.question, db,db_keys_col)

    foreign_keys, foreign_set = find_foreign_keys_MYSQL_like(tables_info_dir, db)      
    cols=ColumnUpdater(db_col).col_pre_update(origin_col,col_retrieve,foreign_set)

    des = DES_new(bert_model, DB_emb, col_values)   

    cols_select, L_values = des.get_key_col_des(cols,
                                    values,
                                    debug=False,
                                    topk=config['top_k'],
                                    shold=0.65)

    column=ColumnUpdater(db_col).col_suffix(cols_select)
    # values = [f"{x[0]}: '{x[1]}'" for x in L_values]
    count=0
    while count<3:
        try:
            q_order=query_order(task.raw_question,chat_model,db_check_prompts().select_prompt,temperature=config['temperature'])
            break
        except:
            count+=1

    # # q_order = f"The content of the SELECT statement should only include: {q_order}"
    # q_order=""

    response = {
        # "col_retrieve":list(col_retrieve),
        # "col_select":list(cols_select),
        "L_values":L_values,
        "column":column,
        "foreign_keys":foreign_keys,
        "foreign_set":foreign_set,
        "q_order":q_order
    }

    return response


def extract_json_array(text: str) -> str:
    text = str(text).strip()
    text = re.sub(r"```json|```", "", text).strip()

    start = text.find("[")
    end = text.rfind("]")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No valid JSON array found in LLM output: {repr(text[:500])}")

    return text[start:end + 1]


def query_order(question, chat_model, select_prompt, temperature):
    fallback_res = [question]

    try:
        prompt = select_prompt.format(question=question)

        ans = chat_model.get_ans(prompt, temperature=temperature)


        ans = extract_json_array(ans)

        select_json = json.loads(ans)

        if isinstance(select_json, dict):
            select_json = [select_json]

        res, judge = json_ext(select_json)

        print("[query_order] parsed res:", res)
        print("[query_order] judge:", judge)

        return res

    except Exception as e:
        print(f"Warning: query_order 失败，应用 Hard-coded 保底。错误: {repr(e)}")
        return fallback_res


def json_ext(jsonf):
    ans = []
    judge = False

    for x in jsonf:
        if x.get("Type") == "QIC":
            extract = x.get("Extract", {})

            I = extract.get("I") or []
            C = extract.get("C") or []

            if isinstance(I, str):
                I = [I]
            if isinstance(C, str):
                C = [C]

            ans.extend(I)
            ans.extend(C)

        elif x.get("Type") == "JC":
            extract = x.get("Extract", {})
            J = extract.get("J")
            if J:
                ans.append(J)
            judge = True

    return ans, judge