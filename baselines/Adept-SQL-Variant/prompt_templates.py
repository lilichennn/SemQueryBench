from typing import Type

from op_DB import vecdb_op, backend_db_op, user_db_op
from user_input_process import user_input_init
import pandas as pd
from utils import *
from call_llm import callLLM

import json
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

class select_tables:
    def __init__(self, user_question, modelname):
        self.user_question = user_question
        self.modelname = modelname
        
        # Get all tables metadata
        status, tables_meta = user_db_op().query_all_tables_meta()
        if not status:
            raise Exception(f"Failed to get tables metadata: {tables_meta}")
        self.tables_meta = tables_meta
    
    def get_table_structure_str(self):
        """Convert tables metadata to string format"""
        structure_str = ""
        for table_name, info in self.tables_meta.items():
            fields = []
            for col_name, col_type in info['columns'].items():
                fields.append(f"{col_name}({col_type})")
            structure_str += f"- Table: {table_name}, Fields: {', '.join(fields)}\n"
        return structure_str
    
    def sys_prompt(self):
        self.SYSTEM_PROMPT = """
# Role
You are a database table selection assistant.

# Task
Based on:
1. User question
2. Table structure (table name, field name, field type)

Identify:
- The most suitable table(s) to answer the question (if one table cannot answer, return multiple tables for joint analysis)
- The relevant fields from each selected table (return all fields needed to answer the question)

You need to understand field semantics, not just string matching.

# Input Format
User question: [user question]
Table structure: Table name: field1(type), field2(type), ...

# Output Format
Output ONLY JSON, no explanation.
Format:
{
    "table": [table_name1, table_name2, ...],
    "fields": {table_name1: ["field1(type)", "field2(type)", ...], table_name2: ["field1(type)", "field2(type)", ...]}
}

# Rules
1. Prefer single table
2. Return only highly relevant tables
3. Fields should only include question-relevant fields
4. Do not generate SQL
5. No irrelevant content
6. Both "table" and "fields" cannot be empty
7. Must select the most relevant tables even if uncertain
8. At least one table must be returned
9. Returned fields must belong to corresponding table
"""
    
    def select_tables_temp(self):
        self.sys_prompt()
        user_prompt = f"""User question: {self.user_question}

Table structure:
{self.get_table_structure_str()}
"""
        
        res = callLLM(self.modelname).init_prompt(self.SYSTEM_PROMPT, user_prompt).call().get_response_content()
        
        if "error" not in str(res):
            try:
                res = res.replace('\n', '').replace('```json', '').replace('```', '')
                res_dict = json.loads(res)
                return 1, res_dict
            except json.JSONDecodeError:
                return 2, f"JSON parse failed: {res}"
        else:
            return 0, f"LLM error: {res}"
    
    def select_tables(self):
        self.sys_prompt()
        

        status, table_count = user_db_op().get_table_count()
        if not status:
            return 0, f"Failed to get table count: {table_count}"
        
        if table_count <= 100:
            user_prompt = f"""User question: {self.user_question}

    Table structure:
    {self.get_table_structure_str()}
    """
            res = callLLM(self.modelname).init_prompt(self.SYSTEM_PROMPT, user_prompt).call().get_response_content()
            
            if "error" not in str(res):
                try:
                    res = res.replace('\n', '').replace('```json', '').replace('```', '')
                    res_dict = json.loads(res)
                    return 1, res_dict
                except json.JSONDecodeError:
                    return 2, f"JSON parse failed: {res}"
            else:
                return 0, f"LLM error: {res}"

        all_tables = list(self.tables_meta.keys())
        batch_size = 100
        batches = [all_tables[i:i+batch_size] for i in range(0, len(all_tables), batch_size)]
        
        batch_results = []
        for idx, batch_tables in enumerate(batches):
            batch_structure = ""
            for table_name in batch_tables:
                info = self.tables_meta[table_name]
                fields = []
                for col_name, col_type in info['columns'].items():
                    fields.append(f"{col_name}({col_type})")
                batch_structure += f"- Table: {table_name}, Fields: {', '.join(fields)}\n"
            
            user_prompt = f"""User question: {self.user_question}

    Table structure (batch {idx+1}/{len(batches)}):
    {batch_structure}
    """
            res = callLLM(self.modelname).init_prompt(self.SYSTEM_PROMPT, user_prompt).call().get_response_content()
            
            if "error" in str(res):
                continue
            try:
                res = res.replace('\n', '').replace('```json', '').replace('```', '')
                res_dict = json.loads(res)
                batch_results.append(res_dict)
            except json.JSONDecodeError:
                batch_results.append({"raw_response": res, "batch_index": idx+1})
                continue
        
        if not batch_results:
            return 0, "No valid results from any batch"
        
        summary_structure = ""
        for i, result in enumerate(batch_results):
            if "raw_response" in result:
                summary_structure += f"Batch {result['batch_index']} returned invalid JSON: {result['raw_response'][:200]}...\n"
            else:
                tables = result.get('table', [])
                fields = result.get('fields', {})
                summary_structure += f"Batch {i+1} selected tables: {', '.join(tables)}\n"
                for table, field_list in fields.items():
                    summary_structure += f"  - {table}: {', '.join(field_list)}\n"
        
        final_prompt = f"""User question: {self.user_question}

    Previous selection results:
    {summary_structure}

    Based on the above selections, please choose the most suitable table(s) and fields to answer the question.
    """
        
        final_res = callLLM(self.modelname).init_prompt(self.SYSTEM_PROMPT, final_prompt).call().get_response_content()
        
        if "error" not in str(final_res):
            try:
                final_res = final_res.replace('\n', '').replace('```json', '').replace('```', '')
                res_dict = json.loads(final_res)
                return 1, res_dict
            except json.JSONDecodeError:
                return 2, f"JSON parse failed in final selection: {final_res}"
        else:
            return 0, f"LLM error in final selection: {final_res}"
    
    def build_meta_response(self):
        """Build formatted table metadata from selection result"""
        flag,selected_tables=self.select_tables()
   
        if not flag:
            return """Table: None.No tables selected. """
        elif flag ==2:
            return f"""Table: None.YOU SHOULD MESSAGE FORM:
{selected_tables}"""
        
            # 正确提取表名列表
        selected_tables = selected_tables.get("table", [])
        if not selected_tables:
            return f"""Table: None.YOU SHOULD MESSAGE FORM:
{selected_tables}"""
        
        save_meta = {}
        for table_name in selected_tables:
            status, meta_data = user_db_op().query_table_meta(table_name)
            if status:
                save_meta[table_name] = meta_data
                
        
        if not save_meta:
            return f"""Table: None.YOU SHOULD MESSAGE FORM:
{selected_tables}"""
        
        # Build formatted output
        result_str = []
        for table_name, fields in save_meta.items():
            table_info = f"Table: {table_name}"
            field_lines = []
            for field, (field_type, sample) in fields.items():
                field_lines.append(f"  - {field}: {field_type} (sample: {sample})")
            table_info += "\n" + "\n".join(field_lines)
            result_str.append(table_info)
        prompt="#Based on the table information below, filter the data relevant to answering the user's question. Output format: Table Name; Field Information: Field: Type (Sample Value)...\n"
        prompt +="\n\n".join(result_str)
        return prompt
    def build_meta_response(self):
        """Build formatted table metadata from selection result"""
        flag,selected_tables=self.select_tables()
   
        if not flag:
            return """Table: None.No tables selected. """
        elif flag ==2:
            return f"""Table: None.YOU SHOULD MESSAGE FORM:
{selected_tables}"""
        
            # 正确提取表名列表
        selected_tables = selected_tables.get("table", [])
        if not selected_tables:
            return f"""Table: None.YOU SHOULD MESSAGE FORM:
{selected_tables}"""
        
        save_meta = {}
        for table_name in selected_tables:
            status, meta_data = user_db_op().query_table_meta(table_name)
            if status:
                save_meta[table_name] = meta_data
                
        
        if not save_meta:
            return f"""Table: None.YOU SHOULD MESSAGE FORM:
{selected_tables}"""
        
        # Build formatted output
        result_str = []
        for table_name, fields in save_meta.items():
            table_info = f"Table: {table_name}"
            field_lines = []
            for field, (field_type, sample) in fields.items():
                field_lines.append(f"  - {field}: {field_type} (sample: {sample})")
            table_info += "\n" + "\n".join(field_lines)
            result_str.append(table_info)
        prompt="#Based on the table information below, filter the data relevant to answering the user's question. Output format: Table Name; Field Information: Field: Type (Sample Value)...\n"
        prompt +="\n\n".join(result_str)
        return prompt

class Prompt_Fewshot:
    def __init__(self, user_input:Type[user_input_init], qtype, assistant_id,modelname):
        self.user_input_cls = user_input
        self.qtype = qtype
        self.assistant_id = int(assistant_id)
        self.modelname=modelname
    
    def get_instances(self):  
        self.qa_pair = vecdb_op(self.assistant_id).retrive_sqlQA(self.qtype)
        return self

    def get_prompts(self):
        self.prompt = '''
    #Role#
    You are a MySQL engineer. You are skilled at writing new SQL statements by imitating similar SQL statements, and you can replace special nouns and time points in the SQL according to the actual situation.
    Now, please follow the example below to write a MySQL statement to answer the user's question.

    #Constraints#
    1. The SQL in the answer must use the professional terms mentioned in the [Reminder]; do not change the professional terms.
    2. Create a MySQL statement with correct syntax following the example below.
    3. The SQL answer needs to be readable; you should add line breaks where appropriate.
    4. Please check the correctness of the SQL, paying attention not to misplace field affiliations.
    5. Your output must be in plain text format.
    '''

        return self
    

    
    def compile(self):
        self.get_instances()
        self.get_prompts()
        tables_meta = select_tables(self.user_input_cls.trans,self.modelname).build_meta_response()
    

        #开始组装
        prefix = self.prompt

        case_sql1 = f"""
#Example 1#
Question：{self.qa_pair["question"]}
Answer SQL：{self.qa_pair["sql"]}
"""
        suffix = f"""
#Commencing Response#
Question:{self.user_input_cls.trans}
"""
        if hasattr(self.user_input_cls, 'gen_hints'):
            suffix += f"""
Reminder：{self.user_input_cls.gen_hints()}
"""
        suffix +="Answer SQL："
       
        self.prompt = [prefix, case_sql1,tables_meta,suffix]

        return "\n".join(self.prompt)



# DIDNOT found the similar question in the complex QA list
class Prompt_Zeroshot:
    def __init__(self, user_input:Type[user_input_init], db_id, assistant_id,modelname):
        self.user_input_cls = user_input
        self.assistant_id = int(assistant_id)
        self.db_id = int(db_id)
        self.modelname=modelname

        
        try:
            self.field_info = backend_db_op(self.assistant_id).query_table('field_info')
            self.field_info = self.field_info[(self.field_info['enable'] == 1) &\
                                                (self.field_info['db_id'] == self.db_id)]
        except:
            self.field_info = pd.DataFrame()
        
        try:
            self.table_info = backend_db_op(self.assistant_id).query_table('table_info')
            self.table_info = self.table_info[(self.table_info['enable'] == 1) &\
                                               (self.table_info['db_id'] == self.db_id)]
        except:
            self.table_info = pd.DataFrame()

    def table_list(self):

        
        self.user_input_cls.term_recognition()
        field_in_uq = set([i[1] for i in self.user_input_cls.hints])
        print('The terms in the question correspond to the following fields:：', field_in_uq)        
   
        if len(field_in_uq) == 0:
            self.tables = []
        else:
            try:
                self.t_id = self.field_info[self.field_info['field_name'].isin(field_in_uq)]['table_id'].tolist()
                relevant_tables = self.table_info[self.table_info['id'].isin(self.t_id)]
                self.tables = relevant_tables[['id', 'table_name', 'table_description']].values.tolist()
            except:
                self.tables = []
        return self

    def field_list(self):

        if len(self.tables) == 0:
            self.table_structure = []
        else:
       
            try:
                relevant_fields = self.field_info[self.field_info['table_id'].isin(self.t_id)]
                self.table_structure = relevant_fields[['table_id','field_name','field_type','field_description']].values.tolist()
            except:
                self.table_structure = []
        return self
    
    def get_prompts(self):
        self.prompt =  '''
    #Role#
    You are a MySQL engineer in the company. You are very familiar with the table information in the database, as well as the meanings of tables, fields, and field types. You serve the production and operation frontline personnel. When they need to query data from the database, you can write correct SQL statements based on their questions.

    #Task#
    You now have a query request from a production and operations person. They have told you the question and which field corresponds to the professional terms in the question. You need to write a correct SQL statement using the table structure information provided below.

    #Constraints#
    1. The SQL in the answer must use the professional terms mentioned in the [Reminder]; do not change the professional terms.
    2. Create a MySQL statement with correct syntax following the example below.
    3. The SQL answer needs to be readable; you should add line breaks where appropriate.
    4. Please check the correctness of the SQL, paying attention not to misplace field affiliations.
    5. You only need to write the SQL; do not provide reasoning or explanations to the user.
    6. You must ensure that the output can be executed by pd.read_sql_query().
    '''

        return self
    
#     def compile_tablestructure(self):
#         if self.tables == []:
#             self.all_tablestructure = \
# '''
# Table: None
# The database you have selected contains no tables that can answer your question. I will generate SQL statements based on my own understanding.
#  '''
#         else:
#             self.all_tablestructure = \
# ''''''
#             for tid in self.t_id:
#                 table = [i for i in self.tables if i[0]==tid][0]
#                 fields = [i for i in self.table_structure if i[0]==tid]

#                 tname = table[1]
#                 tdes = table[2]
#                 table_structure = \
# f'''
# TABLE:\t"{tname}"\t{tdes}
# '''

#                 for field in fields:
#                     fname = field[1]
#                     ftype = field[2]
#                     fdes = field[3]
#                     field_structure = \
# f'''\tField: "{fname}", Type："{ftype}"\t{fdes}
# '''
#                     table_structure += field_structure
#                 self.all_tablestructure += table_structure

#         return self

    def compile(self):
        
        #开始组装
        prefix = self.get_prompts().prompt
        # table_structure = self.table_list().field_list().compile_tablestructure().all_tablestructure
        tables_meta = select_tables(self.user_input_cls.trans,self.modelname).build_meta_response()
    

        suffix = f"""
#Commencing Response#
Question：{self.user_input_cls.trans}
"""
        if hasattr(self.user_input_cls, 'gen_hints'):
                        suffix += f"""
Reminder：{self.user_input_cls.gen_hints()}
"""
        suffix +="Answer SQL："

        self.prompt = [prefix, tables_meta, suffix]

        return "\n".join(self.prompt)




if __name__ == "__main__":


    # status, res = select_tables("在影像数据共享平台（IDC）中，哪些原始数据集的样本数量最多？列出前五个",'qwen-72b-instruct').select_tables()
    # print(res)
    sample=(1,{"table": ["idc_v17_original_collections_metadata","idc_v17_dicom_pivot"]})
    res = select_tables("在影像数据共享平台（IDC）中，哪些原始数据集的样本数量最多？列出前五个",'qwen-72b-instruct').build_meta_response(sample)
    print(res)

    # assistant_id = '22'
    # db_id = '7'

    # # from search_qtype import search_qtype
    # # user_input = user_input_init("中石油广东石化2024年3月联锁投用率是多少")
    # # flag, info, qtype = search_qtype(user_input.input)
    # # prompt = Prompt_Fewshot(user_input, qtype, assistant_id).compile()
    # # print(prompt)


    # user_input = user_input_init("数据库id为1的数据库有几张表").full_process()
    # prompt = Prompt_Zeroshot(user_input, db_id, assistant_id)
    # print(prompt.compile())

#中石油广东石化2024年3月联锁投用率是多少
#常减压装置1套常压不凝气2024年2月计划收率是多少？