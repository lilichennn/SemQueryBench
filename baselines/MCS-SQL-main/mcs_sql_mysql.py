"""Release-safe MCS-SQL reproduction script for MySQL.

Secrets, local paths, and runtime options are read from environment variables.
"""

import json
import random
import pymysql
import time
import os
import re
import sys
from decimal import Decimal
from typing import List, Dict, Tuple, Set, Any, Optional
import numpy as np
import requests
import torch
from transformers import AutoTokenizer, AutoModel
import sqlparse
import warnings
warnings.filterwarnings('ignore')
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print('Warning: faiss is not available. Falling back to scipy/numpy similarity search.')

class Config:
    BASE_DIR = os.getenv('MCS_SQL_BASE_DIR', '.')
    DATASET_TYPE = os.getenv('MCS_SQL_DATASET_TYPE', 'mid')
    RUN_DIR = os.getenv('MCS_SQL_RUN_DIR', os.path.join(BASE_DIR, 'method_SOTA', 'MCS-SQL-main', f'run_{DATASET_TYPE}-3'))
    EMBEDDING_MODEL_PATH = os.getenv('MCS_SQL_EMBEDDING_MODEL_PATH', 'BAAI/bge-large-en-v1.5')
    MYSQL_HOST = os.getenv('MCS_SQL_MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MCS_SQL_MYSQL_PORT', '3306'))
    MYSQL_USER = os.getenv('MCS_SQL_MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MCS_SQL_MYSQL_PASSWORD', '')
    LLM_URL = os.getenv('MCS_SQL_LLM_URL', '')
    LLM_API_KEY = os.getenv('MCS_SQL_LLM_API_KEY', '')
    LLM_HEADERS = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': f'Bearer {LLM_API_KEY}' if LLM_API_KEY else ''}
    LLM_NAME = os.getenv('MCS_SQL_LLM_MODEL', 'qwen-max')
    BIRD_DATASET_PATH = os.getenv('MCS_SQL_DATASET_PATH', os.path.join(BASE_DIR, 'dataset', DATASET_TYPE))
    EVALUATE_SQL_PATH = os.getenv('MCS_SQL_EVALUATE_SQL_PATH', os.path.join(BASE_DIR, 'method_SOTA', 'MCS-SQL-main', 'evaluate_sql.py'))
    TABLE_LINKING_PROMPTS = int(os.getenv('MCS_SQL_TABLE_LINKING_PROMPTS', '1'))
    COLUMN_LINKING_PROMPTS = int(os.getenv('MCS_SQL_COLUMN_LINKING_PROMPTS', '1'))
    SAMPLES_PER_PROMPT = int(os.getenv('MCS_SQL_SAMPLES_PER_PROMPT', '1'))
    SQL_GENERATION_PROMPTS = int(os.getenv('MCS_SQL_GENERATION_PROMPTS', '1'))
    FEW_SHOT_EXAMPLES = int(os.getenv('MCS_SQL_FEW_SHOT_EXAMPLES', '5'))
    CONFIDENCE_THRESHOLD = float(os.getenv('MCS_SQL_CONFIDENCE_THRESHOLD', '0.2'))
    SQL_TIMEOUT = int(os.getenv('MCS_SQL_TIMEOUT', '60'))
    TEMPERATURE = float(os.getenv('MCS_SQL_TEMPERATURE', '1.0'))
    DB_CACHE_DIR = os.getenv('MCS_SQL_DB_CACHE_DIR', './db_cache')
    SQL_CANDIDATES = int(os.getenv('MCS_SQL_CANDIDATES', '5'))
    DEBUG_MODE = os.getenv('MCS_SQL_DEBUG_MODE', 'off')
    TEST_START_INDEX = int(os.getenv('MCS_SQL_TEST_START_INDEX', '0'))
    TEST_END_INDEX = int(os.getenv('MCS_SQL_TEST_END_INDEX', '1'))

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')

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
    def get_db_name(db_id: str) -> str:
        database_name = db_id
        return database_name

class DatabaseUtils:

    @staticmethod
    def get_connection(db_name: str):
        return pymysql.connect(host=Config.MYSQL_HOST, port=Config.MYSQL_PORT, user=Config.MYSQL_USER, password=Config.MYSQL_PASSWORD, database=db_name, charset='utf8mb4', autocommit=True)

    @staticmethod
    def execute_sql(sql: str, db_name: str, timeout: int=Config.SQL_TIMEOUT) -> Tuple[bool, Any, float]:
        conn = None
        try:
            conn = DatabaseUtils.get_connection(db_name)
            cursor = conn.cursor()
            timeout_ms = timeout * 1000
            cursor.execute(f'SET SESSION MAX_EXECUTION_TIME = {timeout_ms}')
            start_time = time.time()
            cursor.execute(sql)
            result = cursor.fetchall()
            execution_time = time.time() - start_time
            return (True, result, execution_time)
        except Exception as e:
            return (False, str(e), 0.0)
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_schema(db_name: str) -> Dict[str, List[str]]:
        schema = {}
        conn = None
        try:
            conn = DatabaseUtils.get_connection(db_name)
            cursor = conn.cursor()
            cursor.execute('SHOW TABLES')
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f'DESCRIBE `{table}`')
                columns = [row[0] for row in cursor.fetchall()]
                schema[table] = columns
            return schema
        except Exception as e:
            print(f'Failed to retrieve MySQL schema [DB: {db_name}]: {e}')
            return {}
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_sample_data(db_name: str, table: str, limit: int=3) -> List[Tuple]:
        conn = None
        try:
            conn = DatabaseUtils.get_connection(db_name)
            cursor = conn.cursor()
            cursor.execute(f'SELECT * FROM `{table}` LIMIT {limit}')
            data = cursor.fetchall()
            return data
        except Exception as e:
            print(f'Failed to retrieve sample data [{table}]: {e}')
            return []
        finally:
            if conn:
                conn.close()

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
        self.url = Config.LLM_URL
        self.headers = Config.LLM_HEADERS
        self.embedding_model = LocalEmbeddingModel()

    def get_embedding(self, text: str) -> np.ndarray:
        return self.embedding_model.get_embedding(text)

    def health_check(self) -> bool:
        print(f'Checking LLM service availability:')
        try:
            test_prompt = 'who are you'
            response = requests.post(self.url, headers=self.headers, json={'model': Config.LLM_NAME, 'messages': [{'role': 'user', 'content': test_prompt}], 'temperature': 0.1, 'max_tokens': 15, 'stream': False}, timeout=30)
            print('[', Config.LLM_NAME, ']:', response.json().get('choices', [{}])[0].get('message', {}).get('content', ''))
            return response.status_code == 200
        except Exception as e:
            print('[LLM connection error]:', e)
            return False

    def _single_call(self, prompt: str, temperature: float) -> Optional[str]:
        try:
            data = {'model': Config.LLM_NAME, 'messages': [{'role': 'system', 'content': 'You are a professional SQL assistant specialized in converting natural language questions into SQL queries.'}, {'role': 'user', 'content': prompt}], 'temperature': temperature, 'max_tokens': 1024, 'stream': False}
            response = requests.post(self.url, headers=self.headers, json=data, timeout=200)
            if response.status_code != 200:
                print(f'[LLM error response] {response.text[:2000]}')
                return None
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            if not content:
                print(f'[Empty LLM content] Full response: {result}')
                return None
            return content
        except Exception as e:
            print(f'Single request failed: {type(e).__name__}: {e}')
            return None

    def call_llm(self, prompt: str, n: int=1, temperature: float=Config.TEMPERATURE) -> List[str]:
        responses = []
        with ThreadPoolExecutor(max_workers=n) as executor:
            future_to_req = {executor.submit(self._single_call, prompt, temperature): i for i in range(n)}
            for future in as_completed(future_to_req):
                res = future.result()
                if res:
                    responses.append(res)
                else:
                    responses.append(f'Fallback response for failed request')
        return responses

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
            print(responses)
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
        if Config.DEBUG_MODE == 'on':
            DEBUG_TRAIN_LIMIT = 10
            self.training_data = self.training_data[:DEBUG_TRAIN_LIMIT]
            print(f'Debug mode: only the first {len(self.training_data)} training samples are used for embedding precomputation')
        question_texts = [item['question'] for item in self.training_data]
        self.question_embeddings = []
        for i, text in enumerate(question_texts):
            if i % 40 == 0:
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
            indices = indices[0]
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
            indices = indices[0]
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
        prompt_parts.append('\nGenerate a correct MySQL SQL query for the question above. Provide detailed reasoning steps.\nYour response must strictly follow this JSON format:\n{\n  "reasoning": "Reasoning steps for generating the SQL, including table, column, and condition selection",\n  "sql": "Generated SQL query"\n}\n\nReturn JSON only. Do not include any other text.\n')
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
        if not candidates:
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
        db_name = BIRDDatasetLoader.get_db_name(db_id)
        print(f'\nStep 1: Retrieve database schema [MySQL DB: {db_name}]...')
        full_schema = DatabaseUtils.get_schema(db_name)
        if not full_schema:
            print(f"Error: failed to retrieve database schema. Please check whether the database exists in MySQL '{db_name}'")
            return {'error': f'Failed to retrieve database schema: {db_name}'}
        print(f'  Database contains {len(full_schema)} tables')
        DEBUG_RANDOM_DROP_SCHEMA = True
        RANDOM_SEED = 42
        MAX_SCHEMA_CHARS = 22000

        def estimate_schema_chars(schema: Dict[str, List[str]]) -> int:
            schema_lines = []
            for table, columns in schema.items():
                schema_lines.append(f"# {table} ({', '.join(columns)})")
            return len('\n'.join(schema_lines))
        if DEBUG_RANDOM_DROP_SCHEMA:
            random.seed(RANDOM_SEED)
            full_schema_chars = estimate_schema_chars(full_schema)
            print(f'  Approximate full_schema text length:: {full_schema_chars} characters')
            all_tables = list(full_schema.keys())
            if full_schema_chars <= MAX_SCHEMA_CHARS:
                reduced_schema = full_schema
                drop_ratio = 0
                print('  Schema length is within the limit; random truncation is not applied')
            else:
                keep_ratio = MAX_SCHEMA_CHARS / full_schema_chars
                keep_ratio = keep_ratio * 0.9
                keep_ratio = max(0.1, min(1.0, keep_ratio))
                keep_num = max(1, int(len(all_tables) * keep_ratio))
                drop_ratio = 1 - keep_ratio
                kept_tables = random.sample(all_tables, keep_num)
                reduced_schema = {table: full_schema[table] for table in kept_tables}
                reduced_schema_chars = estimate_schema_chars(reduced_schema)
                print(f'  Automatically computed drop_ratio: {drop_ratio:.2%}')
                print(f'  Debug mode: randomly retained  {len(reduced_schema)}/{len(full_schema)} tables')
                print(f'  Approximate reduced_schema text length:: {reduced_schema_chars} characters')
        else:
            reduced_schema = full_schema
        print('\nStep 2: Schema linking...')
        selected_tables = self.schema_linker.table_linking(reduced_schema, question, evidence)
        print(f'  Selected tables ({len(selected_tables)}): {list(selected_tables)[:5]}...')
        selected_columns = self.schema_linker.column_linking(selected_tables, reduced_schema, question, evidence)
        print(f'  Selected columns ({len(selected_columns)}): {list(selected_columns)[:5]}...')
        filtered_schema = {}
        for column in selected_columns:
            clean_column = column.replace('`', '').strip()
            if '.' in clean_column:
                parts = clean_column.split('.', 1)
                table = parts[0].strip()
                col = parts[1].strip()
                if table in selected_tables and table in reduced_schema:
                    if table not in filtered_schema:
                        filtered_schema[table] = []
                    if col not in filtered_schema[table]:
                        filtered_schema[table].append(col)
        if not filtered_schema:
            print('Warning: schema linking did not select any table or column. Using the randomly reduced schema.')
            filtered_schema = reduced_schema
        print(f'  Filtered schema: {len(filtered_schema)} tables')
        print('\nStep 3: Generate SQL candidates...')
        sql_candidates = self.sql_generator.generate_candidates(question, filtered_schema, evidence)
        print('\nStep 4: Candidate filtering (MySQL execution validation)...')
        filtered_candidates = self.sql_selector.filter_candidates(sql_candidates, db_name)
        print('\nStep 5: Multiple-choice selection...')
        if filtered_candidates:
            final_sql = self.sql_selector.multiple_choice_selection(filtered_candidates, question, filtered_schema, evidence)
            print(f'  Final SQL: {final_sql[:100]}...')
        else:
            final_sql = ''
            print('  Warning: no valid SQL candidate was found')
        if final_sql:
            success, result, exec_time = DatabaseUtils.execute_sql(final_sql, db_name)
            return {'question': question, 'evidence': evidence, 'db_id': db_id, 'db_name': db_name, 'final_sql': final_sql, 'execution_success': success, 'execution_result': result if success else str(result), 'execution_time': exec_time, 'num_candidates_generated': len(sql_candidates), 'num_candidates_filtered': len(filtered_candidates), 'selected_tables': list(selected_tables), 'selected_columns': list(selected_columns)}
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
            result['question_id'] = test_item.get('question_id')
            result['global_index'] = global_index
            results.append(result)
            if (i + 1) % 5 == 0:
                BatchTester.save_results(results, f'results_batch_{global_index + 1}.json')
        return results

    @staticmethod
    def save_results(results, filename):
        os.makedirs(Config.RUN_DIR, exist_ok=True)
        full_path = os.path.join(Config.RUN_DIR, filename)
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=decimal_default)
        except Exception as e:
            print(f'Failed to save results [{filename}]: {e}')

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
    os.makedirs(Config.RUN_DIR, exist_ok=True)
    print('Checking model service connection...')
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
    print('\n6. Start evaluating generated SQL results...')
    pred_file = os.path.join(Config.RUN_DIR, 'predictions.json')
    eval_predictions = []
    for result in results:
        if 'final_sql' in result and result['final_sql']:
            q_id = result.get('question_id') or result.get('global_index', 0)
            eval_predictions.append({'question_id': q_id, 'db_id': result['db_id'], 'predicted_sql': result['final_sql']})
    with open(pred_file, 'w', encoding='utf-8') as f:
        json.dump(eval_predictions, f, ensure_ascii=False, indent=2, default=decimal_default)
    try:
        sys.path.append(os.path.dirname(Config.EVALUATE_SQL_PATH))
        from evaluate_sql import evaluate_sql as run_evaluation
        output_f = os.path.join(Config.RUN_DIR, 'evaluation_results.txt')
        dev_json = os.path.join(Config.BIRD_DATASET_PATH, 'dev', 'dev.json')
        run_evaluation(pred_file, dev_json, output_f)
        print(f'✅ Evaluation completed. Results saved to: {output_f}')
    except Exception as e:
        print(f'⚠️ Automatic evaluation failed, possibly due to path settings inside the evaluation script: {e}')
        print(f'Please run manually: python evaluate_sql.py')

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
    print('Checking LLM service connection...')
    llm = LocalLLMClient()
    if llm.health_check():
        print('✅ LLM service is reachable')
    else:
        print('⚠️  LLM service connection failed. Fallback responses will be used.')
