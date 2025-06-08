from openai import OpenAI
from dotenv import load_dotenv
import streamlit as st
from swarm import Swarm
from agents import main_agent

load_dotenv()

client = OpenAI()

if 'messages' not in st.session_state:
    st.session_state.messages = []

st.title("Google Calendar Agent")

# Initialize the chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("What is your message?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        swarm_client = Swarm()
        response = swarm_client.run(
            agent=main_agent,
            debug=False,
            messages=st.session_state.messages
        )
        st.markdown(response.messages[-1]['content'])
        st.session_state.messages.append({'role': 'assistant', 'content': response.messages[-1]['content']})
