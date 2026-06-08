import argparse, os, sys, re, tqdm
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm.model import model_chose

# 设置基本配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 保留你原来的辅助函数 ---
def convert_table(s, sql):
    l = re.findall(' ([^ ]*) +AS +([^ ]*)', sql)
    for li in l:
        s = s.replace(f" {li[1]}.", f" {li[0]}.")
    return s

def extract_ans(sql, ans):
    reason_match = re.search("#reason:.*", ans)
    reason = reason_match.group() if reason_match else "#reason: N/A"
    column_match = re.search("#columns:.*", ans)
    column = column_match.group() if column_match else "#columns: N/A"
    
    vals = re.findall("'((?:''|[^'])*)'", sql)
    vals_f = [f"\"{x}\"" for x in vals if x != "%Y"]
    final_str = f"{reason}\n{column}\n#values: {', '.join(vals_f)}"
    return final_str

# --- 新增：单个任务的处理函数 ---
def process_single_row(i, row, model_name):
    """处理单行数据的 worker 函数"""
    q, e, sql = row['question'], row["evidence"], row["SQL"]
    for attempt in range(3):
        try:
            # 获取模型实例并调用
            model_instance = model_chose("prepare_train_queries", model_name)
            content = model_instance.fewshot_parse(q, e, sql)
            
            parse_content = content.strip() + "\n#SQL: " + sql
            extract_content = extract_ans(sql, content)
            
            return i, parse_content, extract_content
        except Exception as err:
            if attempt == 2:  # 最后一次尝试失败
                logging.error(f"Error processing row {i} after 3 attempts: {str(err)}")
    return i, None, None

def prepare_train_queries(data_dir, new_train_dir, model_name, start=0, end=9427, max_workers=3):
    train_json = os.path.join(data_dir, 'data_preprocess', 'train.json')
    df = pd.read_json(train_json)
    end = min(end, len(df))
    
    # 选定需要处理的范围
    target_df = df.iloc[start:end]
    results = [None] * len(target_df)
    
    logging.info(f"正在启动并发处理，最大线程数: {max_workers}")

    # 使用线程池进行并发 LLM 调用
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_idx = {
            executor.submit(process_single_row, i, df.iloc[i], model_name): i 
            for i in range(start, end)
        }
        
        # 使用 tqdm 渲染进度条
        for future in tqdm.tqdm(as_completed(future_to_idx), total=len(future_to_idx)):
            idx, parse_res, extract_res = future.result()
            if parse_res:
                df.at[idx, 'parse'] = parse_res
                df.at[idx, 'extract'] = extract_res

    # 保存结果
    df[start:end].to_json(new_train_dir, orient='records', indent=4, force_ascii=False)
    logging.info(f"处理完成，结果已保存至: {new_train_dir}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db_root_directory', type=str, default="Bird")
    parser.add_argument('--model', type=str, default="gpt-4o-mini-0718")
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--end', type=int, default=9428)
    parser.add_argument('--max_workers', type=int, default=3, help='并行线程数') # 新增参数
    
    args = parser.parse_args()

    llm_train_json = os.path.join(args.db_root_directory, 'llm_train_parse.json')
    prepare_train_queries(
        args.db_root_directory,
        llm_train_json,
        args.model,
        args.start,
        args.end,
        args.max_workers
    )