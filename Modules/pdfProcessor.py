# pdfProcessor.py
import google.generativeai as genai
import streamlit as st


""" takes input of PDFs, model,DB details and ingestion prompt and
    gives output of triplets of relationships and 
    entities that needs top be stored in DB """

def process_pdf_and_store(uploaded_file_object, graph_db,\
                           model, ingestion_prompt):

    st.toast(f"Step 1: Reading '{uploaded_file_object.name}'...")

    # 1. Read the file's bytes directly from the uploaded object
    pdf_bytes = uploaded_file_object.getvalue()

    # 2. Prepare the file data for the API call
    # We no longer upload the file first. We will send it
    # "inline" with the prompt.
    pdf_file_data = {"mime_type": "application/pdf", "data": pdf_bytes}

    st.toast(
        "Step 2: Extracting entities and relationships with Gemini..."
        " This may take a moment."
    )
    try:
        # 3. Send the prompt AND the file data in one go
        # The model.generate_content call now takes a list
        # containing the prompt string and the file data object.
        response = model.generate_content([ingestion_prompt, pdf_file_data])

        # Process the response to get triples (remains the same)
        lines = response.text.strip().split("\n")
        triples = []
        for line in lines:
            parts = line.split("|")
            if len(parts) == 3:
                e1 = parts[0].strip().strip("'\"")
                rel = parts[1].strip().strip("'\"")
                e2 = parts[2].strip().strip("'\"")
                if e1 and rel and e2:
                    triples.append((e1, rel, e2))

        if not triples:
            st.warning(
                "Could not extract any \
                       structured data from the document."
            )
            return

        st.toast(
            f"Step 3: Storing {len(triples)}\
                  relationships in the knowledge graph."
        )
        graph_db.add_triples(triples)

    except Exception as e:
        st.error(f"An error occurred during the Gemini API call: {e}")
        raise
