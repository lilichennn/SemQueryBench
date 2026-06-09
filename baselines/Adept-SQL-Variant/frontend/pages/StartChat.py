import streamlit as st
from streamlit import session_state as ss


# sidebar setting
if 'tables' in ss and len(ss.tables)>0:
    st.sidebar.checkbox("DB ready", value=True, key="DBcheck")

if 'speSQL' in ss and 'selfSQL' in ss and 'answerGen' in ss:
    st.sidebar.checkbox("Prompts ready", value=True, key="PPcheck")


st.title("Echo Bot")
st.write(f"""
You are asking questions to Database: {ss.userdb['db_name']}
"""
)
# Initialize chat history
if "messages" not in st.session_state:
    ss.messages = []

# Display chat messages from history on app rerun
for message in ss.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("What is up?"):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    ss.messages.append({"role": "user", "content": prompt})

    response = f"Echo: {prompt}"
    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        st.markdown(response)
    # Add assistant response to chat history
    ss.messages.append({"role": "assistant", "content": response})