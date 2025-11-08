# app.py
import streamlit as st
import os
from graph_db import Neo4jConnection
from pdf_processor import process_pdf_and_store
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI
import anthropic
from Questions import QUESTIONS


# --- Load secrets ---
# try:

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

# except (KeyError, AttributeError):
#     load_dotenv()

#     DB_NAME = os.getenv["DB_NAME"]
#     GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
#     OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
#     CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
#     GEMINI_MODEL = os.getenv("GEMINI_MODEL")
#     OPENAI_MODEL = os.getenv("OPENAI_MODEL")
#     CLAUDE_MODEL = os.getenv("CLAUDE_MODEL")
#     NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
#     NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
#     NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

if not GEMINI_API_KEY:
    st.error(
        "Gemini API key is required for PDF ingestion. Please set it in secrets or .env."
    )
    st.stop()
genai.configure(api_key=GEMINI_API_KEY)


# Model Wrapper
class ModelWrapper:
    def __init__(self, provider: str): 
        self.provider = provider.lower()

    def generate(self, prompt: str) -> str:
        if "gemini" in self.provider:
            # Updated model name
            model = genai.GenerativeModel(GEMINI_MODEL)
            return model.generate_content(prompt).text

        elif "openai" in self.provider:
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                # Updated model name
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content.strip()

        elif "claude" in self.provider:
            client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
            resp = client.messages.create(
                # Updated model name
                model=CLAUDE_MODEL,
                max_tokens=10240,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")


# Caching & DB
@st.cache_resource
def get_db_connection():
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


# Default Prompts
DEFAULT_INGESTION_PROMPT = """
Based on the entire content of the provided PDF document, extract all key entities and their relationships.
An entity can be a person, organization, location, date, or a monetary value.
Present the output as a list of comma-separated values (CSV) with the format: 'ENTITY_1|RELATIONSHIP|ENTITY_2'.
The RELATIONSHIP should be a concise, active verb phrase formatted in snake_case_upper, like 'IMPOSED_FINE_ON' or 'IS_DIRECTOR_OF'.
Do not include a header row. Ensure all relevant relationships are extracted from the document.

Example Output:
'John Doe|IS_A|Director'
'XYZ Corp|IMPOSED_FINE_ON|ABC Ltd'
'ABC Ltd|WAS_FINED|Rs. 5 Lakh'
'SEBI|ISSUED_ORDER_ON|2023-04-15'
"""

# Streamlit UI
st.set_page_config(page_title="Document Knowledge Graph", layout="wide")
st.title("📄 Document Knowledge Graph Q&A")


def handle_question_click(question):
    st.session_state.user_input = question


#  Initialize the prompt in session state if it doesn't exist
if "ingestion_prompt" not in st.session_state:
    st.session_state.ingestion_prompt = DEFAULT_INGESTION_PROMPT

# Sidebar
with st.sidebar:

    st.subheader("Ingestion Settings")

    with st.form(key="prompt_form"):
        st.text_area(
            "PDF Ingestion Prompt",
            key="editable_prompt",
            value=st.session_state.ingestion_prompt,
            help="This prompt instructs the AI on how to extract information from the PDFs.",
        )

        if st.form_submit_button("Update Prompt"):
            st.session_state.ingestion_prompt = st.session_state.editable_prompt
            st.toast("✅ Prompt updated successfully!")

    uploaded_files = st.file_uploader(
        "Upload one or more PDFs", type="pdf", accept_multiple_files=True
    )

    if st.button("Process and Add to Graph"):
        if uploaded_files:
            graph_db = get_db_connection()
            model = genai.GenerativeModel("gemini-2.5-pro")

            progress_bar = st.progress(0)
            status_text = st.empty()
            total_files = len(uploaded_files)

            for i, uploaded_file in enumerate(uploaded_files, start=1):
                status_text.text(
                    f"Processing {uploaded_file.name} ({i}/{total_files})..."
                )
                try:
                    process_pdf_and_store(
                        uploaded_file,
                        graph_db,
                        model,
                        st.session_state.ingestion_prompt,
                    )
                    st.success(f"Added '{uploaded_file.name}' to the graph.")
                    st.session_state.graph_built = True
                except Exception as e:
                    st.error(f"Error processing '{uploaded_file.name}': {e}")

                progress_bar.progress(i / total_files)

            status_text.text("✅ All files processed.")
        else:
            st.warning("Please upload at least one PDF file.")

    st.divider()
    st.subheader("Query Settings")
    model_choice = st.selectbox(
        "Choose query model:",
        ["Google Gemini 2.5 Pro", "OpenAI GPT-4.1", "Anthropic Claude Sonnet 4.5"],
        index=1,
    )

    with st.container(border=True, height=380):
        for i, question in enumerate(QUESTIONS):
            st.button(
                question,
                key=f"q_btn_{i}",
                on_click=handle_question_click,
                args=(question,),
                use_container_width=True,
            )

# Chat Interface
if "graph_built" not in st.session_state:
    st.session_state.messages = []
    db_conn = get_db_connection()
    st.session_state.graph_built = db_conn.check_if_graph_exists()

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Unify input: either typed by user OR clicked question
user_input = None
if prompt := st.chat_input("Ask a question about the uploaded documents..."):
    user_input = prompt
elif "user_input" in st.session_state and st.session_state.user_input:
    user_input = st.session_state.pop("user_input")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    if not st.session_state.get("graph_built", False):
        response_text = "Graph is empty. Please upload and process PDFs first."
        with st.chat_message("assistant"):
            st.warning(response_text)
        st.session_state.messages.append(
            {"role": "assistant", "content": response_text}
        )
    else:
        with st.chat_message("assistant"):
            with st.spinner(f"Querying graph with {model_choice}..."):
                try:
                    graph_db = get_db_connection()
                    model = ModelWrapper(model_choice)

                    # Step 1: Generate Cypher query
                    st.toast("🔄 Generating Cypher query...")
                    cypher_query = graph_db.generate_cypher(user_input, model)

                    if not cypher_query:
                        response_text = "Could not generate a valid query."
                        st.error(response_text)
                    else:
                        # Step 2: Run query
                        st.toast("🔍 Querying the graph...")
                        context_data = graph_db._execute_read(cypher_query)

                        if not context_data:
                            response_text = "No matching data found."
                            st.warning(response_text)
                        else:
                            # Step 3: Synthesize final answer
                            st.toast("✍️ Generating final answer...")
                            context_str = "\n".join(
                                [str(item) for item in context_data]
                            )
                            system_prompt = f"""
                            You are a helpful assistant. 
                            Use ONLY the retrieved graph data to answer.

                            Retrieved Data:
                            {context_str}

                            Question: {user_input}
                            """
                            response_text = model.generate(system_prompt)
                            st.markdown(response_text)

                            # Show Gemini-processed graph
                            st.subheader("Relevant Graph Snippet")
                            graph_db.visualize_subgraph(user_input, st, model)

                except Exception as e:
                    response_text = f"Error: {e}"
                    st.error(response_text)

        st.session_state.messages.append(
            {"role": "assistant", "content": response_text}
        )
