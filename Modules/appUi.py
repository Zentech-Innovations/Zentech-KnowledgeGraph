# appUi.py
import streamlit as st
from Modules.Constants import QUESTIONS, DEFAULT_INGESTION_PROMPT
from Modules.pdfProcessor import process_pdf_and_store
import google.generativeai as genai
from Modules.loadConfig import (
    GEMINI_MODEL,
    OPENAI_MODEL,
    CLAUDE_MODEL,
)


def handle_question_click(question):
    # Callback to set the user input when a question button is clicked.
    st.session_state.user_input = question


def render_sidebar(db_connection):
    with st.sidebar:
        st.subheader("Ingestion Settings")

        with st.form(key="prompt_form"):
            st.text_area(
                "PDF Ingestion Prompt",
                key="editable_prompt",
                value=st.session_state.ingestion_prompt,
                help="This prompt instructs the AI on how to \
                    extract information from the PDFs.",
            )
            if st.form_submit_button("Update Prompt"):
                st.session_state.ingestion_prompt =\
                      st.session_state.editable_prompt
                st.toast("✅ Prompt updated successfully!")

        uploaded_files = st.file_uploader(
            "Upload one or more PDFs", type="pdf", accept_multiple_files=True
        )

        if st.button("Process and Add to Graph"):
            if uploaded_files:
                model = genai.GenerativeModel(GEMINI_MODEL)
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_files = len(uploaded_files)

                for i, uploaded_file in enumerate(uploaded_files, start=1):
                    status_text.text(
                        f"Processing \
                        {uploaded_file.name} ({i}/{total_files})..."
                    )
                    try:
                        process_pdf_and_store(
                            uploaded_file,
                            db_connection,
                            model,
                            st.session_state.ingestion_prompt,
                        )
                        st.success(
                            f"Added \
                                   '{uploaded_file.name}' to the graph."
                        )
                        st.session_state.graph_built = True
                    except Exception as e:
                        st.error(
                            f"Error processing \
                                 '{uploaded_file.name}': {e}"
                        )
                    progress_bar.progress(i / total_files)
                status_text.text("✅ All files processed.")
            else:
                st.warning("Please upload at least one PDF file.")

        st.divider()
        st.subheader("Query Settings")
        model_choice = st.selectbox(
            "Choose query model:",
            [GEMINI_MODEL, OPENAI_MODEL, CLAUDE_MODEL],
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
    return model_choice


def render_chat_interface(db_connection, model_choice, model_wrapper):
    # main chat interface and handles the Q&A logic
    # Display previous messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    """ imput - either typed by user OR clicked question"""
    user_input = None
    if prompt := st.chat_input\
        ("Ask a question about the uploaded documents..."):
        user_input = prompt
    elif "user_input" in st.session_state and st.session_state.user_input:
        user_input = st.session_state.pop("user_input")

    if user_input:
        st.session_state.messages.append({"role": "user", \
                                          "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        if not st.session_state.get("graph_built", False):
            response_text = \
                "Graph is empty. Please upload and process PDFs first."
            with st.chat_message("assistant"):
                st.warning(response_text)
            st.session_state.messages.append(
                {"role": "assistant", "content": response_text}
            )
        else:
            with st.chat_message("assistant"):
                with st.spinner(f"Querying graph with {model_choice}..."):
                    try:
                        # Step 1: Generate Cypher query
                        st.toast("🔄 Generating Cypher query...")
                        cypher_query = db_connection.generate_cypher(
                            user_input, model_wrapper
                        )

                        if not cypher_query:
                            response_text = "Could not generate a valid query."
                            st.error(response_text)
                        else:
                            # Step 2: Run query
                            st.toast("🔍 Querying the graph...")
                            context_data = db_connection\
                                .execute_read(cypher_query)

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
                                response_text = \
                                    model_wrapper.generate(system_prompt)
                                st.markdown(response_text)

                                # Show relevant graph snippet
                                st.subheader("Relevant Graph Snippet")
                                db_connection.visualize_subgraph(
                                    user_input, st, model_wrapper
                                )

                    except Exception as e:
                        response_text = f"Error: {e}"
                        st.error(response_text)

            st.session_state.messages.append(
                {"role": "assistant", "content": response_text}
            )

