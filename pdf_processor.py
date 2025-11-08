# pdf_processor.py
import google.generativeai as genai
import streamlit as st
import tempfile
import os

# The function now accepts 'ingestion_prompt' as an argument
def process_pdf_and_store(uploaded_file_object, graph_db, model, ingestion_prompt):

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        # Write the uploaded file's content to the temporary file
        tmp_file.write(uploaded_file_object.getvalue())
        pdf_path = tmp_file.name # Get the path to the temporary file

    st.toast(f"Step 1: Uploading '{uploaded_file_object.name}' to Gemini's File API...")
    
    try:
        # Use the path of the temporary file to upload
        gemini_pdf_file = genai.upload_file(
            path=pdf_path,
            display_name=uploaded_file_object.name,
        )
        st.toast(f"Successfully uploaded '{uploaded_file_object.name}'.")

    except Exception as e:
        st.error(f"An error occurred while uploading the file: {e}")
        raise # Stop the process if upload fails
    finally:
        os.remove(pdf_path)

    st.toast("Step 2: Extracting entities and relationships with Gemini... This may take a moment.")
    try:
        # The function now uses the 'ingestion_prompt' argument
        response = model.generate_content([ingestion_prompt, gemini_pdf_file])

        # Process the response to get triples (remains the same)
        lines = response.text.strip().split('\n')
        triples = []
        for line in lines:
            parts = line.split('|')
            if len(parts) == 3:
                e1 = parts[0].strip().strip("'\"")
                rel = parts[1].strip().strip("'\"")
                e2 = parts[2].strip().strip("'\"")
                if e1 and rel and e2:
                    triples.append((e1, rel, e2))
        
        if not triples:
            st.warning("Could not extract any structured data from the document.")
            return

        st.toast(f"Step 3: Storing {len(triples)} relationships in the knowledge graph.")
        graph_db.add_triples(triples)
        
    except Exception as e:
        st.error(f"An error occurred during the Gemini API call: {e}")
        raise