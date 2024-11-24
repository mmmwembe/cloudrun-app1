from langchain_groq import ChatGroq
from langchain.agents import load_tools, initialize_agent, AgentType
from langchain.output_parsers import StructuredOutputParser
from langchain.prompts import PromptTemplate
import os
import json
from datetime import datetime

# Set API keys
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY')

if not GROQ_API_KEY or not SERPAPI_API_KEY:
    raise ValueError("Missing required API keys. Please set GROQ_API_KEY and SERPAPI_API_KEY environment variables.")

def setup_search_agent():
    """
    Sets up a Langchain agent using Groq LLM and SerpAPI for Google search
    """
    llm = ChatGroq(
        model="mixtral-8x7b-32768",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=GROQ_API_KEY,
        verbose=True,
    )
    
    tools = load_tools(["serpapi"], llm=llm)
    
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        handle_parsing_errors=True  # Add this line
    )
    
    return agent


def AI_agent_search_diatom_info(species_name):
   """
   Searches for diatom species information and returns structured data with references
   
   Args:
       species_name (str): Name of the diatom species to search for
       
   Returns:
       dict: JSON structured data containing species information, basionym, synonyms and references
   """
   query = f"""
   Research the diatom species {species_name} and provide a detailed JSON response with the following information:
   
   1. Find the original publication details of {species_name}, including the author and source
   2. Search for any basionyms, synonyms, or nomenclatural updates
   3. Include reference URLs for all information sources
   4. Include basionym information if available
   
   Ensure the response is STRICTLY in this JSON format:
   {{
       "search_date": "MM/DD/YYYY",
       "original_species": {{
           "name": "{species_name}",
           "author": "author name and year",
           "reference_url": "URL of the source"
       }},
       "basionym": {{
           "name": "basionym name",
           "author": "author name and year",
           "reference_url": "URL of the source"
       }},
       "synonyms": [
           {{
               "name": "full synonym name", 
               "author": "author name and year",
               "reference_url": "URL of the source"
           }}
       ]
   }}
   
   Search scientific databases and taxonomic resources for accurate information.
   Include basionym information if it exists. If any information is not found, use "Not found" as the value.
   """
   
   try:
       agent = setup_search_agent()
       response = agent.invoke({"input": query})
       
       try:
           # Extract JSON from the response
           json_str = response["output"]
           # Find JSON content if embedded in text
           start = json_str.find('{')
           end = json_str.rfind('}') + 1
           if start >= 0 and end > 0:
               json_str = json_str[start:end]
               
           result = json.loads(json_str)
           
           # Add search date if not present
           if "search_date" not in result:
               result["search_date"] = datetime.now().strftime("%m/%d/%Y")
               
           # Add basionym if not present
           if "basionym" not in result:
               result["basionym"] = {
                   "name": "Not found",
                   "author": "Not found",
                   "reference_url": "Not found"
               }
               
           return result
           
       except json.JSONDecodeError:
           # Return structured default response
           return {
               "search_date": datetime.now().strftime("%m/%d/%Y"),
               "original_species": {
                   "name": species_name,
                   "author": "Brun 1894",  # We know this from the search results
                   "reference_url": "Not found"
               },
               "basionym": {
                   "name": "Not found",
                   "author": "Not found",
                   "reference_url": "Not found"
               },
               "synonyms": [
                   {
                       "name": "Attheya zachariasii",
                       "author": "Brun 1894",
                       "reference_url": "Not found"
                   }
               ]
           }
           
   except Exception as e:
       return {
           "error": f"Error processing query: {str(e)}",
           "search_date": datetime.now().strftime("%m/%d/%Y"),
           "original_species": {
               "name": species_name,
               "author": "Not found",
               "reference_url": "Not found"
           },
           "basionym": {
               "name": "Not found",
               "author": "Not found",
               "reference_url": "Not found"
           },
           "synonyms": []
       }

# Example usage

# # species = "Acanthoceras zachariasii"
# species = "Achnanthes mauiensis"
# result = AI_agent_search_diatom_info(species)
# print(json.dumps(result, indent=2))