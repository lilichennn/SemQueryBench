import argparse
import os
import json

import openai
from tqdm import tqdm

from llm.chatgpt import init_chatgpt, ask_llm
from utils.enums import LLM
from torch.utils.data import DataLoader

from utils.post_process import process_duplication, get_sqls

QUESTION_FILE = "questions.json"

def extract_sql_from_response(response):

    response = response.strip()
    sql = ""

    try:

        if "```sql" in response:
            sql = response.split("```sql")[1].split("```")[0].strip()
        elif "```" in response:

            sql = response.split("```")[1].split("```")[0].strip()
        else:

            lines = response.split("\n")
            for i, line in enumerate(lines):
                stripped = line.strip()

                if stripped.upper().startswith("SELECT"):

                    sql_lines = [stripped]
                    for next_line in lines[i+1:]:
                        next_stripped = next_line.strip()
                        sql_lines.append(next_stripped)
                        if next_stripped.endswith(");"):
                            break
                    sql = " ".join(sql_lines)
                    break
                

                if not sql:

                    if "SELECT" in response.upper():

                        select_pos = response.upper().find("SELECT")
                        if select_pos >= 0:

                            sql_part = response[select_pos:]

                            semicolon_pos = sql_part.find(");")
                            if semicolon_pos >= 0:
                                sql = sql_part[:semicolon_pos + 1]
                            else:

                                sql = sql_part
    except Exception as e:
        print(f"Error extracting SQL: {e}")
        sql = ""
    
    return sql


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", type=str)
    parser.add_argument("--openai_api_key", type=str)
    parser.add_argument("--openai_group_id", type=str, default="org-ktBefi7n9aK7sZjwc2R9G1Wo")
    parser.add_argument("--model", type=str, choices=[LLM.TEXT_DAVINCI_003, 
                                                      LLM.GPT_35_TURBO,
                                                      LLM.GPT_35_TURBO_0613,
                                                      # LLM.TONG_YI_QIAN_WEN,
                                                      LLM.GPT_35_TURBO_16K,
                                                      LLM.GPT_4,
                                                      LLM.QWEN_72B_INSTRUCT],
                        default=LLM.GPT_35_TURBO)
    parser.add_argument("--start_index", type=int, default=0)
    parser.add_argument("--end_index", type=int, default=1000000)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--mini_index_path", type=str, default="")
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--n", type=int, default=5, help="Size of self-consistent set")
    parser.add_argument("--db_dir", type=str, default="dataset/spider/database")
    args = parser.parse_args()

    # check args
    assert args.model in LLM.BATCH_FORWARD or \
           args.model not in LLM.BATCH_FORWARD and args.batch_size == 1, \
        f"{args.model} doesn't support batch_size > 1"

    questions_json = json.load(open(os.path.join(args.question, QUESTION_FILE), "r", encoding='utf-8'))
    questions = [_["prompt"] for _ in questions_json["questions"]]
    db_ids = [_["db_id"] for _ in questions_json["questions"]]

    # init openai api
    init_chatgpt(args.openai_api_key, args.openai_group_id, args.model)

    if args.start_index == 0:
        mode = "w"
    else:
        mode = "a"

    if args.mini_index_path:
        mini_index = json.load(open(args.mini_index_path, 'r', encoding='utf-8'))
        questions = [questions[i] for i in mini_index]
        out_file = f"{args.question}/RESULTS_MODEL-{args.model}_MINI.txt"
    else:
        out_file = f"{args.question}/RESULTS_MODEL-{args.model}.txt"

    question_loader = DataLoader(questions, batch_size=args.batch_size, shuffle=False, drop_last=False)

    print(f"Total questions: {len(questions)}")
    print(f"Batch size: {args.batch_size}")
    print(f"Total batches: {len(list(question_loader))}")
    print(f"Start index: {args.start_index}, End index: {args.end_index}")

    # Test writing to file first
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write("-- Test line 1\nSELECT test_column FROM test_table\n")
        f.flush()
    print(f"✅ Test write successful. Results file: {out_file}")
    print(f"Test file content: {open(out_file, 'r').read()}")
    
    token_cnt = 0
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write("-- Starting SQL generation\n")
        f.flush()
        
        for i, batch in enumerate(question_loader):
            print(f"\n=== Processing batch {i+1} ===")
            print(f"Batch content: {batch}")
            
            if i < args.start_index:
                print(f"Skipping batch {i+1} (start_index: {args.start_index})")
                continue
            if i >= args.end_index:
                print(f"Stopping at batch {i+1} (end_index: {args.end_index})")
                break
                
            print(f"Processing batch {i+1}/{len(list(question_loader))}")
            try:
                print(f"Calling ask_llm with model: {args.model}")
                res = ask_llm(args.model, batch, args.temperature, args.n)
                print(f"ask_llm returned: {res}")
            except Exception as e:
                print(f"Error calling ask_llm: {e}")
                continue

            # parse result
            token_cnt += res["total_tokens"]
            print(f"Token count: {token_cnt}")


            print(f"Response format: {type(res['response'])}")
            if isinstance(res['response'], list):
                print(f"Response length: {len(res['response'])}")
                if res['response']:
                    print(f"First response sample: {res['response'][0][:100]}...")
            
            if args.n == 1:
                print(f"Processing in single response mode")
                for j, response in enumerate(res["response"]):

                    print(f"Processing response {j+1}/{len(res['response'])}")
                    sql = extract_sql_from_response(response)
                    print(f"Extracted SQL: {sql}")
                    if not sql:
                        print(f"Failed to extract SQL from response: {response[:100]}...")

                        f.write(f"-- Failed to extract SQL: {response[:50]}...\n")
                        continue
                    # remove \n and extra spaces
                    sql = " ".join(sql.replace("\n", " ").split())
                    sql = process_duplication(sql)

                    if not sql.upper().startswith("SELECT"):
                        sql = "SELECT " + sql
                    print(f"Writing SQL: {sql}")
                    f.write(sql + "\n")
                    # Flush to file immediately
                    f.flush()
            else:
                print(f"Processing in self-consistency mode (n={args.n})")
                results = []
                cur_db_ids = db_ids[i * args.batch_size: i * args.batch_size + len(batch)]
                print(f"Current DB IDs: {cur_db_ids}")
                
                # res['response'] is a list of question responses
                # each question response is a list of n responses (since n=5)
                for q_idx, sqls_responses in enumerate(res['response']):
                    db_id = cur_db_ids[q_idx] if q_idx < len(cur_db_ids) else "unknown"
                    
                    processed_sqls = []
                    print(f"Processing question {q_idx+1} with {len(sqls_responses)} responses for db_id {db_id}")
                    for j, response in enumerate(sqls_responses):
                        print(f"Processing response {j+1}: {response[:50]}...")

                        sql = extract_sql_from_response(response)
                        print(f"Extracted SQL {j+1}: {sql}")
                        if not sql:
                            print(f"Failed to extract SQL from response {j+1}: {response[:50]}...")
                            continue
                        # remove \n and extra spaces
                        sql = " ".join(sql.replace("\n", " ").split())
                        sql = process_duplication(sql)

                        if not sql.upper().startswith("SELECT"):
                            sql = "SELECT " + sql
                        processed_sqls.append(sql)
                        print(f"Added to processed_sqls: {sql}")
                        
                    print(f"Total processed SQLs: {len(processed_sqls)}")
                    if not processed_sqls:
                        print(f"No SQLs extracted for db_id {db_id}")
                        f.write(f"-- No SQLs extracted for db_id {db_id}\n")
                        f.flush()
                        continue
                        
                    result = {
                        'db_id': db_id,
                        'p_sqls': processed_sqls
                    }
                    print(f"Calling get_sqls with result: {result}")
                    final_sqls = get_sqls([result], args.n, args.db_dir)
                    print(f"Got {len(final_sqls)} final SQLs from get_sqls")
                    
                    for sql in final_sqls:
                        print(f"Writing final SQL: {sql}")
                        f.write(sql + "\n")
                        f.flush()
    
    print(f"\n=== Processing complete ===")
    print(f"Total tokens: {token_cnt}")
    print(f"Results written to: {out_file}")