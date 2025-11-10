# app.py
import streamlit as st
from Modules.appConfig import NEO4J_URI, NEO4J_USERNAME,\
      NEO4J_PASSWORD, DB_NAME, configure_apis
from Modules.appConstants import DEFAULT_INGESTION_PROMPT
from Modules.graphDB import Neo4jConnection
from Modules.llmWrapper import ModelWrapper
from Modules.appUi import render_sidebar, render_chat_interface

# Page Configuration
st.set_page_config(page_title="Document Knowledge Graph", layout="wide")
st.title("📄 Document Knowledge Graph Q&A")

# API and DB Initialization
configure_apis()


@st.cache_resource
def get_db_connection():
    # Caches the Neo4j database connection
    try:
        return Neo4jConnection(
            uri=NEO4J_URI,
            user=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            database=DB_NAME,
        )
    except Exception as e:
        st.error(f"Failed to connect to Neo4j: {e}")
        st.stop()


db_conn = get_db_connection()


# Session State Initialization
def initialize_session_state():
    # Initializes session state variables if they don't exist.
    if "ingestion_prompt" not in st.session_state:
        st.session_state.ingestion_prompt = DEFAULT_INGESTION_PROMPT
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "graph_built" not in st.session_state:
        st.session_state.graph_built = db_conn.check_if_graph_exists()


initialize_session_state()

# Render the sidebar and get the user's model choice
model_choice = render_sidebar(db_conn)

# Initialize the model wrapper based on the choice
model = ModelWrapper(model_choice)

# Render the main chat interface
render_chat_interface(db_conn, model_choice, model)
