import os,sys
pythonon_path = os.path.dirname('../')
sys.path.append(pythonon_path)
from call_llm import callLLM

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine, MetaData, select,text
from urllib.parse import quote_plus


import streamlit as st
from streamlit import session_state as ss
import pandas as pd

#################### PAGE START ######################
st.title("Define your Assistant ~")


tabllm, tabds, tabsql, tabptpt = st.tabs(['LLM', 'DataSource', 'Your SQLs', 'Prompts'])

###################### llm TAB #######################
with tabllm:

    if "llm" not in ss:
        ss.llm = {}

    ss.llm['name'] = st.text_input("Model Name")
    ss.llm['url'] = st.text_input("URL")
    ss.llm['token'] = st.text_input("API Key")


    if st.button("Connect", icon=":material/mood:"):
        res = callLLM(ss.llm).init_prompt('When user ask who are you, answer:You are a Text2SQL expert.'
                                          ,'Who are you?').call().get_response_content()
        if res == 'LLM Fail':
            st.error("Connection FAIL, please check the form")
            ss.llm['active'] = False
        else:
            st.success("Connection success!")
            st.markdown(f'''
                        ------------------------
                        TEST RESPONSE

                        - Who are you?
                         
                        - {res}
                        ''')
            ss.llm['active'] = True
            st.sidebar.checkbox("LLM Connected 🥳", value=ss.llm['active'], key="llmcheck")



################### DataSource Tab ##################
# Connect to Local SQLite
class localsqlite():
    def __init__(self, db_path):
        self.db_path = db_path
    
    def conn(self):
        self.connection = create_engine(f"sqlite:///{self.db_path}").connect()
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.connection)
        return self
    
def dataframe_with_selections(df):
    df_with_selections = df.copy()
    df_with_selections.insert(0, "Select", False)

    # Get dataframe row-selections from user with st.data_editor
    edited_df = st.data_editor(
        df_with_selections,
        hide_index=True,
        width=1000,
        height=400,
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=('Table'),
    )

    # Filter the dataframe using the temporary column, then drop the column
    selected_rows = edited_df[edited_df.Select]
    return selected_rows.drop('Select', axis=1)

with tabds:
    # DB信息填写表单
    if 'userdb' not in ss or ss.userdb['conn'] == False:
        ss.userdb = {}
        ss.userdb['option'] = st.pills(
            "Database Type",
            options=['MySQL', 'Sqlite', 'Turtorial DB'],
            default='Turtorial DB',
            selection_mode="single",
            )
        if ss.userdb['option'] == 'MySQL':
            ss.userdb['ip'] = st.text_input("IP")
            ss.userdb['port'] = st.text_input("Port")
            ss.userdb['user_name']= st.text_input("User name")
            ss.userdb['user_password'] = st.text_input("Password")
            ss.userdb['db_name'] = st.text_input("Database")
            ss.userdb['conn'] = False

        if ss.userdb['option'] == 'Sqlite':
            ss.userdb['sqlite_path'] = st.text_input("Database Location")
            ss.userdb['db_name'] = ss.userdb['sqlite_path'].split('/')[-1]
            ss.userdb['conn'] = False

        if ss.userdb['option'] == 'Turtorial DB':
            ss.userdb['sqlite_path'] = "./sqlite/cre_Drama_Workshop_Groups.sqlite"
            ss.userdb['db_name'] = ss.userdb['sqlite_path'].split('/')[-1]
            ss.userdb['conn'] = False


    # 连接DB / 显示链接信息
    if not ss.userdb['conn']:
        if st.button("Connect"):
            try:
                db = localsqlite(ss.userdb['sqlite_path']).conn()
                ss.userdb['conn'] = True
                st.sidebar.checkbox("DB Connected 🥳", value=ss.userdb['conn'], key="dbcheck")
                pass
            except Exception as e:
                st.write(f"Connection failed: {e}")
    else:
        st.sidebar.checkbox("DB Connected 🥳", value=ss.userdb['conn'], key="dbcheck")
        st.markdown(f'''
 Connecting to        
                                
    - Database Type:  {ss.userdb['option']}

    - Database Name:  {ss.userdb['db_name']}''')    

    st.divider()
    st.write('We have all these tables and columns:')

    # DB信息写入session_state -》 可根据需求添加
    if ss.userdb['conn']:

        ss.dbconn = localsqlite(ss.userdb['sqlite_path']).conn()

        ss.alltables = list(ss.dbconn.metadata.tables.keys())
        ss.alltablesdf = pd.DataFrame(
            {"Table":ss.alltables, "Description":[" "] * len(ss.alltables)}
                                      )

        ss.alltable_cols = {'Table':[], 'Column':[], 'Description':[]}
        for table in ss.alltables:
            columns = ss.dbconn.metadata.tables[table].columns.keys()
            for i in range(len(columns)):
                ss.alltable_cols['Table'].append(table)
                ss.alltable_cols['Column'].append(list(columns)[i]) 
                ss.alltable_cols['Description'].append('')
        ss.alltable_colsdf = pd.DataFrame(ss.alltable_cols)



    #复选table 
    if ss.userdb['conn']:
        tableselection = dataframe_with_selections(ss.alltablesdf)
        colselection = dataframe_with_selections(ss.alltable_colsdf)
        st.write("Your selection:")
        st.write(tableselection)
        st.write(colselection)






###################### sql TAB ##################
with tabsql:
    st.header("Add some Special QA pairs")
    if "qa_pairs" not in ss:
        ss.qa_pairs = pd.DataFrame(columns=["question", "answer"])

    st.header("Saved QA pairs")
    st.dataframe(ss.qa_pairs,hide_index=True,use_container_width = True)


    st.header("Add new QA pairs")

    Q = st.text_input("Enter the question", key="q")
    A = st.text_area("Enter the SQL", key="a")

    if st.button("Add", key="add"):
        ss.qa_pairs = pd.concat([ss.qa_pairs, pd.DataFrame({"question": [Q], "answer": [A]})])

#################### Prompt TAB ##################
with tabptpt:
    st.header("Create your Prompts")
    #####################
    ss.speSQL = st.text_area(
        "Prompt for Generat Special SQL",height=200,value='''  
    #Role#
    You are a MySQL engineer who is skilled at writing new SQL statements based on imitating similar SQL statements, and can replace special terms and time points in SQL according to actual situations.
    Now, please write a MySQL statement to answer the user's question, following the example below.

    #Constraint#
    1. The professional terms mentioned in the [Reminder] must be used in the SQL answer and should not be changed.
    2. Create a grammatically correct MySQL code following the example below.
    3. The answer SQL needs to be readable, and you need to wrap lines in appropriate places.
    4. Please check the correctness of the SQL and be careful not to make mistakes in the dependency relationships of fields.
    5. Your output must be in plain text format.
    ''',
    )

    st.write(f"You wrote {len(ss.speSQL)} characters.")

    st.button("Save",key="save1")

    st.divider()

    #####################
    ss.selfSQL = st.text_area(
        "Prompt for Generat Special SQL",height=200,value='''   
    #Role#
    You are a MySQL engineer in the company, and you are very familiar with the table information in the database. You are also very familiar with the meaning of tables, the meaning of fields, and the types of fields. You serve frontline personnel in the company's production and operation. When they have a need to query data from the database, you can write the correct SQL statements based on their questions.

    #Task#
    You now have a query request from a production and operation personnel, who has informed you of the problem and also told you which field corresponds to the professional term in this question. You need to use the table structure information below to write a correct SQL statement.

    #Constraint#
    1. The professional terms mentioned in the [Reminder] must be used in the SQL answer and should not be changed.
    2. Create a grammatically correct MySQL code following the example below.
    3. The answer SQL needs to be readable, and you need to wrap lines in appropriate places.
    4. Please check the correctness of the SQL and be careful not to make mistakes in the dependency relationships of fields.
    5. You only need to write SQL without providing reasoning or explanations to the user.
    6. You need to ensure that the output can be executed by pd.read_sql_query().
    ''',
    )

    st.write(f"You wrote {len(ss.selfSQL)} characters.")

    st.button("Save",key="save2")

    st.divider()

    ##################
    ss.answerGen = st.text_area(
        "Prompt for Generat Special SQL",height=200,value='''  
    #Role#
    Now, you are a task assistant who excels at organizing the task process for your users. Your tone is objective and instructive.

    #Task#
    Your backend system program has completed a Text2SQL task and performed several tasks: user problem handling ->matching the processed problem with pre stored complex SQL ->if it matches, requiring the large model to write a new SQL according to the pre stored SQL; if it does not match, the large model will generate SQL on its own ->sending the SQL to the user specified database to run and obtain data

    #Requirement#
    1. Explain the structure of SQL statements appropriately
    2. Keep the word count within 200 words
    ''',
    )

    st.write(f"You wrote {len(ss.answerGen )} characters.")

    st.button("Save",key="save3")



    # sidebar setting
    if 'tables' in ss and len(ss.tables)>0:
        st.sidebar.checkbox("DB ready", value=True, key="DBcheck")

    if 'speSQL' in ss and 'selfSQL' in ss and 'answerGen' in ss:
        st.sidebar.checkbox("Prompts ready", value=True, key="PPcheck")
        