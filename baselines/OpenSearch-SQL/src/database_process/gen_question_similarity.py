import argparse
import json
import os
import torch
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main(args):
    # 1. 路径推导
    # 按照你的目录结构，train 和 dev 应该在 data_preprocess 目录下
    train_json = os.path.join(args.db_root_directory, "data_preprocess", "train.json")
    dev_json = os.path.join(args.db_root_directory, "data_preprocess", "dev.json")
    output_path = os.path.join(args.db_root_directory, "skeletonsql_dev.json")

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    # 2. 加载 BGE 模型
    logging.info(f"正在加载 BGE 模型: {args.bert_model}")
    model = SentenceTransformer(args.bert_model, device=device)

    # 3. 读取数据
    logging.info("加载数据中...")
    with open(train_json, 'r', encoding='utf-8') as f:
        train_data = json.load(f)
    with open(dev_json, 'r', encoding='utf-8') as f:
        dev_data = json.load(f)

    train_questions = [item['question'] for item in train_data]
    dev_questions = [item['question'] for item in dev_data]

    # 4. 生成向量
    logging.info("正在对题目进行向量编码...")
    train_embs = model.encode(train_questions, convert_to_tensor=True, device=device, batch_size=4)
    dev_embs = model.encode(dev_questions, convert_to_tensor=True, device=device, batch_size=4)

    # 5. 执行检索
    logging.info(f"执行 DAIL-SQL 相似度匹配 (K={args.k_shot})...")
    output_questions = []

    for i, dev_emb in enumerate(tqdm(dev_embs, desc="匹配进度")):
        scores = torch.nn.functional.cosine_similarity(dev_emb.unsqueeze(0), train_embs)
        top_k_val, top_k_idx = torch.topk(scores, args.k_shot)
        
        prompt_parts = []
        for idx in top_k_idx.cpu().numpy():
            prompt_parts.append(f"/* Answer the following: {train_questions[idx]} */")
        
        # 附上当前 Dev 题目
        prompt_parts.append(f"/* Answer the following: {dev_questions[i]} */")
        full_prompt = "\n".join(prompt_parts)
        
        output_questions.append({
            "prompt": full_prompt,
            "db_id": dev_data[i]["db_id"],
            "n_examples": args.k_shot
        })

    # 6. 保存结果
    final_output = {"questions": output_questions, "costs": 0}
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)

    logging.info(f"✅ 成功生成检索文件: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Similarity Index (DAIL-SQL Style)")
    parser.add_argument('--db_root_directory', type=str, required=True, help='Root directory (e.g., Bird/easy)')
    parser.add_argument('--bert_model', type=str, required=True, help='Path to BGE model')
    parser.add_argument('--k_shot', type=int, default=5, help='Number of few-shot examples')
    
    args = parser.parse_args()
    main(args)