from anthropic import Anthropic
import json
import base64
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the Google service account JSON from environment variable
api_key = os.getenv('ANTHROPIC_API_KEY')

# While PDF support is in beta, you must pass in the correct beta header
# Instantiate the client with the API key and beta headers
client = Anthropic(
    api_key=api_key,
    default_headers={"anthropic-beta": "pdfs-2024-09-25"}
)

# For now, only claude-3-5-sonnet-20241022 supports PDFs
MODEL_NAME = "claude-3-5-sonnet-20241022"

# Start by reading in the PDF and encoding it as base64

# file_name = "/content/3_Azores.pdf"

# with open(file_name, "rb") as pdf_file:
#     binary_data = pdf_file.read()
#     base64_encoded_data = base64.standard_b64encode(binary_data)
#     base64_string = base64_encoded_data.decode("utf-8")


def encode_pdf_to_base64(file_name):
    with open(file_name, "rb") as pdf_file:
        binary_data = pdf_file.read()
        base64_encoded_data = base64.standard_b64encode(binary_data)
        return base64_encoded_data.decode("utf-8")

# Function to create the Claude prompt with the formatted text
def create_claude_prompt():
    # Prepare the prompt
    llm_prompt = f"""
    Analyze the following document and extract the information into a structured JSON. 
    Please ensure to include details for all diatom species mentioned in the document, even if some fields are missing or the data is unclear. 
    For fields where information is missing, return them as empty strings or empty lists. The JSON should follow this structure for each species:

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

    Remember: diatom_species_array is a listing of all diatom species dicts, with the above diatom dict just giving an example of what the dicts look like.
    This is very important - you should return the full JSON with ALL DIATOM SPECIES listed in the document
    This is also very import: Your response should just be the json with no introductory text.

    
    """

    # Return the prompt to be used for the LLM call
    return llm_prompt

# prompt = create_claude_prompt()

# messages = [
#     {
#         "role": 'user',
#         "content": [
#             {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64_string}},
#             {"type": "text", "text": prompt}
#         ]
#     }
# ]

def create_messages(base64_string, prompt):
    return [
        {
            "role": 'user',
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64_string}},
                {"type": "text", "text": prompt}
            ]
        }
    ]

# # Example usage
# messages = create_messages(base64_string, prompt)


def get_completion(messages):
    return client.messages.create(
        model=MODEL_NAME,
        max_tokens=8192,
        messages=messages
    ).content

# completion = get_completion(client, messages)

# print(completion)