import os
from PyPDF2 import PdfReader
from groq import Groq
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the Google service account JSON from environment variable
GROQ_API_KEY = os.getenv('GROQ_API_KEY2')

LLM_MODEL = "llama3-8b-8192"
MODEL_TEMPERATURE = 0.5
MAX_TOKENS = 8000
TOP_P = 1

# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)

# System message template
SYSTEM_MESSAGE = """
You are an expert in diatom analysis. Your role is to analyze the provided document and return the information in a structured JSON format.

# The JSON structure should capture all available details, even if some fields are empty:
paper_info = {
    "figure_caption": "",  # Include if available
    "source_material": {
        "location": "",  # Include if available
        "coordinates": "",  # Include if available
        "description": "",  # Include if available
        "date_collected": "",  # Include if available
        "received_from": "",  # Include if available
        "date_received": "",  # Include if available
        "note": ""  # Include if available
    },
    "diatom_species_array": [
        {
            "index": 0,  # Replace with the species index or leave as 0 if not available
            "species_name": "",  # Include the full species name
            "species_authors": [],  # List of authors, or leave empty
            "year": "",  # Year of species publication, or leave empty
            "references": [],  # List of references with author, year, and figure details
            "formatted_species_name": "",  # Species name formatted for output
            "genus": "",  # The genus of the species
            "magnification": "",  # Magnification level, or leave empty
            "scale_bar_microns": "",  # Scale bar size in microns, or leave empty
            "note": ""  # Any additional notes, or leave empty
        }
        # Repeat for additional diatom species as needed
    ]
}
"""

def extract_diatom_data_with_groq_llama(text):
    """
    Function to extract diatom data from a given document text using the Groq model.
    
    Parameters:
    - text (str): The text content from the document (e.g., extracted from a PDF).
    
    Returns:
    - dict: JSON object containing the paper information, diatom species, and other attributes.
    """
    # Formulate the LLM prompt with the document text
    llm_prompt = f"""
    Please analyze the following document text and convert it into the structured JSON format described:
    
    {text}  # The text to analyze
    """

    try:
        # Send a request to the Groq model to process the document text
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": llm_prompt},
            ],
            model=LLM_MODEL,
            temperature=MODEL_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            top_p=TOP_P,
            stop=None,
            stream=False,
        )

        # Extract and print the response from the LLM
        groq_summary = chat_completion.choices[0].message.content
        print(f"LLM Response: {groq_summary}")

        # If the response is empty, print a warning and return an empty dictionary
        if not groq_summary.strip():
            print("Warning: Empty response received.")
            return {}

        # Parse the response into a JSON object
        paper_info_json = json.loads(groq_summary)
        return paper_info_json

    except Exception as e:
        # Handle any errors during the API request
        print(f"Error occurred during chat completion request: {str(e)}")
        return {}  # Return an empty dictionary if an error occurs

# Function to read the text from the PDF file
def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# Function to create the Llama prompt with the formatted text
def create_llama_prompt(text):
    # Prepare the prompt
    llm_prompt = f"""
    Analyze the following document and extract the information into a structured JSON. Please ensure to include details for all diatom species mentioned in the document, even if some fields are missing or the data is unclear. For fields where information is missing, return them as empty strings or empty lists. The JSON should follow this structure for each species:

    paper_info = {{
        "figure_caption": "Plate 3: Marine Diatoms from the Azores",
        "source_material": {{
            "location": "South East coast of Faial, Caldeira Inferno",
            "coordinates": "38° 31' N; 28° 38' W",
            "description": "An open crater of a small volcano, shallow and sandy. Gathered from Pinna (molluscs) and stones.",
            "date_collected": "June 1st, 1981",
            "received_from": "Hans van den Heuvel, Leiden",
            "date_received": "March 17th, 1988",
            "note": "Material also deposited in Rijksherbarium Leiden, the Netherlands. Aliquot sample and slide also in collection Sterrenburg, Nr. 249."
        }},
        "diatom_species_array": [
            {{
                "index": 65,
                "species_name": "Diploneis bombus",
                "species_authors": ["Cleve-Euler", "Backman"],
                "year": 1922,
                "references": [
                    {{
                        "author": "Hendey",
                        "year": 1964,
                        "figure": "pl. 32, fig. 2"
                    }}
                ],
                "formatted_species_name": "Diploneis_bombus",
                "genus": "Diploneis",
                "magnification": 1000,
                "scale_bar_microns": 30,
                "note": ""
            }}
            # Repeat for additional diatom species as needed
        ]
    }}

    Here is the document text for analysis:
    {text}
    """

    # Return the prompt to be used for the LLM call
    return llm_prompt

# # Path to the PDF file
# pdf_path = "/content/3_Azores.pdf"  # Replace with your PDF file path

# # Extract text from the PDF
# pdf_text = extract_text_from_pdf(pdf_path)

# # Create the Llama prompt with the extracted text
# llama_prompt = create_llama_prompt(pdf_text)

# # Extract diatom data using the Groq LLM
# llama_paper_info = extract_diatom_data_with_groq_llama(llama_prompt)

# # Print the extracted diatom data
# print("Diatom Data Extracted by Llama LLM:")
# print(llama_paper_info)

def get_llama_paper_info(pdf_path):
    # Step 1: Extract text from the PDF
    pdf_text = extract_text_from_pdf(pdf_path)
    
    # Step 2: Create the Llama prompt using the extracted PDF text
    llama_prompt = create_llama_prompt(pdf_text)
    
    # Step 3: Extract diatom data using the Groq LLM
    llama_paper_info = extract_diatom_data_with_groq_llama(llama_prompt)
    
    # Return the extracted diatom information
    return llama_paper_info