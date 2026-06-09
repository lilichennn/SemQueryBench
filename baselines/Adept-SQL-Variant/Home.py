import streamlit as st
from streamlit import session_state as ss
st.logo("logobar.png",icon_image= 'logonew.png', size = 'large')
st.set_page_config(layout="wide")
#
st.title('Welcome to ADEPT-SQL!👋')

st.markdown(
"""
*Welcome for trying out the DEMO version of ADEPT-SQL!*


**ADEPT-SQL is designed for High-Complexity Text2SQL tasks, and its official version have been deployed on multiple REAL-WORLD Industry databases.**
"""
)

st.divider()
st.header('How to Use 📝')
st.markdown(
"""
*IMPORTANT: This is an online demo depolyed based on Github repository.*

*The system requries LLM and Embedding models to run, therefore, to get full experience, PLEASE pull the github and put your models in the correct directory.* 

1️⃣ Start with the **Settings** page. With the perfect **Settings**, ADEPT-SQL is able to achieve stunning results~

2️⃣ Look into **Review**, to see infomations you justed recorded.

3️⃣ Go to the **Start Chat**, and explore your database! BUT make sure you get all these sidebar status:

"""
)

st.image("sidebar.png" )


st.divider()

st.markdown(
"""
- To Get the full experience please Check out [Github](https://github.com/lilichennn/ADEPT-SQL-DEMO)
- Contact [Email](chenyongnan@cnpc.com.cn) 
""" 
)
