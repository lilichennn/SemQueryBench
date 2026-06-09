import streamlit as st
from streamlit import session_state as ss
import pandas as pd

#####################################################
st.title("Add some Special QA pairs")
if "qa_pairs" not in st.session_state:
    ss.qa_pairs = pd.DataFrame(columns=["question", "answer"])

st.header("Saved QA pairs")
st.dataframe(ss.qa_pairs,hide_index=True,use_container_width = True)


st.header("Add new QA pairs")

Q = st.text_input("Enter the question", key="q")
A = st.text_area("Enter the SQL", key="a")

if st.button("Add", key="add"):
    ss.qa_pairs = pd.concat([ss.qa_pairs, pd.DataFrame({"question": [Q], "answer": [A]})])


