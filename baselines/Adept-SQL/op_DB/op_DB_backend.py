import pandas as pd
import pymysql
pymysql.install_as_MySQLdb()
from sqlalchemy import create_engine, MetaData, select, insert

from config import *

class backend_db_op():
    def __init__(self,assistant_id = '9'):

        self.assistant_id = int(assistant_id)

        DB_string =f"mysql+mysqldb://{backendb.user_name}:{backendb.password}@{backendb.url}:{backendb.port}/{backendb.database}?charset=utf8mb4"

        self.engine = create_engine(DB_string)
        self.conn = self.engine.connect()
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)

    def query_table(self, table_name):

        table = self.metadata.tables[table_name]

        with self.engine.connect() as conn:
            result = conn.execute(table.select())
            table = pd.DataFrame([row for row in result])
            if 'assistant_id' in table.columns:
                table = table[table['assistant_id']== self.assistant_id]
            return table
        
    def query_field(self, table_name, field_name):

        table = self.metadata.tables[table_name]

        with self.engine.connect() as conn:
            if 'assistant_id' in table.columns:
                result = conn.execute(select(getattr(table.c, field_name)).where(table.c.assistant_id == self.assistant_id))
            else:
                result = conn.execute(select(getattr(table.c, field_name)))
        return [row[0] for row in result] 
        
    def insert_data(self, table_name, data):

        table = self.metadata.tables[table_name]

        with self.engine.connect() as conn:
            insert_stmt = insert(table).values(data)
            result = conn.execute(insert_stmt)
            conn.commit()
            if result.is_insert: 
                return("Insert successed")
            else:
                return("Insert failed")
    def delete_data_in_termlist(self, term):

        table = self.metadata.tables['term_list']

        with self.engine.connect() as conn:
            delete_stmt = table.delete().where("term" == term)
            delete_stmt = table.delete().where(getattr(table.c, "term") == term)
            result = conn.execute(delete_stmt)
            conn.commit()
            if result.rowcount > 0: 
                return "Delete success"
            else:
                return "Delete failed"


if __name__ == '__main__':
    data = [
            {'qtype': 'L34356', 
            'question1': 'q1',
            'sql1': 'SELECT AAA',
            'question2': 'Q2',
            'sql2': 'SELECT bbb'},
        ]
    db = backend_db_op(assistant_id = '9')
    #print(db.query_table('field_info'))
    print(db.delete_data_in_termlist('对象1'))