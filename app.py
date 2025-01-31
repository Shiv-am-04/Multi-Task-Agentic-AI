from main_workflow import graph
import streamlit as st
from datetime import datetime
import time
import os
import tempfile
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel,Field
from typing import Literal
from invoking import get_audio_output_from_graph,get_labels_output_from_graph
from invoking import get_mail_output_from_graph,get_output_from_graph,get_web_output_from_graph

load_dotenv()

groq_api_key = os.getenv('GROQ_API_KEY')

llm = ChatGroq(model='llama-3.3-70b-versatile',api_key=groq_api_key)

class Node_Selector(BaseModel):
    node : Literal['send_mail','schedule_meeting','sort_mail','web_search','transcribe'] = Field(
        ...,
        description = 'Given user query based on which the node among these four should be selected.Removing labels is also considered in sort_mail'
    )

structured_llm = llm.with_structured_output(Node_Selector)

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Repetative MultiTask Agent", page_icon="🤖", layout="wide")

# --- CUSTOM CSS FOR STYLING ---
st.markdown("""
    <style>
        /* Background Styling */
        body {
            background-color:rgb(218, 222, 233);
        }
        .main {
            background: linear-gradient(135deg,rgb(226, 224, 238),rgb(222, 220, 232));
            padding: 2rem;
            border-radius: 10px;
            color: white;
        }
        .title {
            font-size: 2.5rem;
            font-weight: bold;
            text-align: center;
            color: #f8f9fa;
        }
        .subtitle {
            font-size: 1.2rem;
            text-align: center;
            color: #d1d1d1;
            margin-bottom: 20px;
        }
        .input-box {
            border: 2px solid #0d6efd;
            border-radius: 10px;
            padding: 10px;
            background-color: white;
            font-size: 1rem;
            color: black;
        }
        .submit-btn {
            background-color: #007bff;
            color: white;
            padding: 12px 20px;
            border-radius: 5px;
            border: none;
            font-size: 1rem;
        }
        .submit-btn:hover {
            background-color: #0056b3;
            cursor: pointer;
        }
        .success-box {
            background-color:rgb(20, 141, 146);
            padding: 10px;
            border-radius: 5px;
            color: white;
            font-size: 1rem;
        }
        .result-box {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.1);
            color: black;
        }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown("<h1 class='title'>🚀 Agentic AI</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>An intelligent AI agent that automates email handling, scheduling, web searching, and transcription.</p>", unsafe_allow_html=True)

# --- USER QUERY INPUT ---
query = st.text_area("💬 Type your query here...", placeholder="e.g., Schedule a meeting with John at 5 PM today.")
print(query)
Node = structured_llm.invoke(query)

if query:
    if Node.node == 'transcribe':
        file = st.file_uploader('upload_here')
        if file:
            file_ext = os.path.splitext(file.name)[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                temp_file.write(file.read())
                temp_file_path = temp_file.name  
                print(temp_file_path)
            if st.button("Submit", key="submit-btn"):
                if query.strip():
                    st.session_state["loading"] = True
                    with st.spinner("🤖 Processing your request..."):
                        time.sleep(2)  # Simulate AI processing

                        response = get_audio_output_from_graph(temp_file_path,query)

                        st.session_state['response'] = response

                        st.session_state["action"] = "transcribe_audio"

    elif Node.node == 'send_mail':
        file = st.file_uploader('upload attachment here')
        if file:
            file_ext = os.path.splitext(file.name)[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                temp_file.write(file.read())
                temp_file_path = temp_file.name  
                print(temp_file_path)
            if st.button("Submit", key="submit-btn"):
                if query.strip():
                    st.session_state["loading"] = True
                    with st.spinner("🤖 Processing your request..."):
                        time.sleep(2)  # Simulate AI processing

                        response = get_mail_output_from_graph(query,temp_file_path)

                        st.session_state['response'] = response

                        st.session_state["action"] = "send_mail"

                    st.session_state["loading"] = False
        else:
            if st.button("Submit", key="submit-btn"):
                if query.strip():
                    st.session_state["loading"] = True
                    with st.spinner("🤖 Processing your request..."):
                        time.sleep(2)  # Simulate AI processing

                        response = get_mail_output_from_graph(query)

                        st.session_state['response'] = response

                        st.session_state["action"] = "send_mail"

                    st.session_state["loading"] = False

    elif Node.node == 'sort_mail':
        if st.button("Submit", key="submit-btn"):
            if query.strip():
                st.session_state["loading"] = True
                with st.spinner("🤖 Processing your request..."):
                    time.sleep(2)  # Simulate AI processing

                    criteria = st.text_input('***criteria***',placeholder='sender or subject based on which labels to be created or have created earlier')

                    if criteria:
                        response = get_labels_output_from_graph(query,criteria)

                        st.session_state['response'] = response

                        st.session_state["action"] = "sort_mail"

                st.session_state["loading"] = False
                
    elif Node.node == 'web_search':
        if st.button("Submit", key="submit-btn"):
            if query.strip():
                st.session_state["loading"] = True
                with st.spinner("🤖 Processing your request..."):
                    time.sleep(2)  # Simulate AI processing

                    response = get_web_output_from_graph(query)

                    st.session_state['response'] = response

                    st.session_state["action"] = "web_search"

                st.session_state["loading"] = False   

    else:
        if st.button("Submit", key="submit-btn"):
            if query.strip():
                st.session_state["loading"] = True
                with st.spinner("🤖 Processing your request..."):
                    time.sleep(2)  # Simulate AI processing

                    response = get_output_from_graph(query)

                    st.session_state['response'] = response

                    st.session_state["action"] = "schedule_meeting"

                st.session_state["loading"] = False   
                

# --- FUNCTION EXECUTION & UI RESPONSE ---
if "action" in st.session_state:
    action = st.session_state["action"]

    st.markdown("<div class='main'>", unsafe_allow_html=True)

    if action == "send_email":
        st.markdown("<div class='success-box'>📧 Email Sent Successfully!</div>", unsafe_allow_html=True)

    elif action == "sort_mail":
        st.markdown("<div class='success-box'>📂 Emails Sorted Successfully!</div>", unsafe_allow_html=True)

    elif action == "schedule_meeting":
        st.markdown("<div class='success-box'>📅 Meeting Scheduled Successfully!</div>", unsafe_allow_html=True)
        if 'response' in st.session_state:
            st.markdown(st.session_state['response'])

    elif action == "web_search":
        st.markdown("<div class='success-box'>🔍 Web Search Completed!</div>", unsafe_allow_html=True)
        st.success(st.session_state['response'])

    elif action == "transcribe_audio":
        st.markdown("<div class='success-box'>🎙️ Audio Transcription Completed!</div>", unsafe_allow_html=True)
        st.warning(st.session_state['response'])

    else:
        st.markdown("<div class='success-box' style='background-color: #dc3545;'>⚠️ Unknown Query: Please try again!</div>", unsafe_allow_html=True)


st.sidebar.markdown("---")
st.sidebar.markdown("🚀 **Powered by LangGraph & Streamlit**")
