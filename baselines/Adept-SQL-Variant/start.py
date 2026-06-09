from types import SimpleNamespace
from user_input_process import user_input_init
from search_qtype import search_qtype
from prompt_templates import Prompt_Zeroshot, Prompt_Fewshot
from generate_sql import generate_sql
from execute_sql import execute_sql
from generate_answer import generate_answer
from utils import *

def main(params):
    

    user_input = params["user_input"]
    assistant_id = params["assistant_id"]
    llm = params["llm"]
    db_id = params["db_id"]




    print_pink('='*50+'User Question Packaging')
    try:
        full_processed_input = user_input_init(user_input).full_process()
    except:
        full_processed_input=SimpleNamespace(trans=user_input)



    print_pink('='*50+'Search of Pre-stored SQL')
    not_exist, info, qtype = search_qtype(full_processed_input,assistant_id,params["skeleton_type"])
    print(info,qtype)
    params["qtype_search_res"] = '\n'.join([info, qtype])


    print_pink('='*50+'SQL Generation')
    if not_exist:
        prompt = Prompt_Zeroshot(full_processed_input, db_id, assistant_id,llm).compile()
        print_blue(prompt)

    else:
        prompt = Prompt_Fewshot(full_processed_input, qtype, assistant_id,llm).compile()
        print_blue(prompt)


    sql = generate_sql(prompt=prompt, llm=llm)
    print_green(sql)
    params["sql"] = sql.replace('\n',' ')
    

    print_pink('='*50+'SQL Execution')
    sql_exe_info, data = execute_sql(sql)
    print(sql_exe_info)
    params["sql_exe_info"] = sql_exe_info



    print_pink('='*50+'Answer Generation')
    answer = generate_answer(params,llm)


    print_pink('='*50+'Return Value')
    print()
    print({"sql": sql,  
            "answer": answer,
            "table": data})

    return({"sql": sql,  
            "answer": answer,
            "table": data})


if __name__ == "__main__":
    params = {
        "assistant_id": "149",
        "llm":'qwen-72b-instruct',
        "db_id": "1",
        "user_input":"In the Image Data Commons (IDC), which raw datasets have the largest number of samples? List the top five.",
        "skeleton_type":"skeleton1"
    }
    res = main(params)
    print(res)
