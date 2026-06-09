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
st.logo("logo.png", size = 'large')
tabllm, tabdb, tabsql = st.tabs(['LLM', 'DataSource', 'Your SQLs'])

###################### llm TAB #######################
def llmactive():
    return ss.llm['active']


with tabllm:

    if "llm" not in ss : 
        st.sidebar.checkbox("LLM Connected 🥳", value=False)
        ss.llm = {}
    else:
        st.sidebar.checkbox("LLM Connected 🥳", value=llmactive) ### 用on_change = llmactive
        st.sidebar.write(ss.llm)

    ss.llm['name'] = st.text_input("Model Name")
    ss.llm['url'] = st.text_input("URL")
    ss.llm['token'] = st.text_input("API Key")
    ss.llm['active'] = False

    if st.button("Connect", icon=":material/mood:"):
        res = callLLM(ss.llm).init_prompt('When user ask who are you, answer:You are a Text2SQL expert.', 'Who are you?').call().get_response_content()
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
        height=700,
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=('Table'),
    )

    # Filter the dataframe using the temporary column, then drop the column
    selected_rows = edited_df[edited_df.Select]
    return selected_rows.drop('Select', axis=1)

with tabdb:
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
                st.sidebar.checkbox("DB Connected 🥳", value=ss.userdb['conn'])
                pass
            except Exception as e:
                st.write(f"Connection failed: {e}")
    else:
        st.sidebar.checkbox("DB Connected 🥳", value=ss.userdb['conn'])
        st.markdown(f'''
 Connecting to        
                                
    - Database Type:  {ss.userdb['option']}

    - Database Name:  {ss.userdb['db_name']}''')    
        if st.button("Reconnect"):
            del st.session_state['userdb']
            st.rerun()


    st.divider()

    # DB信息写入session_state -》 可根据需求添加
    if ss.userdb['conn']:

        ss.dbconn = localsqlite(ss.userdb['sqlite_path']).conn()

        ss.alltables = list(ss.dbconn.metadata.tables.keys())
        ss.alltablesdf = pd.DataFrame(
            {"Table":ss.alltables#,  "Description":[" "] * len(ss.alltables)
             } )

        ss.alltable_cols = {'Table':[], 'Column':[]#, 'Description':[]
                            }
        for table in ss.alltables:
            columns = ss.dbconn.metadata.tables[table].columns.keys()
            for i in range(len(columns)):
                ss.alltable_cols['Table'].append(table)
                ss.alltable_cols['Column'].append(list(columns)[i]) 
                #ss.alltable_cols['Description'].append('')
        ss.alltable_colsdf = pd.DataFrame(ss.alltable_cols)

        #st.write(ss.alltable_colsdf)

    #复选table 
    if 'selected_table_colsdf' not in ss:
        ss.selected_table_colsdf = pd.DataFrame(columns = ['Table','Table Description','Column','Columns Description'])

    if ss.userdb['conn']:

        col4table, col4col = st.columns(2)

        with col4table:
            st.subheader("Choose Tables")
            ss.tableselection = dataframe_with_selections(ss.alltablesdf)
            ss.selectedtables = list(ss.tableselection['Table'])

        with col4col:

            newtable = None 
            if len(ss.selectedtables) == 1:
                newtable = ss.selectedtables[0]
            elif len(ss.selectedtables) > 1:
                newtable = ss.selectedtables[-1]


            if newtable:
                st.subheader('Columns of "'+ newtable+'"')
            else:
                st.subheader("Choose Columns")
            ss.colselection = dataframe_with_selections(ss.alltable_colsdf[ss.alltable_colsdf['Table'] == newtable][['Column']])


        ss.selected_table_colsdf = pd.concat([ss.selected_table_colsdf,
                                                pd.DataFrame({
                                                    'Table':[newtable]*len(ss.colselection),
                                                    'Table Description':['']*len(ss.colselection),
                                                    'Column':list(ss.colselection['Column']),
                                                    'Columns Description':['']*len(ss.colselection)
                                                    })
                                                ]
                                            ).drop_duplicates()
                
        st.subheader("Summary")

        edited_df = st.data_editor(
            ss.selected_table_colsdf,
            hide_index=True,
            width=1000,
            height=300,
            disabled=('Table','Column'),
            num_rows='dynamic'
        )

        if st.button('Clear'):
            ss.selected_table_colsdf = pd.DataFrame(columns = ['Table','Table Description','Column','Columns Description'])
            st.rerun()
        if st.button('Save'):
            st.success('Data Saved!')


###################### sql TAB ##################
with tabsql:
    if "qa_pairs" not in ss:
        ss.qa_pairs = pd.DataFrame(columns=["question", "answer"])


    st.header("Add a QS pair")

    Qstr = st.text_input("Enter the question", key="q")
    Astr = st.text_area("Enter the SQL", key="a")

    if st.button("Add"):
        if Qstr not in set(ss.qa_pairs['question']):
            ss.qa_pairs = pd.concat([ss.qa_pairs, pd.DataFrame({"question": [Qstr], "answer": [Astr]})])
            st.success('QS pair Added')
        else:
            st.error('Question MUST be a NEW one!')

    st.header("Check and Save your QS pairs")
    st.data_editor(ss.qa_pairs,
                    hide_index=True,
                    use_container_width = True,
                    num_rows='dynamic')

