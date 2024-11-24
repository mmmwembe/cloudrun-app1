import pandas as pd
import uuid

# Initialize global parent files DataFrame with ALL columns
PROCESS_FILES_PD = pd.DataFrame(
    columns=[
        'gcp_public_url',
        'original_filename',
        'pdf_text_content',
        'file_256_hash',
        'citation_name',
        'citation_authors',
        'citation_year',
        'citation_organization',
        'citation_doi',
        'citation_url',
        'upload_timestamp',
        'processed',
        'images_in_doc',
        'paper_image_urls',
        'species_id',
        'species_index',
        'species_name',
        'species_authors',
        'species_year',
        'species_references',
        'formatted_species_name',
        'genus',
        'species_magnification',
        'species_scale_bar_microns',
        'species_note',
        'figure_caption',
        'source_material_location',
        'source_material_coordinates',
        'source_material_description',
        'source_material_received_from',
        'source_material_date_received',
        'source_material_note',
        'cropped_image_url',
        'embeddings_256',
        'embeddings_512',
        'embeddings_1024',
        'embeddings_2048',
        'embeddings_4096',
        'bbox_top_left_bottom_right',
        'yolo_bbox',
        'segmentation'
    ]
)


def update_process_files_pd(result, citation, llm_json_output, public_url, filename, pdf_text_content):
    """
    Updates the PROCESS_FILES_PD DataFrame with new data.
    
    Args:
        result (dict): Output from `extract_images_and_metadata_from_pdf`.
        citation (dict): Citation metadata (e.g., name, authors, year, etc.).
        llm_json_output (dict): Parsed JSON output from LLM with species details and additional metadata.
        public_url (str): Public URL of the processed file.
        filename (str): Original filename of the file.
        pdf_text_content (str): Text content extracted from the PDF.

    Returns:
        None
    """
    global PROCESS_FILES_PD

    # Extract global attributes
    figure_caption = llm_json_output.get('figure_caption', '')
    source_material_location = llm_json_output.get('source_material_location', '')
    source_material_coordinates = llm_json_output.get('source_material_coordinates', '')
    source_material_description = llm_json_output.get('source_material_description', '')
    source_material_received_from = llm_json_output.get('source_material_received_from', '')
    source_material_date_received = llm_json_output.get('source_material_date_received', '')
    source_material_note = llm_json_output.get('source_material_note', '')

    # Initialize new rows list
    new_rows = []

    # Process species array from LLM output
    for species in llm_json_output.get('diatom_species_array', []):
        try:
            # Extract species-specific attributes
            species_index = species.get('species_index', '')
            species_name = species.get('species_name', '')
            species_authors = species.get('species_authors', [])
            species_year = species.get('species_year', '')
            species_references = species.get('species_references', [])
            formatted_species_name = species.get('formatted_species_name', '')
            genus = species.get('genus', '')
            species_magnification = species.get('species_magnification', '')
            species_scale_bar_microns = species.get('species_scale_bar_microns', '')
            species_note = species.get('species_note', '')

            # Create a new row
            new_row = {
                'gcp_public_url': public_url,
                'original_filename': filename,
                'pdf_text_content': pdf_text_content,
                'file_256_hash': result.get('file_256_hash', ''),
                'citation_name': citation.get('name', ''),
                'citation_authors': ', '.join(citation.get('authors', [])),
                'citation_year': citation.get('year', ''),
                'citation_organization': citation.get('organization', ''),
                'citation_doi': citation.get('doi', ''),
                'citation_url': citation.get('url', ''),
                'upload_timestamp': pd.Timestamp.now(),
                'processed': True,
                'images_in_doc': result.get('images_in_doc', []),
                'paper_image_urls': result.get('paper_image_urls', []),
                'species_id': uuid.uuid4().hex,
                'species_index': species_index,
                'species_name': species_name,
                'species_authors': species_authors,
                'species_year': species_year,
                'species_references': species_references,
                'formatted_species_name': formatted_species_name,
                'genus': genus,
                'species_magnification': species_magnification,
                'species_scale_bar_microns': species_scale_bar_microns,
                'species_note': species_note,
                'figure_caption': figure_caption,
                'source_material_location': source_material_location,
                'source_material_coordinates': source_material_coordinates,
                'source_material_description': source_material_description,
                'source_material_received_from': source_material_received_from,
                'source_material_date_received': source_material_date_received,
                'source_material_note': source_material_note,
                'cropped_image_url': "",
                'embeddings_256': [],
                'embeddings_512': [],
                'embeddings_1024': [],
                'embeddings_2048': [],
                'embeddings_4096': [],
                'bbox_top_left_bottom_right': "",
                'yolo_bbox': "",
                'segmentation': ""
            }
            new_rows.append(new_row)

        except Exception as e:
            print(f"Error processing species: {species.get('species_name', 'Unknown')} - {e}")
            continue

    # Add all new rows to the DataFrame
    if new_rows:
        PROCESS_FILES_PD = pd.concat([PROCESS_FILES_PD, pd.DataFrame(new_rows)], ignore_index=True)


def validate_update_arguments(**kwargs):
    """
    Validates the presence and types of required arguments for update_parent_files_pd.
    
    Args:
        kwargs: Keyword arguments representing the arguments to validate.
    
    Returns:
        bool: True if all arguments are valid, False otherwise.
    """
    required_keys = {
        "result": dict,
        "citation": dict,
        "llm_json_output": dict,
        "public_url": str,
        "filename": str,
        "pdf_text_content": str
    }

    for key, expected_type in required_keys.items():
        value = kwargs.get(key)
        if value is None or not isinstance(value, expected_type):
            print(f"Validation failed: '{key}' is missing or not of type {expected_type.__name__}.")
            return False

    return True


# # Example values
# result = {"images_in_doc": [], "file_256_hash": "abc123"}
# citation = {"name": "Sample Citation", "authors": ["Author A"], "year": "2024"}
# llm_json_output = {"diatom_species_array": []}
# public_url = "https://example.com/file.pdf"
# filename = "file.pdf"
# pdf_text_content = "This is sample text from a PDF."

# # Validate arguments
# if validate_update_arguments(
#     result=result,
#     citation=citation,
#     llm_json_output=llm_json_output,
#     public_url=public_url,
#     filename=filename,
#     pdf_text_content=pdf_text_content
# ):
#     # Arguments are valid, proceed to update
#     update_process_files_pd(result, citation, llm_json_output, public_url, filename, pdf_text_content)
# else:
#     print("Invalid arguments. Skipping update.")