# appConstants.py

# Default prompt for information extraction from PDFs.
DEFAULT_INGESTION_PROMPT = """
Based on the entire content of the provided PDF document, extract all key 
entities and their relationships.
An entity can be a person, organization, location, date, or a monetary value.
Present the output as a list of comma-separated values (CSV) with the format:
 'ENTITY_1|RELATIONSHIP|ENTITY_2'.
The RELATIONSHIP should be a concise, active verb phrase formatted in
 snake_case_upper, like 'IMPOSED_FINE_ON' or 'IS_DIRECTOR_OF'.
Do not include a header row. 
Ensure all relevant relationships are extracted from the document.

Example Output:
'John Doe|IS_A|Director'
'XYZ Corp|IMPOSED_FINE_ON|ABC Ltd'
'ABC Ltd|WAS_FINED|Rs. 5 Lakh'
'SEBI|ISSUED_ORDER_ON|2023-04-15'
"""

# List of pre-defined questions for the user to click.
QUESTIONS = [
    # 'What causes Anthrax?',
    # 'Bioresearch Monitoring (BIMO) program',
    # 'Food and Drug Administration',
    "What does Kshama P. Wagherkar do?"
]
