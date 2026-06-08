"""Release-safe MCS-SQL reproduction script for SQLite.

Secrets, local paths, and runtime options are read from environment variables.
"""

import json
import random
import sqlite3
import time
import os
import re
import sys
from typing import List, Dict, Tuple, Set, Any, Optional
import numpy as np
import pandas as pd
import requests
import torch
from transformers import AutoTokenizer, AutoModel
import sqlparse
import warnings
warnings.filterwarnings('ignore')
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print('Warning: faiss is not available. Falling back to scipy/numpy similarity search.')

class Config:
    LOCAL_LLM_URL = os.getenv('MCS_SQL_LLM_URL', '')
    LOCAL_LLM_API_KEY = os.getenv('MCS_SQL_LLM_API_KEY', '')
    LOCAL_LLM_HEADERS = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': f'Bearer {LOCAL_LLM_API_KEY}' if LOCAL_LLM_API_KEY else ''}
    LLM_NAME = os.getenv('MCS_SQL_LLM_MODEL', 'qwen-72b-instruct')
    EMBEDDING_MODEL_PATH = os.getenv('MCS_SQL_EMBEDDING_MODEL_PATH', 'BAAI/bge-large-en-v1.5')
    BIRD_DATASET_PATH = os.getenv('MCS_SQL_DATASET_PATH', os.path.join('.', 'dataset'))
    TABLE_LINKING_PROMPTS = int(os.getenv('MCS_SQL_TABLE_LINKING_PROMPTS', '3'))
    COLUMN_LINKING_PROMPTS = int(os.getenv('MCS_SQL_COLUMN_LINKING_PROMPTS', '3'))
    SAMPLES_PER_PROMPT = int(os.getenv('MCS_SQL_SAMPLES_PER_PROMPT', '20'))
    SQL_GENERATION_PROMPTS = int(os.getenv('MCS_SQL_GENERATION_PROMPTS', '5'))
    FEW_SHOT_EXAMPLES = int(os.getenv('MCS_SQL_FEW_SHOT_EXAMPLES', '5'))
    CONFIDENCE_THRESHOLD = float(os.getenv('MCS_SQL_CONFIDENCE_THRESHOLD', '0.2'))
    SQL_TIMEOUT = int(os.getenv('MCS_SQL_TIMEOUT', '60'))
    TEMPERATURE = float(os.getenv('MCS_SQL_TEMPERATURE', '1.0'))
    DB_CACHE_DIR = os.getenv('MCS_SQL_DB_CACHE_DIR', './db_cache')
    SQL_CANDIDATES = int(os.getenv('MCS_SQL_CANDIDATES', '5'))
    TEST_START_INDEX = int(os.getenv('MCS_SQL_TEST_START_INDEX', '0'))
    TEST_END_INDEX = int(os.getenv('MCS_SQL_TEST_END_INDEX', '4'))
    EVALUATE_SQL_PATH = os.getenv('MCS_SQL_EVALUATE_SQL_PATH', 'evaluate_sql.py')

class BIRDDatasetLoader:

    @staticmethod
    def load_train_data(data_path: str=Config.BIRD_DATASET_PATH) -> List[Dict]:
        train_path = os.path.join(data_path, 'train')
        train_file = os.path.join(train_path, 'train.json')
        if not os.path.exists(train_file):
            print(f'Warning: training data file not found {train_file}')
            return []
        with open(train_file, 'r', encoding='utf-8') as f:
            train_data = json.load(f)
        formatted_data = []
        for item in train_data:
            formatted_data.append({'question_id': len(formatted_data), 'question': item.get('question', ''), 'evidence': item.get('evidence', ''), 'difficulty': 'simple', 'db_id': item.get('db_id', ''), 'sql': item.get('SQL', ''), 'query': item.get('SQL', '')})
        print(f'Loaded {len(formatted_data)} training samples')
        return formatted_data

    @staticmethod
    def load_dev_data(data_path: str=Config.BIRD_DATASET_PATH) -> List[Dict]:
        dev_path = os.path.join(data_path, 'dev')
        dev_file = os.path.join(dev_path, 'dev.json')
        if not os.path.exists(dev_file):
            print(f'Warning: dev data file not found {dev_file}')
            return []
        with open(dev_file, 'r', encoding='utf-8') as f:
            dev_data = json.load(f)
        formatted_data = []
        for item in dev_data:
            formatted_data.append({'question_id': item.get('question_id', len(formatted_data)), 'question': item.get('question', ''), 'evidence': item.get('evidence', ''), 'difficulty': item.get('difficulty', 'simple'), 'db_id': item.get('db_id', ''), 'sql': item.get('SQL', ''), 'query': item.get('SQL', '')})
        print(f'Loaded {len(formatted_data)} dev samples')
        return formatted_data

    @staticmethod
    def get_database_path(db_id: str) -> str:
        dev_db_path = os.path.join(Config.BIRD_DATASET_PATH, 'dev', 'dev_databases', db_id, f'{db_id}.sqlite')
        if os.path.exists(dev_db_path):
            return dev_db_path
        train_db_path = os.path.join(Config.BIRD_DATASET_PATH, 'train', 'train_databases', db_id, f'{db_id}.sqlite')
        if os.path.exists(train_db_path):
            return train_db_path
        base_db_path = os.path.join(Config.BIRD_DATASET_PATH, 'database', db_id, f'{db_id}.sqlite')
        if os.path.exists(base_db_path):
            return base_db_path
        os.makedirs(Config.DB_CACHE_DIR, exist_ok=True)
        return os.path.join(Config.DB_CACHE_DIR, f'{db_id}.sqlite')

class DatabaseUtils:

    @staticmethod
    def execute_sql(sql: str, db_path: str, timeout: int=Config.SQL_TIMEOUT) -> Tuple[bool, Any, float]:
        try:
            conn = sqlite3.connect(db_path)
            conn.text_factory = str
            cursor = conn.cursor()
            cursor.execute(f'PRAGMA busy_timeout = {timeout * 1000}')
            start_time = time.time()
            cursor.execute(sql)
            result = cursor.fetchall()
            execution_time = time.time() - start_time
            conn.close()
            return (True, result, execution_time)
        except Exception as e:
            return (False, str(e), 0.0)

    @staticmethod
    def get_schema(db_path: str) -> Dict[str, List[str]]:
        if not os.path.exists(db_path):
            print(f'Warning: database file does not exist {db_path}')
            return {}
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            schema = {}
            for table in tables:
                cursor.execute(f'PRAGMA table_info({table})')
                columns = [row[1] for row in cursor.fetchall()]
                schema[table] = columns
            conn.close()
            return schema
        except Exception as e:
            print(f'Failed to retrieve database schema: {e}')
            return {}

    @staticmethod
    def get_sample_data(db_path: str, table: str, limit: int=3) -> List[Tuple]:
        if not os.path.exists(db_path):
            return []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(f'SELECT * FROM {table} LIMIT {limit}')
            data = cursor.fetchall()
            conn.close()
            return data
        except:
            return []

class LocalEmbeddingModel:

    def __init__(self, model_path: str=Config.EMBEDDING_MODEL_PATH):
        print(f'Loading embedding model: {model_path}')
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path)
        self.model.eval()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

    def get_embedding(self, text: str) -> np.ndarray:
        try:
            inputs = self.tokenizer(text, return_tensors='pt', max_length=512, truncation=True, padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model(**inputs)
                embeddings = outputs.last_hidden_state.mean(dim=1)
            return embeddings.cpu().numpy()[0]
        except Exception as e:
            print(f'Embedding generation failed: {e}')
            return np.random.randn(768)

class LocalLLMClient:

    def __init__(self):
        self.url = Config.LOCAL_LLM_URL
        self.headers = Config.LOCAL_LLM_HEADERS
        self.embedding_model = LocalEmbeddingModel()

    def health_check(self) -> bool:
        try:
            test_prompt = 'health check'
            response = requests.post(self.url, headers=self.headers, json={'model': Config.LLM_NAME, 'messages': [{'role': 'user', 'content': test_prompt}], 'temperature': 0.1, 'max_tokens': 10, 'stream': False}, timeout=30)
            return response.status_code == 200
        except Exception as e:
            print(f'LLM health check failed: {e}')
            return False

    def get_embedding(self, text: str) -> np.ndarray:
        return self.embedding_model.get_embedding(text)

    def health_check(self) -> bool:
        try:
            test_prompt = 'health check'
            response = requests.post(self.url, headers=self.headers, json={'model': Config.LLM_NAME, 'messages': [{'role': 'user', 'content': test_prompt}], 'temperature': 0.1, 'max_tokens': 10, 'stream': False}, timeout=30)
            return response.status_code == 200
        except:
            return False

    def call_llm(self, prompt: str, n: int=1, temperature: float=Config.TEMPERATURE) -> List[str]:
        try:
            responses = []
            for i in range(n):
                data = {'model': Config.LLM_NAME, 'messages': [{'role': 'system', 'content': 'You are a professional SQL assistant specialized in converting natural language questions into SQL queries.'}, {'role': 'user', 'content': prompt}], 'temperature': temperature, 'stream': False}
                response = requests.post(self.url, headers=self.headers, json=data, timeout=200)
                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content']
                        responses.append(content)
                    else:
                        print(f'Unexpected response format: {result}')
                        responses.append(f'Fallback response {i + 1}')
                else:
                    print(f'API call failed: {response.status_code}')
                    responses.append(f'Fallback response {i + 1}')
                if i < n - 1:
                    time.sleep(0.5)
            return responses
        except Exception as e:
            print(f'LLM call failed: {e}')
            return [f'Fallback response {i + 1}: {prompt[:50]}...' for i in range(n)]

    def extract_json_from_response(self, response: str) -> Dict:
        try:
            json_pattern = '```json\\s*(.*?)\\s*```'
            match = re.search(json_pattern, response, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = response
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                brace_match = re.search('\\{.*\\}', response, re.DOTALL)
                if brace_match:
                    json_str = brace_match.group(0)
                    return json.loads(json_str)
            except:
                pass
            return {}

class SchemaLinker:

    def __init__(self, llm_client: LocalLLMClient):
        self.llm = llm_client

    def _shuffle_schema(self, schema: Dict[str, List[str]]) -> List[str]:
        tables = list(schema.keys())
        random.shuffle(tables)
        shuffled_schema = []
        for table in tables:
            columns = schema[table].copy()
            random.shuffle(columns)
            shuffled_schema.append(f"# {table} ({', '.join(columns)})")
        return shuffled_schema

    def table_linking(self, schema: Dict[str, List[str]], question: str, evidence: str='') -> Set[str]:
        if not schema:
            return set()
        all_tables = set()
        for i in range(Config.TABLE_LINKING_PROMPTS):
            shuffled_schema = self._shuffle_schema(schema)
            schema_text = '\n'.join(shuffled_schema)
            prompt = f'\nGiven a database schema, a question, and evidence, identify the tables required to translate the question into SQL.\n\nDatabase schema:\n{schema_text}\n\nQuestion:{question}\n\nEvidence:{evidence}\n\nSelect the required tables and briefly explain the rationale. Your response must strictly follow this JSON format:\n{{\n  "reasoning": "Rationale for selecting each table",\n  "tables": ["table1", "table2"]\n}}\n\nReturn JSON only. Do not include any other text.\n'
            responses = self.llm.call_llm(prompt, n=Config.SAMPLES_PER_PROMPT)
            for response in responses:
                try:
                    result = self.llm.extract_json_from_response(response)
                    tables = result.get('tables', [])
                    valid_tables = [t for t in tables if t in schema]
                    all_tables.update(valid_tables)
                except Exception as e:
                    print(f'Failed to parse table-linking response: {e}')
                    continue
        return all_tables

    def column_linking(self, selected_tables: Set[str], full_schema: Dict[str, List[str]], question: str, evidence: str='') -> Set[str]:
        if not selected_tables:
            return set()
        filtered_schema = {table: full_schema[table] for table in selected_tables if table in full_schema}
        if not filtered_schema:
            return set()
        all_columns = set()
        for i in range(Config.COLUMN_LINKING_PROMPTS):
            shuffled_schema = self._shuffle_schema(filtered_schema)
            schema_text = '\n'.join(shuffled_schema)
            prompt = f'\nGiven a database schema, a question, and evidence, identify the columns required to translate the question into SQL.\n\nDatabase schema:\n{schema_text}\n\nQuestion:{question}\n\nEvidence:{evidence}\n\nSelect the required columns and briefly explain the rationale. Your response must strictly follow this JSON format:\n{{\n  "reasoning": "Rationale for selecting each column",\n  "columns": ["table1.column1", "table2.column2"]\n}}\n\nNote: column names must use the table.column format.\nReturn JSON only. Do not include any other text.\n'
            responses = self.llm.call_llm(prompt, n=Config.SAMPLES_PER_PROMPT)
            for response in responses:
                try:
                    result = self.llm.extract_json_from_response(response)
                    columns = result.get('columns', [])
                    for col in columns:
                        if '.' in col:
                            table, column_name = col.split('.', 1)
                            if table in selected_tables:
                                all_columns.add(col)
                except Exception as e:
                    print(f'Failed to parse column-linking response: {e}')
                    continue
        return all_columns

class FewShotSelector:

    def __init__(self, llm_client: LocalLLMClient, training_data: List[Dict]):
        self.llm = llm_client
        self.training_data = training_data
        self.question_embeddings = None
        self.masked_question_embeddings = None
        self._precompute_embeddings()

    def _precompute_embeddings(self):
        if not self.training_data:
            print('Warning: training data is empty')
            return
        print('Precomputing training-data embeddings...')
        question_texts = [item['question'] for item in self.training_data]
        self.question_embeddings = []
        for i, text in enumerate(question_texts):
            if i % 100 == 0:
                print(f'  Processing question {i}/{len(question_texts)}')
            emb = self.llm.get_embedding(text)
            self.question_embeddings.append(emb)
        self.question_embeddings = np.array(self.question_embeddings)
        print('Computing masked-question embeddings...')
        self.masked_question_embeddings = []
        for i, item in enumerate(self.training_data):
            if i % 100 == 0:
                print(f'  Processing masked question {i}/{len(self.training_data)}')
            masked_question = self._mask_question(item['question'])
            emb = self.llm.get_embedding(masked_question)
            self.masked_question_embeddings.append(emb)
        self.masked_question_embeddings = np.array(self.masked_question_embeddings)
        print('Embedding precomputation completed')

    def _mask_question(self, question: str) -> str:
        sql_keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'TABLE', 'DATABASE', 'INDEX', 'VIEW', 'PROCEDURE']
        masked = question
        for keyword in sql_keywords:
            pattern = '\\b' + re.escape(keyword) + '\\b'
            masked = re.sub(pattern, '[MASK]', masked, flags=re.IGNORECASE)
        masked = re.sub('\\d+', '[NUM]', masked)
        masked = re.sub('"[^"]*"', '[STR]', masked)
        masked = re.sub("'[^']*'", '[STR]', masked)
        words = masked.split()
        for i, word in enumerate(words):
            if word not in ['[MASK]', '[NUM]', '[STR]']:
                if re.match('^[A-Z][a-zA-Z0-9_]*$', word) or '_' in word:
                    words[i] = '[ID]'
        return ' '.join(words)

    def select_by_question_similarity(self, question: str, k: int=Config.FEW_SHOT_EXAMPLES) -> List[Dict]:
        if self.question_embeddings is None or len(self.question_embeddings) == 0:
            print('Warning: question embeddings have not been computed')
            return random.sample(self.training_data, min(k, len(self.training_data)))
        query_embedding = self.llm.get_embedding(question).reshape(1, -1)
        if FAISS_AVAILABLE:
            dimension = self.question_embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            index.add(self.question_embeddings)
            k_search = min(k, len(self.training_data))
            distances, indices = index.search(query_embedding, k_search)
        else:
            distances = np.linalg.norm(self.question_embeddings - query_embedding, axis=1)
            indices = np.argsort(distances)[:k]
        selected = []
        for idx in indices:
            if idx < len(self.training_data):
                selected.append(self.training_data[idx])
        return selected

    def select_by_masked_similarity(self, question: str, k: int=Config.FEW_SHOT_EXAMPLES) -> List[Dict]:
        if self.masked_question_embeddings is None or len(self.masked_question_embeddings) == 0:
            print('Warning: masked-question embeddings have not been computed')
            return random.sample(self.training_data, min(k, len(self.training_data)))
        masked_question = self._mask_question(question)
        query_embedding = self.llm.get_embedding(masked_question).reshape(1, -1)
        if FAISS_AVAILABLE:
            dimension = self.masked_question_embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            index.add(self.masked_question_embeddings)
            k_search = min(k, len(self.training_data))
            distances, indices = index.search(query_embedding, k_search)
        else:
            distances = np.linalg.norm(self.masked_question_embeddings - query_embedding, axis=1)
            indices = np.argsort(distances)[:k]
        selected = []
        for idx in indices:
            if idx < len(self.training_data):
                selected.append(self.training_data[idx])
        return selected

    def generate_prompts(self, question: str, schema: Dict, evidence: str='') -> List[str]:
        prompts = []
        examples1 = self.select_by_question_similarity(question)
        prompt1 = self._build_sql_generation_prompt(examples1, question, schema, evidence)
        prompts.append(prompt1)
        examples2 = self.select_by_masked_similarity(question)
        prompt2 = self._build_sql_generation_prompt(examples2, question, schema, evidence)
        prompts.append(prompt2)
        for i in range(3):
            mixed_examples = random.sample(self.training_data, min(10, len(self.training_data)))
            prompt = self._build_sql_generation_prompt(mixed_examples, question, schema, evidence)
            prompts.append(prompt)
        return prompts[:Config.SQL_GENERATION_PROMPTS]

    def _build_sql_generation_prompt(self, examples: List[Dict], question: str, schema: Dict, evidence: str='') -> str:
        prompt_parts = []
        if examples:
            prompt_parts.append('Here are several correct question-SQL examples:')
            for i, example in enumerate(examples[:3]):
                prompt_parts.append(f'Example {i + 1}:')
                prompt_parts.append(f"Question: {example.get('question', '')}")
                if 'sql' in example:
                    prompt_parts.append(f"SQL: {example['sql']}")
                elif 'query' in example:
                    prompt_parts.append(f"SQL: {example['query']}")
                prompt_parts.append('')
        if schema:
            prompt_parts.append('Database schema:')
            for table, columns in schema.items():
                prompt_parts.append(f"Table {table}: {', '.join(columns)}")
            prompt_parts.append('')
        prompt_parts.append(f'Question:{question}')
        if evidence:
            prompt_parts.append(f'Evidence:{evidence}')
        prompt_parts.append('')
        prompt_parts.append('\nGenerate a correct SQLite SQL query for the question above. Provide detailed reasoning steps.\nYour response must strictly follow this JSON format:\n{\n  "reasoning": "Reasoning steps for generating the SQL, including table, column, and condition selection",\n  "sql": "Generated SQL query"\n}\n\nReturn JSON only. Do not include any other text.\n')
        return '\n'.join(prompt_parts)

class SQLGenerator:

    def __init__(self, llm_client: LocalLLMClient, few_shot_selector: FewShotSelector):
        self.llm = llm_client
        self.selector = few_shot_selector

    def generate_candidates(self, question: str, schema: Dict, evidence: str='', max_candidates: int=Config.SQL_CANDIDATES) -> List[str]:
        all_candidates = []
        prompts = self.selector.generate_prompts(question, schema, evidence)
        print(f'  Generated {len(prompts)} prompts')
        samples_per_prompt = max(1, max_candidates // len(prompts))
        remaining_candidates = max_candidates
        for i, prompt in enumerate(prompts):
            if remaining_candidates <= 0:
                break
            print(f'  Processing prompt {i + 1}/{len(prompts)}')
            current_samples = min(samples_per_prompt, remaining_candidates)
            responses = self.llm.call_llm(prompt, n=current_samples)
            for response in responses:
                if remaining_candidates <= 0:
                    break
                try:
                    result = self.llm.extract_json_from_response(response)
                    sql = result.get('sql', '')
                    if sql:
                        sql = sql.strip()
                        if sql.endswith(';'):
                            sql = sql[:-1]
                        try:
                            sqlparse.parse(sql)
                            all_candidates.append(sql)
                            remaining_candidates -= 1
                        except:
                            print(f'Invalid SQL syntax: {sql[:50]}...')
                except Exception as e:
                    print(f'Failed to parse SQL response: {e}')
                    continue
        print(f'  Generated {len(all_candidates)} SQL candidates')
        return all_candidates

class SQLSelector:

    def __init__(self, llm_client):
        self.llm = llm_client

    @staticmethod
    def filter_candidates(candidates: List[str], db_path: str) -> List[Tuple[str, float, float]]:
        if not candidates or not os.path.exists(db_path):
            return []
        print(f'  Executing {len(candidates)} candidate SQL queries...')
        execution_results = []
        for i, sql in enumerate(candidates):
            if i % 10 == 0:
                print(f'    Executing candidate {i}/{len(candidates)} SQL queries')
            success, result, exec_time = DatabaseUtils.execute_sql(sql, db_path)
            if success:
                result_str = str(sorted([str(row) for row in result]))
                execution_results.append({'sql': sql, 'result': result_str, 'time': exec_time, 'success': True})
            else:
                execution_results.append({'sql': sql, 'result': None, 'time': 0.0, 'success': False})
        valid_results = [r for r in execution_results if r['success']]
        print(f'  Number of valid SQL queries: {len(valid_results)}')
        if not valid_results:
            return []
        result_groups = {}
        for item in valid_results:
            result_str = item['result']
            if result_str not in result_groups:
                result_groups[result_str] = []
            result_groups[result_str].append(item)
        filtered_candidates = []
        total_valid = len(valid_results)
        for result_str, group in result_groups.items():
            group_size = len(group)
            confidence = group_size / total_valid
            fastest = min(group, key=lambda x: x['time'])
            if confidence >= Config.CONFIDENCE_THRESHOLD:
                filtered_candidates.append((fastest['sql'], confidence, fastest['time']))
        filtered_candidates.sort(key=lambda x: x[1], reverse=True)
        print(f'  Filtered candidates remaining: {len(filtered_candidates)} candidates')
        return filtered_candidates

    def multiple_choice_selection(self, candidates: List[Tuple[str, float, float]], question: str, schema: Dict, evidence: str='') -> str:
        if not candidates:
            return ''
        if len(candidates) == 1:
            return candidates[0][0]
        prompt = self._build_mcs_prompt(candidates, question, schema, evidence)
        print('  Running multiple-choice selection...')
        responses = self.llm.call_llm(prompt, n=Config.SAMPLES_PER_PROMPT)
        sql_votes = {}
        for response in responses:
            try:
                result = self.llm.extract_json_from_response(response)
                selected_sql = result.get('sql', '')
                if selected_sql:
                    for candidate_sql, _, _ in candidates:
                        if candidate_sql.strip() == selected_sql.strip():
                            if candidate_sql in sql_votes:
                                sql_votes[candidate_sql] += 1
                            else:
                                sql_votes[candidate_sql] = 1
                            break
            except Exception as e:
                print(f'Failed to parse MCS response: {e}')
                continue
        if not sql_votes:
            print('  Warning: MCS voting failed. Returning the highest-confidence candidate.')
            return candidates[0][0]
        final_sql = max(sql_votes.items(), key=lambda x: x[1])[0]
        print(f'  MCS selection completed. Highest vote count: {sql_votes[final_sql]}')
        return final_sql

    def _build_mcs_prompt(self, candidates: List[Tuple[str, float, float]], question: str, schema: Dict, evidence: str) -> str:
        prompt_parts = []
        prompt_parts.append('Given a database schema, a question, evidence, and multiple candidate SQL queries, select the most accurate SQL query.')
        if schema:
            prompt_parts.append('\nDatabase schema:')
            for table, columns in schema.items():
                prompt_parts.append(f"Table {table}: {', '.join(columns)}")
        prompt_parts.append(f'\nQuestion:{question}')
        if evidence:
            prompt_parts.append(f'Evidence:{evidence}')
        prompt_parts.append('\nCandidate SQL queries:')
        for i, (sql, confidence, _) in enumerate(candidates[:5]):
            prompt_parts.append(f'{i + 1}. {sql}')
            prompt_parts.append(f'   Confidence: {confidence:.2f}')
        prompt_parts.append('\n\nEvaluate each candidate SQL query using the following checklist:\n1. The SQL should accurately represent the question intent.\n2. The SQL should correctly use the given evidence.\n3. The SELECT clause should not include extra columns that are not requested by the question.\n4. Operations should be correctly applied according to column types.\n5. The SQL syntax should be valid.\n')
        prompt_parts.append('\nSelect the most accurate SQL query and explain your choice in detail.\nYour response must strictly follow this JSON format:\n{\n  "reasoning": "Reasoning steps for selecting the SQL, including evaluation against the checklist",\n  "sql": "Selected SQL query"\n}\n\nReturn JSON only. Do not include any other text.\n')
        return '\n'.join(prompt_parts)

class MCS_SQL_Pipeline:

    def __init__(self, training_data: List[Dict]):
        print('Initializing the MCS-SQL pipeline...')
        self.llm = LocalLLMClient()
        self.schema_linker = SchemaLinker(self.llm)
        self.few_shot_selector = FewShotSelector(self.llm, training_data)
        self.sql_generator = SQLGenerator(self.llm, self.few_shot_selector)
        self.sql_selector = SQLSelector(self.llm)

    def process(self, question: str, db_id: str, evidence: str='') -> Dict[str, Any]:
        print(f"\n{'=' * 60}")
        print(f'Processing question: {question}')
        if evidence:
            print(f'Evidence: {evidence}')
        db_path = BIRDDatasetLoader.get_database_path(db_id)
        if not os.path.exists(db_path):
            print(f'Error: database file does not exist {db_path}')
            return {'error': f'Database file does not exist: {db_path}'}
        print('\nStep 1: Retrieve database schema...')
        full_schema = DatabaseUtils.get_schema(db_path)
        if not full_schema:
            print('Error: failed to retrieve database schema')
            return {'error': 'Failed to retrieve database schema'}
        print(f'  Database contains {len(full_schema)} tables')
        print('\nStep 2: Schema linking...')
        selected_tables = self.schema_linker.table_linking(full_schema, question, evidence)
        print(f'  Selected tables ({len(selected_tables)}): {list(selected_tables)[:5]}...')
        selected_columns = self.schema_linker.column_linking(selected_tables, full_schema, question, evidence)
        print(f'  Selected columns ({len(selected_columns)}): {list(selected_columns)[:5]}...')
        filtered_schema = {}
        for column in selected_columns:
            if '.' in column:
                table, col = column.split('.', 1)
                if table in selected_tables:
                    if table not in filtered_schema:
                        filtered_schema[table] = []
                    if col not in filtered_schema[table]:
                        filtered_schema[table].append(col)
        if not filtered_schema:
            print('Warning: schema linking did not select any table or column. Using the full schema.')
            filtered_schema = full_schema
        print(f'  Filtered schema: {len(filtered_schema)} tables')
        print('\nStep 3: Generate SQL candidates...')
        sql_candidates = self.sql_generator.generate_candidates(question, filtered_schema, evidence)
        print('\nStep 4: Candidate filtering...')
        filtered_candidates = self.sql_selector.filter_candidates(sql_candidates, db_path)
        print('\nStep 5: Multiple-choice selection...')
        if filtered_candidates:
            final_sql = self.sql_selector.multiple_choice_selection(filtered_candidates, question, filtered_schema, evidence)
            print(f'  Final SQL: {final_sql[:100]}...')
        else:
            final_sql = ''
            print('  Warning: no valid SQL candidate was found')
        if final_sql:
            success, result, exec_time = DatabaseUtils.execute_sql(final_sql, db_path)
            return {'question': question, 'evidence': evidence, 'db_id': db_id, 'final_sql': final_sql, 'execution_success': success, 'execution_result': result if success else str(result), 'execution_time': exec_time, 'num_candidates_generated': len(sql_candidates), 'num_candidates_filtered': len(filtered_candidates), 'selected_tables': list(selected_tables), 'selected_columns': list(selected_columns)}
        else:
            return {'question': question, 'evidence': evidence, 'db_id': db_id, 'final_sql': '', 'error': 'Failed to generate a valid SQL query', 'num_candidates_generated': len(sql_candidates), 'num_candidates_filtered': len(filtered_candidates)}

class BatchTester:

    @staticmethod
    def run_test(pipeline: MCS_SQL_Pipeline, test_data: List[Dict], start_index: int=Config.TEST_START_INDEX, end_index: int=Config.TEST_END_INDEX) -> List[Dict]:
        results = []
        start_index = max(0, start_index)
        end_index = min(len(test_data), end_index)
        if start_index >= end_index:
            print(f'Warning: start index {start_index} is greater than or equal to end index {end_index}')
            return results
        test_subset = test_data[start_index:end_index]
        total_samples = len(test_subset)
        for i, test_item in enumerate(test_subset):
            global_index = start_index + i
            print(f"\n{'#' * 60}")
            print(f'Test sample {i + 1}/{total_samples} (global index: {global_index})')
            print(f"Question ID: {test_item.get('question_id', 'N/A')}")
            question = test_item.get('question', '')
            evidence = test_item.get('evidence', '')
            db_id = test_item.get('db_id', '')
            if not question or not db_id:
                print('Warning: sample is missing question or database ID')
                continue
            result = pipeline.process(question, db_id, evidence)
            result['global_index'] = global_index
            results.append(result)
            if (i + 1) % 5 == 0:
                BatchTester.save_results(results, f'results_batch_{global_index + 1}.json')
        return results

    @staticmethod
    def save_results(results: List[Dict], filename: str):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f'\nResults saved to {filename}')

    @staticmethod
    def evaluate_results(results: List[Dict], test_data: List[Dict]) -> Dict[str, Any]:
        if not results:
            return {'error': 'No results to evaluate'}
        total = len(results)
        successful_executions = sum((1 for r in results if r.get('execution_success', False)))
        generated_sql = sum((1 for r in results if r.get('final_sql', '')))
        metrics = {'total_samples': total, 'sql_generated_rate': generated_sql / total if total > 0 else 0, 'execution_success_rate': successful_executions / total if total > 0 else 0, 'avg_candidates_generated': np.mean([r.get('num_candidates_generated', 0) for r in results]), 'avg_candidates_filtered': np.mean([r.get('num_candidates_filtered', 0) for r in results])}
        return metrics

def main():
    print('Checking LLM service connection...')
    llm = LocalLLMClient()
    if llm.health_check():
        print('✅ LLM service is reachable')
    else:
        print('⚠️  LLM service connection failed. Fallback responses will be used.')
    'Main function'
    print('MCS-SQL reproduction framework')
    print('=' * 60)
    print('\n1. Load training data...')
    train_data = BIRDDatasetLoader.load_train_data()
    print(f'   Loaded {len(train_data)} training samples')
    print('\n2. Load test data...')
    test_data = BIRDDatasetLoader.load_dev_data()
    print(f'   Loaded {len(test_data)} test samples')
    if not train_data:
        print('Warning: training data is empty. Using test data as training data.')
        train_data = test_data[:100]
    print('\n3. Create the MCS-SQL pipeline...')
    pipeline = MCS_SQL_Pipeline(train_data)
    print('\n4. Run a single test...')
    if test_data:
        sample = test_data[0]
        question = sample.get('question', 'List all employees')
        evidence = sample.get('evidence', '')
        db_id = sample.get('db_id', '')
        if db_id:
            print(f'   Test question: {question}')
            result = pipeline.process(question, db_id, evidence)
            print(f'\n   Result:')
            print(f"   Generated SQL: {result.get('final_sql', 'None')}")
            print(f"   Execution succeeded: {result.get('execution_success', False)}")
            if result.get('execution_success'):
                print(f"   Execution time: {result.get('execution_time', 0):.2f}s")
        else:
            print('   Test sample is missing database ID')
    print('\n5. Run batch tests automatically...')
    start_index = Config.TEST_START_INDEX
    end_index = Config.TEST_END_INDEX
    print(f'   Testing samples from {start_index} to {end_index}')
    results = BatchTester.run_test(pipeline, test_data, start_index, end_index)
    metrics = BatchTester.evaluate_results(results, test_data[start_index:end_index])
    print(f'\nInternal evaluation results:')
    for key, value in metrics.items():
        print(f'   {key}: {value}')
    results_file = 'final_results.json'
    BatchTester.save_results(results, results_file)
    print('\n6. Evaluate generated SQL results using evaluate_sql.py...')
    if os.path.exists(Config.EVALUATE_SQL_PATH):
        try:
            eval_predictions = []
            for result in results:
                if 'final_sql' in result and result['final_sql']:
                    eval_predictions.append({'question_id': result.get('global_index', 0), 'db_id': result['db_id'], 'predicted_sql': result['final_sql']})
            pred_file = 'predictions.json'
            with open(pred_file, 'w', encoding='utf-8') as f:
                json.dump(eval_predictions, f, ensure_ascii=False, indent=2)
            print(f'   Prediction results saved to {pred_file}')
            print(f'   Calling {Config.EVALUATE_SQL_PATH} for evaluation...')
            import subprocess
            eval_result = subprocess.run([sys.executable, '-X', 'utf8', Config.EVALUATE_SQL_PATH, '--predictions', pred_file, '--ground_truth', os.path.join(Config.BIRD_DATASET_PATH, 'dev', 'dev.json'), '--db_path', os.path.join(Config.BIRD_DATASET_PATH, 'dev', 'dev_databases')], capture_output=True, text=True, encoding='utf-8', cwd=os.path.dirname(Config.EVALUATE_SQL_PATH))
            print('\n   Evaluation results:')
            print('   ' + '=' * 50)
            print(eval_result.stdout)
            if eval_result.stderr:
                print('   Error message:')
                print('   ' + '=' * 50)
                print(eval_result.stderr)
            eval_output_file = 'evaluation_results.txt'
            with open(eval_output_file, 'w', encoding='utf-8') as f:
                f.write('=' * 60 + '\n')
                f.write('SQL evaluation report\n')
                f.write('=' * 60 + '\n')
                f.write(f"Evaluation time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f'Prediction file: {pred_file}\n')
                f.write(f"Question file: {os.path.join(Config.BIRD_DATASET_PATH, 'dev', 'dev.json')}\n")
                f.write(f"Database directory: {os.path.join(Config.BIRD_DATASET_PATH, 'dev', 'dev_databases')}\n")
                f.write('=' * 60 + '\n')
                f.write(f'Total queries: {len(results)}\n')
                f.write('=' * 60 + '\n\n')
                f.write(eval_result.stdout)
                if eval_result.stderr:
                    f.write('\nError message:\n')
                    f.write('=' * 50 + '\n')
                    f.write(eval_result.stderr)
            print(f'\n   Evaluation results saved to: {eval_output_file}')
        except Exception as e:
            print(f'   An error occurred during evaluation: {e}')
            eval_output_file = 'evaluation_results.txt'
            with open(eval_output_file, 'w', encoding='utf-8') as f:
                f.write('=' * 60 + '\n')
                f.write('SQL evaluation report\n')
                f.write('=' * 60 + '\n')
                f.write(f"Evaluation time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f'Prediction file: {pred_file}\n')
                f.write(f"Question file: {os.path.join(Config.BIRD_DATASET_PATH, 'dev', 'dev.json')}\n")
                f.write(f"Database directory: {os.path.join(Config.BIRD_DATASET_PATH, 'dev', 'dev_databases')}\n")
                f.write('=' * 60 + '\n\n')
                f.write(f'An error occurred during evaluation: {e}\n')
            print(f'   Basic evaluation results saved to: {eval_output_file}')
    else:
        print(f'   Warning: evaluation script not found {Config.EVALUATE_SQL_PATH}')
        eval_output_file = 'evaluation_results.txt'
        with open(eval_output_file, 'w', encoding='utf-8') as f:
            f.write('=' * 60 + '\n')
            f.write('SQL evaluation report\n')
            f.write('=' * 60 + '\n')
            f.write(f"Evaluation time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f'Evaluation script not found: {Config.EVALUATE_SQL_PATH}\n')
        print(f'   Basic evaluation information saved to: {eval_output_file}')
    print('\nProgram completed!')

def quick_test():
    print('Quick test for the MCS-SQL pipeline...')
    example_data = [{'question': 'Show all employee names and salaries', 'sql': 'SELECT name, salary FROM employees', 'db_id': 'example_db'}, {'question': 'Calculate the average salary for each department', 'sql': 'SELECT department, AVG(salary) FROM employees GROUP BY department', 'db_id': 'example_db'}, {'question': 'Find the employee with the highest salary', 'sql': 'SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 1', 'db_id': 'example_db'}]
    pipeline = MCS_SQL_Pipeline(example_data)
    test_question = 'List all employees in the sales department'
    test_db_id = 'example_db'
    result = pipeline.process(test_question, test_db_id)
    print(f'Test question: {test_question}')
    print(f"Generated SQL: {result.get('final_sql', 'None')}")
    print(f"Execution succeeded: {result.get('execution_success', False)}")
if __name__ == '__main__':
    os.makedirs(Config.DB_CACHE_DIR, exist_ok=True)
    main()
