import pandas as pd
import pymysql
pymysql.install_as_MySQLdb()
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine, MetaData, select,text
from urllib.parse import quote_plus

from config import *
from op_DB_backend import *


class user_db_op():
    def __init__(self):
        self.userdb = user_db_config
        print('Connect  user database：',self.userdb['db_name'])

        DB_string = f"mysql+mysqldb://{self.userdb['user_name']}:{self.userdb['user_password']}@{self.userdb['ip']}:{self.userdb['port']}/{self.userdb['db_name']}?charset=utf8mb4"
        self.engine = create_engine(DB_string)

        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)

    
    def query_table(self,table_name):

        table = self.metadata.tables[table_name.upper()]
        with self.engine.connect() as conn:
            result = conn.execute(table.select())
            return [row for row in result]
        
    def query_field(self, table_name, field_name):

        table = self.metadata.tables[table_name.upper()]
        with self.engine.connect() as conn:
            result = conn.execute(select(getattr(table.c, field_name)))
            return [row[0] for row in result]

    
    def query_table_meta(self, table_name):
        conn = None
        
        try:
            conn = self.engine.connect()
            
            # 获取数据
            df = pd.read_sql(f'SELECT * FROM {table_name} LIMIT 10000', conn)
            
            # 获取数据库字段类型
    
            query = text(f"""
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = '{self.userdb['db_name']}' AND TABLE_NAME = '{table_name}'
            ORDER BY ORDINAL_POSITION
        """)
            res = conn.execute(query)
            db_types = {row[0]: row[1] for row in res.fetchall()}
            
            
            result = {}
            for col in df.columns:
               
                if df[col].notna().any():
                    value = df[col].dropna().iloc[0]
                    if isinstance(value, str) and len(value) > 20:
                        value = value[:20] + '..'
                else:
                    value = None
                
                result[col] = (db_types.get(col, 'unknown'), value)
            
            return 1, result
            
        except Exception as e:
            print(f"Query execution failed: {e}")
            return 0, f"Query execution failed: {e}"
        finally:
            if conn:
                conn.close()
    def query_all_tables_meta(self):
        conn = None
        try:
            conn = self.engine.connect()
            
            # Get all table names
            tables_query = text("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = :db_name AND TABLE_TYPE = 'BASE TABLE'
            """)
            tables = conn.execute(tables_query, {"db_name": self.userdb['db_name']}).fetchall()
            
            result = {}
            for table in tables:
                table_name = table[0]
                
                # Get column info for each table
                columns_query = text("""
                    SELECT COLUMN_NAME, DATA_TYPE 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name
                    ORDER BY ORDINAL_POSITION
                """)
                columns = conn.execute(columns_query, {
                    "db_name": self.userdb['db_name'], 
                    "table_name": table_name
                }).fetchall()
                
                # Build column info
                result[table_name] = {
                    'columns': {col_name: col_type for col_name, col_type in columns}
                }
            
            return 1, result
            
        except SQLAlchemyError as e:
            return 0, f"Query failed: {e}"
        finally:
            if conn:
                conn.close()
        
    def sql_execute(self, sql):
        with self.engine.connect() as connection:
            try:
                df = pd.read_sql_query(text(sql), self.engine)
            except SQLAlchemyError as e:
                df = pd.DataFrame({'SQLerror': [f"SQLAlchemyError: {e}"]})
            except ValueError as ve:
                df = pd.DataFrame({'SQLerror': [f"ValueError: {ve}"]})  
            except Exception as e:
                df = pd.DataFrame({'SQLerror': [f"An unexpected error occurred: {e}"]})
            except:
                df = pd.DataFrame({'SQLerror': ["An unknown error occurred."]})
            if df.empty:
                return [{col: None for col in df.columns}]
            return df.to_dict('records')

        
    def query_ddl(self, table_name):
        with self.engine.connect() as conn:
            result = conn.execute(text("SHOW CREATE TABLE {}".format(table_name)))
            result = result.fetchone()[1].split('ENGINE=')[0]
            return result
    def get_table_count(self):
        conn = None
        try:
            conn = self.engine.connect()
            query = text("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = :db_name AND TABLE_TYPE = 'BASE TABLE'
            """)
            result = conn.execute(query, {"db_name": self.userdb['db_name']})
            count = result.scalar()
            return 1, count
        except SQLAlchemyError as e:
            return 0, f"Query failed: {e}"
        finally:
            if conn:
                conn.close()   

if __name__ == '__main__':
    table_name="idc_v17_original_collections_metadata"
    res = user_db_op().query_table_meta(table_name)
    #res = user_db_op('1').query_ddl('pm_unit_t')
    print(res)
