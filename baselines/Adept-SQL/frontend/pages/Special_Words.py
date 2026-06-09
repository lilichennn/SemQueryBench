import streamlit as st
import pandas as pd
from streamlit import session_state as ss
#####################

#####################################################
st.title("Define some Special words")

if "specialword" not in st.session_state:
    ss.specialword = pd.DataFrame(columns=["Table","Column", "sampleWord"])

st.header("Saved word")
st.dataframe(ss.specialword,hide_index=True,use_container_width = True)

st.header("Select target table")
table = st.selectbox( "",ss.tables,
)
st.write("You selected:", table)

st.header("Select target columns")
columns = []
for column in ss.db.metadata.tables[table].columns:
    columns.append(column.name)
cols = st.multiselect( "", columns,columns[0:2],)
st.write("You selected:", cols)

if st.button("Add"):
    for col in cols:
        ss.specialword = pd.concat([ss.specialword, 
                                                pd.DataFrame({"Table": table, 
                                                            "Column": col, 
                                                            "sampleWord":"some words in this columns"}, index=[0])
                                                            ])
