# appConfig.py
import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv

"""attempts to load from Streamlit secrets first, 
then falls back to a .env file"""
try:
    DB_NAME = st.secrets["DB_NAME"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    CLAUDE_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
    GEMINI_MODEL = st.secrets["GEMINI_MODEL"]
    OPENAI_MODEL = st.secrets["OPENAI_MODEL"]
    CLAUDE_MODEL = st.secrets["CLAUDE_MODEL"]
    NEO4J_URI = st.secrets["NEO4J_URI"]
    NEO4J_USERNAME = st.secrets["NEO4J_USERNAME"]
    NEO4J_PASSWORD = st.secrets["NEO4J_PASSWORD"]

except (KeyError, AttributeError):
    load_dotenv()
    DB_NAME = os.getenv("DB_NAME")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL")
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

"""Configure APIs"""


def configure_apis():
    """Validates and configures the Gemini API."""
    if not GEMINI_API_KEY:
        st.error(
            "Gemini API key is required for PDF ingestion. "
            "Please set it in secrets or .env."
        )
        st.stop()
    genai.configure(api_key=GEMINI_API_KEY)
