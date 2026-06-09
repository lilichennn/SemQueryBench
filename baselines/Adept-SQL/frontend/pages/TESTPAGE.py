import streamlit as st
import numpy as np
import pandas as pd

items= [1,2,3,4]

def get_new_values_list():
    st.write(values) # < returns list before removal

values = st.multiselect('issue', items, items, on_change=get_new_values_list)

st.write(values)