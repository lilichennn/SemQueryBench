import pandas as pd
import re, os, chardet
import pymysql
import random

def random_reduce_db_info_by_tables(
    table_infos,
    max_db_info_chars=50000,
    seed=42
):
    """
    以表为单位随机裁剪 db_info，使拼接后的 schema 描述不超过 max_db_info_chars。
    table_infos: List[Tuple[str, str]]，格式为 [(table_name, table_info), ...]
    """
    if not table_infos:
        return ""

    full_db_info = "\n".join([info for _, info in table_infos])

    if len(full_db_info) <= max_db_info_chars:
        return full_db_info

    original_len = len(full_db_info)
    keep_ratio = max_db_info_chars / original_len
    keep_ratio = max(0.05, min(1.0, keep_ratio))

    keep_num = max(1, int(len(table_infos) * keep_ratio))

    rng = random.Random(seed)
    kept_indices = sorted(rng.sample(range(len(table_infos)), keep_num))

    kept_table_infos = [table_infos[i] for i in kept_indices]
    reduced_db_info = "\n".join([info for _, info in kept_table_infos])

    # 因为不同表长度不一样，按比例抽完后仍可能超长，所以继续删表
    while len(reduced_db_info) > max_db_info_chars and len(kept_table_infos) > 1:
        remove_idx = rng.randrange(len(kept_table_infos))
        kept_table_infos.pop(remove_idx)
        reduced_db_info = "\n".join([info for _, info in kept_table_infos])

    print(f"[get_db_des] original db_info length: {original_len}")
    print(f"[get_db_des] reduced db_info length: {len(reduced_db_info)}")
    print(f"[get_db_des] original table count: {len(table_infos)}")
    print(f"[get_db_des] kept table count: {len(kept_table_infos)}")
    print(f"[get_db_des] keep_ratio estimate: {keep_ratio:.2f}")
    print("[get_db_des] kept tables:", len([name for name, _ in kept_table_infos]))

    return reduced_db_info

def find_foreign_keys_MYSQL_like(DATASET_JSON, db_name):
    schema_df = pd.read_json(DATASET_JSON, encoding='utf-8')
    schema_df = schema_df.drop(['column_names', 'table_names'], axis=1)
    f_keys = []
    for index, row in schema_df.iterrows():
        tables = row['table_names_original']
        col_names = row['column_names_original']
        foreign_keys = row['foreign_keys']
        for foreign_key in foreign_keys:
            first, second = foreign_key
            first_index, first_column = col_names[first]
            second_index, second_column = col_names[second]
            f_keys.append([
                row['db_id'], tables[first_index], tables[second_index],
                first_column, second_column
            ])
    spider_foreign = pd.DataFrame(f_keys,
                                  columns=[
                                      'Database name', 'First Table Name',
                                      'Second Table Name',
                                      'First Table Foreign Key',
                                      'Second Table Foreign Key'
                                  ])

    df = spider_foreign[spider_foreign['Database name'] == db_name]
    output = []
    col_set = set()
    for index, row in df.iterrows():
        output.append(row['First Table Name'] + '.' +
                      row['First Table Foreign Key'] + " = " +
                      row['Second Table Name'] + '.' +
                      row['Second Table Foreign Key'])
        col_set.add(row['First Table Name'] + '.' +
                    row['First Table Foreign Key'])
        col_set.add(row['Second Table Name'] + '.' +
                    row['Second Table Foreign Key'])
    output = ", ".join(output)
    return output, col_set


def quote_field(field_name):
    # 正则表达式判断字段名是否包含空格或特殊字符
    if re.search(r'\W', field_name):
        # 如果匹配到，给字段名添加反引号
        return f"`{field_name}`"
    else:
        # 否则，不做改变
        return field_name


class db_agent:

    def __init__(self, chat_model) -> None:
        self.chat_model = chat_model

    def get_allinfo(self,db_json_dir, db,sqllite_dir,db_dir,tables_info_dir, model):
        db_info, db_col = self.get_db_des(sqllite_dir,db_dir,model)
        foreign_keys = find_foreign_keys_MYSQL_like(tables_info_dir, db)[0]
        all_info = f"Database Management System: MySQL\n#Database name: {db}\n{db_info}\n#Forigen keys:\n{foreign_keys}\n"
        prompt = self.db_conclusion(all_info)  #db_conclusion 就是个prompt
        db_all = self.chat_model.get_ans(prompt)
        all_info = f"{all_info}\n{db_all}\n"


        return all_info, db_col

    def get_complete_table_info(self, conn, table_name, table_df):
        cursor = conn.cursor()
        # 获取列的基本信息
        cursor.execute(f"DESCRIBE `{table_name}`")
        res = cursor.fetchall()
        columns_info = []
        for i, r in enumerate(res):
            columns_info.append((
                i,              # id
                r[0],           # name (Field)
                r[1],           # type (Type)
                1 if r[2] == 'NO' else 0, # notnull (Null)
                r[4],           # default_value (Default)
                1 if r[3] == 'PRI' else 0 # pk (Key)
            ))

        df = pd.read_sql_query(f"SELECT * FROM `{table_name}`", conn)
        contains_null = {
            column: df[column].isnull().any()
            for column in df.columns
        }
        contains_duplicates = {
            column: df[column].duplicated().any()
            for column in df.columns
        }
        dic = {}
        for _, row in table_df.iterrows():
            try:
                col_description, val_description = "", ""
                col = str(row.iloc[0]).strip()
                if pd.notna(row.iloc[2]):
                    col_description = re.sub(r'\s+', ' ', str(row.iloc[2]))
                if col_description.strip() == col or col_description.strip(
                ) == "":
                    col_description = ''
                if pd.notna(row.iloc[4]):
                    val_description = re.sub(r'\s+', ' ', str(row.iloc[4]))
                if val_description.strip() == "" or val_description.strip(
                ) == col or val_description == col_description:
                    val_description = ""
                col_description = col_description[:200]
                val_description = val_description[:200]
                dic[col] = col_description, val_description
            except Exception as e:
                print(e)
                dic[col] = "", ""
        # 获取示例值 (MySQL 语法兼容)
        cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 1")
        first_row_res = cursor.fetchone()
        row = list(first_row_res) if first_row_res else [None] * len(df.columns)

        for i, col in enumerate(df.columns):
            try:
                vals = df[col].dropna().drop_duplicates().iloc[:3].values
                val_p = []
                for val in vals:
                    try:
                        val_p.append(int(val))
                    except:
                        val_p.append(val)
                if len(vals) == 0:
                    raise ValueError
                row[i] = val_p
            except:
                pass
        # 构建schema表示
        schema_str = f"## Table {table_name}:\nColumn| Column Description| Value Description| Type| 3 Example Value\n"
        columns = {}
        for column, val in zip(columns_info, row):

            column_name, column_type, not_null, default_value, pk = column[1:6]
            tmp_col = column_name.strip()
            column_name = quote_field(column_name)

            schema_str += f"{column_name}| "
            col_des, val_des = dic.get(tmp_col, ["", ""])
            schema_str += f"{col_des}|{val_des}|"
            schema_str += f"{column_type}| "
            include_null = f"{'Include Null' if contains_null[tmp_col] else 'Non-Null'}"
            # schema_str += f"{include_null}| "
            unique = f"{'Non-Unique' if contains_duplicates[tmp_col] else 'Unique'}"
            # schema_str += f"{unique}| "
            if len(str(val)) > 360:  ## ddl展示 索引正常
                val = "<Long text not displayed>"
            columns[f"{table_name}.{column_name}"] = (col_des, val_des,
                                                      column_type,
                                                      include_null, unique,
                                                      str(val))
            schema_str += f"{val}\n"
        return schema_str, columns

    def get_db_des(self,sqllite_dir,db_dir,model):
        # 修改点：改为连接 MySQL。此时 sqllite_dir 参数应传入数据库名
        conn = pymysql.connect(
            host='localhost', # 根据你的环境修改
            user='root',
            password='your database password', # 替换为你的数据库密码
            database=sqllite_dir, # 这里的变量名保持不变，但内容是库名
            charset='utf8mb4'
        )
        
        table_dir = os.path.join(db_dir, 'database_description')
        # 修改点：MySQL 获取所有表的语法
        sql = "SHOW TABLES;"
        cursor = conn.cursor()
        cursor.execute(sql)
        tables = cursor.fetchall()

        table_infos = []
        db_col = dict()
        file_list = os.listdir(table_dir)
        files_emb = model.encode(file_list, show_progress_bar=False)

        for table in tables:
            if table[0] == 'sqlite_sequence':
                continue
            files_sim = (files_emb @ model.encode(table[0] + '.csv',
                                                  show_progress_bar=False).T)
            if max(files_sim) > 0.9:
                file = os.path.join(table_dir, file_list[files_sim.argmax()])
            else:
                file = os.path.join(table_dir, table[0] + '.csv')

            try:
                with open(file, 'rb') as f:
                    result = chardet.detect(f.read())
                encoding = result['encoding'] if result['encoding'] else 'utf-8'
                table_df = pd.read_csv(file, encoding=encoding)
            except Exception as e:
                print(f"Error reading CSV {file}: {e}")
                table_df = pd.DataFrame()

            table_info, columns = self.get_complete_table_info(
                conn, table[0], table_df)

            table_infos.append((table[0], table_info))
            db_col.update(columns)

        db_info = random_reduce_db_info_by_tables(
                    table_infos,
                    max_db_info_chars=45000,
                    seed=42
                )

        cursor.close()
        conn.close()

        return db_info, db_col

    def db_conclusion(self, db_info):
        prompt = f"""/* Here is a examples about describe database */
    #Forigen keys: 
    Airlines.ORIGIN = Airports.Code, Airlines.DEST = Airports.Code, Airlines.OP_CARRIER_AIRLINE_ID = Air Carriers.Code
    #Database Description: The database encompasses information related to flights, including airlines, airports, and flight operations.
    #Tables Descriptions:
    Air Carriers: Codes and descriptive information about airlines
    Airports: IATA codes and descriptions of airports
    Airlines: Detailed information about flights 

    /* Here is a examples about describe database */
    #Forigen keys:
    data.ID = price.ID, production.ID = price.ID, production.ID = data.ID, production.country = country.origin
    #Database Description: The database contains information related to cars, including country, price, specifications, Production
    #Tables Descriptions:
    Country: Names of the countries where the cars originate from.
    Price: Price of the car in USD.
    Data: Information about the car's specifications
    Production: Information about car's production.

    /* Describe the following database */
    {db_info}
    Please conclude the database in the following format:
    #Database Description:
    #Tables Descriptions:
    """
        # print(prompt)

        return prompt


class db_agent_string(db_agent):

    def __init__(self, chat_model) -> None:
        super().__init__(chat_model)

    def get_complete_table_info(self, conn, table_name, table_df):
        cursor = conn.cursor()
        
        # 1. 获取列的基本信息 (MySQL 语法)
        cursor.execute(f"DESCRIBE `{table_name}`")
        res = cursor.fetchall()
        
        # 映射为原代码预期的 6元组格式，确保 downstream 索引 column[1:6] 不变
        columns_info = []
        for i, r in enumerate(res):
            columns_info.append((
                i,                          # id
                r[0],                       # name (Field)
                r[1],                       # type (Type)
                1 if r[2] == 'NO' else 0,   # notnull (Null)
                r[4],                       # default_value (Default)
                1 if r[3] == 'PRI' else 0   # pk (Key)
            ))

        # 2. 手动构建 DataFrame 避开 pd.read_sql_query 的警告
        cursor.execute(f"SELECT * FROM `{table_name}`")
        data = cursor.fetchall()
        columns_names = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(list(data), columns=columns_names)

        contains_null = {column: df[column].isnull().any() for column in df.columns}
        contains_duplicates = {column: df[column].duplicated().any() for column in df.columns}

        dic = {}
        for _, row_data in table_df.iterrows():
            try:
                col_description, val_description = "", ""
                col = str(row_data.iloc[0]).strip()
                if pd.notna(row_data.iloc[2]):
                    col_description = re.sub(r'\s+', ' ', str(row_data.iloc[2]))
                if col_description.strip() == col or col_description.strip() == "":
                    col_description = ''
                if pd.notna(row_data.iloc[4]):
                    val_description = re.sub(r'\s+', ' ', str(row_data.iloc[4]))
                if val_description.strip() == "" or val_description.strip() == col or val_description == col_description:
                    val_description = ""
                dic[col] = col_description[:200], val_description[:200]
            except:
                dic[col] = "", ""

        # 4. 采样示例数据 (使用原变量名 row)
        cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 1")
        first_res = cursor.fetchone()
        row = list(first_res) if first_res else [None] * len(df.columns)
        for i, col in enumerate(df.columns):
            try:
                df_tmp = df[col].dropna().drop_duplicates()
                vals = df_tmp.sample(3).values if len(df_tmp) >= 3 else df_tmp.values
                val_p = [int(v) if str(v).isdigit() else v for v in vals]
                if len(vals) > 0: row[i] = val_p
            except: pass

        # ==========================================
        # 5. 构建极端压缩的 schema_str (仅用于 LLM Prompt)
        # 格式: Table T: col1(type), col2(type)...
        # ==========================================
        col_defs = []
        for column in columns_info:
            c_name, c_type = column[1], column[2]
            col_defs.append(f"{c_name}({c_type})")
        
        # 这一行是发给 LLM 的，不带示例值，体积减小 70% 以上
        schema_str = f"Table {table_name}: {', '.join(col_defs)}\n"
        
        # 如果有描述，只挑前 5 个重要的放进 Prompt，进一步压缩
        important_descs = []
        for col_name in columns_names[:5]: 
            c_des, _ = dic.get(col_name.strip(), ["", ""])
            if c_des: important_descs.append(f"{col_name}:{c_des[:30]}")
        if important_descs:
            schema_str += f"  Descs: {'; '.join(important_descs)}\n"

        # ==========================================
        # 5. 灵活压缩版 (给每张表分配固定的字符预算）
        # ==========================================
        dynamic_budget = max(300, len(table_name) * 30)
        col_defs = []
        current_len = len(f"T:{table_name}()\n")

        for column in columns_info:
            c_name = column[1]
            # 预估加上这个列后的长度
            next_col_str = f"{c_name}({c_type}),"
            
            # 检查是否超出该表的动态预算
            if current_len + len(next_col_str) > dynamic_budget:
                col_defs.append("...") # 提示 LLM 还有更多列
                break
                
            col_defs.append(next_col_str)
            current_len += len(next_col_str)

        schema_str = f"Table:{table_name}:{''.join(col_defs)}\n"

        # ==========================================
        # 6. 构建详细的 columns 字典 (用于存入 JSON，不限长度)
        # ==========================================
        columns = {}
        for column, val in zip(columns_info, row):
            column_name, column_type = column[1:3]
            tmp_col = column_name.strip()
            from llm.db_conclusion import quote_field
            quoted_name = quote_field(column_name)

            col_des, val_des = dic.get(tmp_col, ["", ""])
            null_info = "Include Null" if contains_null.get(tmp_col, False) else "Non-Null"
            uniq_info = "Non-Unique" if contains_duplicates.get(tmp_col, False) else "Unique"
            
            # 这里是存入 JSON 的详细文本描述，保持原样
            full_detail = f"Type: {column_type}, {null_info}, {uniq_info}. {col_des}"
            
            columns[f"{table_name}.{quoted_name}"] = (
                full_detail, col_des, val_des, column_type, 
                null_info, uniq_info, str(val)
            )
            
        return schema_str, columns