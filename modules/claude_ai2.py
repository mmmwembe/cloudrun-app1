from anthropic import Anthropic
import json
import base64
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the API key from environment variable
api_key = os.getenv('ANTHROPIC_API_KEY')

# Initialize Anthropic client
client = Anthropic(api_key=api_key)

# Model configuration
MODEL_NAME = "claude-3-5-sonnet-20241022"

def create_claude_prompt():
    """
    Creates a structured prompt for Claude to process diatom data.
    Returns a string containing the prompt with instructions and expected JSON structure.
    """
    prompt = """
    Please analyze the provided text and extract information about marine diatoms.
    Return the data in the following JSON structure, maintaining strict adherence to the schema:
    {
        "figure_caption": string,
        "source_material_location": string,
        "source_material_coordinates": string,
        "source_material_description": string,
        "source_material_date_collected": string,
        "source_material_received_from": string,
        "source_material_date_received": string,
        "source_material_note": string,
        "diatom_species_array": [
            {
                "species_index": number,
                "species_name": string,
                "species_authors": string[],
                "species_year": number,
                "species_references": [
                    {
                        "author": string,
                        "year": number,
                        "figure": string
                    }
                ],
                "formatted_species_name": string,
                "genus": string,
                "species_magnification": string,
                "species_scale_bar_microns": string,
                "species_note": string
            }
        ]
    }

    Important instructions:
    1. Extract all information exactly as presented in the source text
    2. Maintain proper formatting for scientific names
    3. Ensure all dates are in the original format
    4. Convert coordinates to standardized format (degrees, minutes)
    5. Include all references with complete citation information
    6. Generate formatted_species_name by replacing spaces with underscores
    7. Leave empty strings for missing information rather than omitting fields
    8. Ensure all numerical values are properly typed (numbers not strings)
    
    Parse the provided text and return only the JSON object without any additional text or explanation.
    """
    return prompt

def create_messages(pdf_text_content, prompt):
    """
    Creates the message array for the Claude API request.
    
    Args:
        pdf_text_content (str): The extracted text from the PDF
        prompt (str): The formatted prompt with instructions
    
    Returns:
        list: Array of message objects for the API request
    """
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": pdf_text_content
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }
    ]

def get_completion(messages):
    """
    Sends the request to Claude API and returns the completion.
    
    Args:
        messages (list): Array of message objects
    
    Returns:
        str: Claude's response containing the JSON data
    """
    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=8192,
            messages=messages
        )
        
        # Parse the response to ensure it's valid JSON
        try:
            json_response = json.loads(response.content)
            return json.dumps(json_response, indent=2)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in response"}
            
    except Exception as e:
        return {"error": str(e)}


def claude_paper_info_processor(pdf_text_content):
    """
    Process PDF text content using Claude API to extract diatom information.
    
    Args:
        pdf_text_content (str): The extracted text from the PDF
        
    Returns:
        str: JSON string containing the processed diatom information or error message
    """
    try:
        # Create the structured prompt
        prompt = create_claude_prompt()
        
        # Create messages for Claude
        messages = create_messages(pdf_text_content, prompt)
        
        # Get completion from Claude
        result = get_completion(messages)
        
        return result
        
    except Exception as e:
        return json.dumps({
            "error": f"Error processing paper information: {str(e)}"
        }, indent=2)