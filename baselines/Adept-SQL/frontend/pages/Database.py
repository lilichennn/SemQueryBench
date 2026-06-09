import pymysql
pymysql.install_as_MySQLdb()
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine, MetaData, select,text
from urllib.parse import quote_plus


import streamlit as st
from streamlit import session_state as ss
import pandas as pd

class localsqlite():
    def __init__(self, db_path):
        self.db_path = db_path
    
    def conn(self):
        self.connection = create_engine(f"sqlite:///{self.db_path}").connect()
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.connection)
        return self

#####################################################
st.title("Database Settings")

# sidebar setting
if 'tables' in ss and len(ss.tables)>0:
    st.sidebar.checkbox("DB ready", value=True, key="DBcheck")

if 'speSQL' in ss and 'selfSQL' in ss and 'answerGen' in ss:
    st.sidebar.checkbox("Prompts ready", value=True, key="PPcheck")
    

# DB信息填写表单
if 'userdb' not in st.session_state or ss.userdb['conn'] == False:
    option = st.pills(
    "Database Type",
    options=['Sqlite', 'MySQL','Use Test DB'],
    default='Use Test DB',
    selection_mode="single",
    )
    if option == 'Sqlite' or option == 'MySQL':
        ss.userdb = {}
        # ss.userdb['ip'] = st.text_input("IP")
        # ss.userdb['port'] = st.text_input("Port")
        ss.userdb['user_name']= st.text_input("User name")
        ss.userdb['user_password'] = st.text_input("Password")
        ss.userdb['db_name'] = st.text_input("Database")
        ss.userdb['conn'] = False
    if option == 'Use Test DB':
        ss.userdb = {}
        ss.userdb['db_name'] = "./sqlite/students.db"
        ss.userdb['conn'] = False
        f'''
        You are going to explore FATO-SQL with this samll test database {ss.userdb['db_name']}, which has 4 tables:
        * students
        * teachers
        * grades
        * subjects
        '''

# 连接DB / 显示链接信息
if not ss.userdb['conn']:
    if st.button("Connect"):
        try:
            db = localsqlite(ss.userdb['db_name']).conn()
            ss.userdb['conn'] = True
            ss.userdb['conn']
            st.sidebar.write(f"{ss.userdb['db_name']}")
            pass
        except Exception as e:
            st.write(f"Connection failed: {e}")
else:
    st.markdown('### You have the connection to')
    st.table(ss.userdb)

st.divider()

# DB信息写入session_state -》 可根据需求添加
if ss.userdb['conn']:
    ss.db = localsqlite(ss.userdb['db_name']).conn()
    ss.alltables = list(ss.db.metadata.tables.keys())

# 复选table
if ss.userdb['conn']:
    if 'tables' not in ss: 
        ss.tables = []
    ss.tables = st.multiselect("Select tables to work on:", ss.alltables, default=ss.tables)
    st.markdown('### These tables will be used')
    st.table(ss.tables)
