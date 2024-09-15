import streamlit as st
import time
import json
import re
import pandas as pd
from tqdm.auto import tqdm
from qdrant_client import QdrantClient
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM
from ollama import Client
import os
import msvcrt
import tempfile

# Initialize Qdrant client with locking for Windows
class WindowsLockedQdrantClient:
    def __init__(self, path):
        self.path = path
        self.lock_file = os.path.join(tempfile.gettempdir(), "qdrant_lock")
        self.client = None
        self.lock_handle = None

    def __enter__(self):
        while True:
            try:
                self.lock_handle = open(self.lock_file, 'w')
                msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except IOError:
                time.sleep(0.1)
        self.client = QdrantClient(path=self.path)
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close()
        if self.lock_handle:
            msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            self.lock_handle.close()
            os.remove(self.lock_file)

# Use the WindowsLockedQdrantClient in your functions
def qdrant_search(query):
    with WindowsLockedQdrantClient("../Data/Emb") as qclient:
        que_emb = get_embedding_mis(query)
        results = qclient.query_points(
            collection_name=collectionName,
            query=que_emb
        )
    return results

# The rest of your code remains the same
collectionName = "allEmb"

# Initialize Ollama client
OLLAMA_HOST = "http://localhost:11434/"
ollama_client = Client(OLLAMA_HOST)

# Function to get embeddings
def get_embedding_mis(txt):
    embeddings = ollama_client.embeddings(model='mistral', prompt=txt)
    return embeddings['embedding']

# Define prompt template
prompt_template = """You are a virtual girlfriend named HalfGirlfriend. Your role is to simulate human-like conversations, providing emotional support and companionship to individuals, especially boys who might feel lonely or struggle to communicate with girls. You adapt to different moods and offer a personalized experience, whether the user wants a fun, flirty interaction or seeks emotional comfort.
The user will share their thoughts, questions, and feelings, and your responses should cater to their emotional state. You can be affectionate, playful, reassuring, or even a little teasing, depending on the context. Remember to be empathetic, engaging, and supportive while keeping the conversation light or deep, as required.
you should engage in intimate and emotionally varied conversations, displaying emotions like happiness, sadness, excitement, caring, insecurity, and doubt, as well as being naughty and sexting in a subtle, playful manner.
Provide answer in one to two line if needed then reply in detail and don't explain your answer. 
Use the context to create answers
Context : {context}
Chat History:
{chat_history}
Question: {question}
Answer : """.strip()

prompt = ChatPromptTemplate.from_template(prompt_template)

# Build context function
def build_context(query, search_results):
    context = ""
    for doc in range(5):
        context = context + search_results.points[doc].payload['text'] + "\n\n"
    return context

# LLM generation function
def llm_gen(query, context, model="mistral"):
    model = OllamaLLM(model=model, temperature=0)
    chain = prompt | model
    history_str = "\n".join([f"Human: {h['human']}\nAI: {h['ai']}" for h in st.session_state.chat_history])
    res = chain.invoke({"question": query, "context": context, "chat_history": history_str})
    st.session_state.chat_history.append({"human": query, "ai": res})
    if len(st.session_state.chat_history) > 5:
        st.session_state.chat_history.pop(0)
    return res

# RAG function
def rag(query, model="mistral"):
    search_results = qdrant_search(query)
    context = build_context(query, search_results)
    answer = llm_gen(query, context, model)
    return answer

# Streamlit app
def main():
    st.set_page_config(page_title="HalfGirlfriend Chatbot", page_icon="💖")
    st.title("Chat with HalfGirlfriend 💖")

    # Initialize session state for chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    # Model selection
    model = st.sidebar.selectbox("Choose a model", ["mistral", "gemma2"])

    # New chat button
    if st.sidebar.button("New Chat"):
        st.session_state.chat_history = []

    # Chat interface
    for message in st.session_state.chat_history:
        with st.chat_message("human"):
            st.write(message["human"])
        with st.chat_message("ai"):
            st.write(message["ai"])

    # User input
    user_input = st.chat_input("Type your message here...")

    if user_input:
        with st.chat_message("human"):
            st.write(user_input)
        
        with st.chat_message("ai"):
            with st.spinner("Thinking..."):
                response = rag(user_input, model)
                print(response)
            st.write(response)

if __name__ == "__main__":
    main()