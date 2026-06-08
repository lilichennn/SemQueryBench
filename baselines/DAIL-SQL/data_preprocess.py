import argparse
import json
import os
import pickle
from pathlib import Path
import sqlite3
from tqdm import tqdm
import random
import shutil
import glob
import jieba
import os
import torch

from utils.linking_process import SpiderEncoderV2Preproc
from utils.pretrained_embeddings import GloVe
from utils.datasets.spider import load_tables
# from dataset.process.preprocess_kaggle import gather_questions

import pymysql

def get_mysql_connection(db_name):
    try:
        conn = pymysql.connect(
            host='localhost',      
            user='root',          
            port = 3306,
            password='YOUR PASSWORD',      
            database=db_name,         
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor 
        )
        return conn
    except Exception as e:
        print(f"Error connecting to MySQL database {db_name}: {e}")
        return None
    
def schema_linking_producer(test, train, table, db, dataset_dir, compute_cv_link=True):

    # load data
    test_data = json.load(open(os.path.join(dataset_dir, test), encoding='utf-8'))
    train_data = json.load(open(os.path.join(dataset_dir, train), encoding='utf-8'))

    # load schemas
    schemas, _ = load_tables([os.path.join(dataset_dir, table)])

    for db_id, schema in tqdm(schemas.items(), desc="DB connections"):

        print(f"Connecting to MySQL DB: {db_id}")
        

        conn = get_mysql_connection(db_id)
        
        if conn is not None:

            schema.connection = conn
        else:
            print(f"Warning: Failed to connect to {db_id}, this may cause errors in linking.")

    word_emb = GloVe(kind='6B', lemmatize=True)
    linking_processor = SpiderEncoderV2Preproc(dataset_dir,
            min_freq=4,
            max_count=5000,
            include_table_name_in_column=False,
            word_emb=word_emb,
            fix_issue_16_primary_keys=True,
            compute_sc_link=True,
            compute_cv_link=compute_cv_link)

    # build schema-linking
    for data, section in zip([test_data, train_data],['test', 'train']):
        for item in tqdm(data, desc=f"{section} section linking"):
            db_id = item["db_id"]
            schema = schemas[db_id]
            to_add, validation_info = linking_processor.validate_item(item, schema, section)
            if to_add:
                linking_processor.add_item(item, schema, section, validation_info)

    # save
    linking_processor.save()


def bird_pre_process(bird_dir, testordev, with_evidence=False):
    new_db_path = os.path.join(bird_dir, "database")
    os.makedirs(new_db_path, exist_ok=True)
    
    # Copy train databases
    train_db_dir = os.path.join(bird_dir, 'train/train_databases')
    for db_folder in os.listdir(train_db_dir):
        src = os.path.join(train_db_dir, db_folder)
        dst = os.path.join(new_db_path, db_folder)
        if os.path.isdir(src) and not os.path.exists(dst):
            shutil.copytree(src, dst)
    
    # Copy dev databases
    dev_db_dir = os.path.join(bird_dir, f'{testordev}/{testordev}_databases')
    for db_folder in os.listdir(dev_db_dir):
        src = os.path.join(dev_db_dir, db_folder)
        dst = os.path.join(new_db_path, db_folder)
        if os.path.isdir(src) and not os.path.exists(dst):
            shutil.copytree(src, dst)

    def json_preprocess(data_jsons):
        new_datas = []
        for data_json in data_jsons:
            ### Append the evidence to the question
            if with_evidence and len(data_json["evidence"]) > 0:
                data_json['question'] = (data_json['question'] + " " + data_json["evidence"]).strip()
            question = data_json['question']
            tokens = []
            for token in question.split(' '):
                if len(token) == 0:
                    continue
                if token[-1] in ['?', '.', ':', ';', ','] and len(token) > 1:
                    tokens.extend([token[:-1], token[-1:]])
                else:
                    tokens.append(token)

            raw_tokens = list(jieba.cut(question)) 
            
            for token in raw_tokens:
                token = token.strip()
                if len(token) == 0:
                    continue

                if token[-1] in ['?', '.', ':', ';', ',', '？', '。', '：', '；', '，'] and len(token) > 1:
                    tokens.extend([token[:-1], token[-1:]])
                else:
                    tokens.append(token)

            data_json['question_toks'] = tokens
            data_json['query'] = data_json['SQL']
            new_datas.append(data_json)
        return new_datas

    output_dev = f'{testordev}.json'
    output_train = 'train.json'
    with open(os.path.join(bird_dir, f'{testordev}/{testordev}.json'), encoding='utf-8') as f:
        data_jsons = json.load(f)
        wf = open(os.path.join(bird_dir, output_dev), 'w', encoding='utf-8')
        json.dump(json_preprocess(data_jsons), wf, indent=4, ensure_ascii=False)
    with open(os.path.join(bird_dir, 'train/train.json'), encoding='utf-8') as f:
        data_jsons = json.load(f)
        wf = open(os.path.join(bird_dir, output_train), 'w', encoding='utf-8')
        json.dump(json_preprocess(data_jsons), wf, indent=4, ensure_ascii=False)
    # Copy SQL files
    shutil.copy(os.path.join(bird_dir, f'{testordev}/{testordev}.sql'), bird_dir)
    shutil.copy(os.path.join(bird_dir, 'train/train_gold.sql'), bird_dir)
    tables = []
    with open(os.path.join(bird_dir, f'{testordev}/{testordev}_tables.json'), encoding='utf-8') as f:
        tables.extend(json.load(f))
    with open(os.path.join(bird_dir, 'train/train_tables.json'), encoding='utf-8') as f:
        tables.extend(json.load(f))
    with open(os.path.join(bird_dir, 'tables.json'), 'w', encoding='utf-8') as f:
        json.dump(tables, f, indent=4, ensure_ascii=False)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, default="./dataset/bird/hard")  #TODO
    parser.add_argument("--data_type", type=str, choices=["spider", "bird"], default="bird")
    args = parser.parse_args()
    data_type = args.data_type
    testordev = 'test'

    if data_type == "bird":
        # schema-linking for bird with evidence
        bird_dir =  args.data_dir
        bird_pre_process(bird_dir, testordev, with_evidence=True )
        bird_dev = f'{testordev}.json'
        bird_train = 'train.json'
        bird_table = 'tables.json'
        bird_db = 'database'
        ## do not compute the cv_link since it is time-consuming in the huge database in BIRD
        schema_linking_producer(bird_dev, bird_train, bird_table, bird_db, bird_dir, compute_cv_link=False)


    # if data_type == "spider":
    #     # merge two training split of Spider
    #     spider_dir = args.data_dir
    #     split1 = "train_spider.json"
    #     split2 = "train_others.json"
    #     total_train = []
    #     for item in json.load(open(os.path.join(spider_dir, split1), encoding='utf-8')):
    #         total_train.append(item)
    #     for item in json.load(open(os.path.join(spider_dir, split2), encoding='utf-8')):
    #         total_train.append(item)
    #     with open(os.path.join(spider_dir, 'train_spider_and_others.json'), 'w', encoding='utf-8') as f:
    #         json.dump(total_train, f, ensure_ascii=False)

    #     # schema-linking between questions and databases for Spider
    #     spider_dev = "dev.json"
    #     spider_train = 'train_spider_and_others.json'
    #     spider_table = 'tables.json'
    #     spider_db = 'database'
    #     schema_linking_producer(spider_dev, spider_train, spider_table, spider_db, spider_dir)