import pickle
import gzip, re
import tqdm, json, random
import pandas as pd
import torch
import sqlite3, os
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import euclidean_distances
import argparse
import logging
import pymysql
device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

uuid_pattern = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
)


def filter_column(table, col, exclude_num, num_shold=6000):
    cols=table[col].unique()
    if len(cols) > num_shold and exclude_num:
        try:
            table[col].dropna().astype(float)
            return []  # 跳过当前列，因为它满足排除条件
        except ValueError:
            pass
    # 排除具有UUID格式的数据
    col_vals = [
        item for item in cols if isinstance(item, str)
        and not uuid_pattern.match(item) and len(item) < 100
    ]
    return col_vals


def make_emb(db, DB_emb, col_values, bert_model, exclude_int=True):
    # 1. 配置 MySQL 连接（根据你的信息硬编码）
    connection_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'YOUR DATABASE PASSWORD',  # 替换为你的数据库密码
        'database': db,  # 脚本会自动将 db_id 映射为数据库名
        'charset': 'utf8mb4'
    }

    try:
        # 建立连接
        conn = pymysql.connect(**connection_config)
        
        # 2. 获取当前数据库下所有的表名
        # MySQL 对应的查询是 SHOW TABLES
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tables = [row[0] for row in cursor.fetchall()]
        
        print(f"db name: {db}, table count: {len(tables)}")

        for table in tables:
            # 3. 读取表数据到 DataFrame (Pandas 支持直接传入 pymysql 连接)
            sql_t = f"SELECT * FROM `{table}`;"
            try:
                with conn.cursor() as cursor:
                    cursor.execute(sql_t)
                    # 获取数据并手动转换成 DataFrame
                    data = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    values = pd.DataFrame(data, columns=columns)
            except Exception as e:
                logging.warning(f"读取表 {table} 失败: {e}")
                continue

            # --- 下面是原有的 Embedding 逻辑，保持不变 ---
            # 排除数值列，只处理文本列
            values = values.select_dtypes(exclude=[np.number])
            for col in tqdm.tqdm(values.columns, desc=f"Processing {table}"):
                col_vals = filter_column(values, col, exclude_int)
                if len(col_vals) == 0:
                    continue
                
                # 对该列所有的 Unique 值生成向量索引
                train_embeddings = bert_model.encode(col_vals, device=device, batch_size=4)
                DB_emb[table + "." + col] = train_embeddings
                col_values[table + "." + col] = col_vals
                
    except Exception as e:
        logging.error(f"连接数据库 {db} 失败: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


def save_emb(dicts, dbname, emb_dir):
    with gzip.open(os.path.join(emb_dir, f'{dbname}.pkl.gz'),
                   'wb') as pkl_file:
        pickle.dump(dicts, pkl_file, protocol=pickle.HIGHEST_PROTOCOL)


def load_emb(dbname, emb_dir="Bird/emb"):
    with gzip.open(os.path.join(emb_dir, f'{dbname}.pkl.gz'),
                   'rb') as pkl_file:
        data = pickle.load(pkl_file)
    with gzip.open(os.path.join(emb_dir, f'{dbname}_value.pkl.gz'),
                   'rb') as pkl_file:
        col_vs = pickle.load(pkl_file)

    return data, col_vs

def make_emb_all(data_dir,bertmodel):
    emb_dir=os.path.join(data_dir,"emb")
    os.makedirs(emb_dir, exist_ok=True)
    data_dir=os.path.join(data_dir,"data_preprocess","dev.json")
    # init model
    bert_model = SentenceTransformer(bertmodel, device=device, cache_folder='model/')
    
    # load data
    Q = pd.read_json(data_dir)
    DB_emb = {}
    Db_names = set()
    col_values = {}
    
    for i, (id, q) in enumerate(tqdm.tqdm(Q.iterrows())):
        db = q['db_id']

        # --- 新增：断点续传逻辑 ---
        # 检查该数据库的向量文件和值文件是否都已经存在
        emb_file = os.path.join(emb_dir, f'{db}.pkl.gz')
        val_file = os.path.join(emb_dir, f'{db}_value.pkl.gz')
        
        if os.path.exists(emb_file) and os.path.exists(val_file):
            # 如果文件已存在，直接跳过这个数据库，不重复处理
            continue 
        # -----------------------

        if db not in Db_names:
            logging.info(f"Processing database: {db}") 
            col_values = {}
            DB_emb = {}
            make_emb(db, DB_emb, col_values,bert_model)
            save_emb(DB_emb, db, emb_dir)
            save_emb(col_values, db + '_value', emb_dir)
            Db_names.add(db)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate embeddings for the specified database.")
    parser.add_argument('--db_root_directory', type=str, help='Directory containing the data files.')
    parser.add_argument('--bert_model', type=str, help='Name of the BERT model to use.')

    args = parser.parse_args()
    logging.info(f"Start make_emb_for_dev,the output_file is {args.db_root_directory}/emb")
    make_emb_all(args.db_root_directory,args.bert_model)
