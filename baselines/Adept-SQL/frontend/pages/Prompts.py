import streamlit as st
from streamlit import session_state as ss
#####################
#####################################################
st.title("Create your Prompts")

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
    