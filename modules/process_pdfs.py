import os
import fitz
import pandas as pd

def process_pdf(PARENT_FILES_PD, TEMP_EXTRACTED_PDFS_DIR, TEMP_EXTRACTED_IMAGES_DIR, row_index):
    global CHILD_FILES_PD
    
    records = []
    parent_file = PARENT_FILES_PD.iloc[row_index]
    
    hash_num = parent_file['hash']
    original_filename = parent_file['original_filename']
    gcp_public_url = parent_file['gcp_public_url']
    
    # Create directories if they don't exist
    pdf_output_dir = os.path.join(TEMP_EXTRACTED_PDFS_DIR, str(hash_num))
    img_output_dir = os.path.join(TEMP_EXTRACTED_IMAGES_DIR, str(hash_num))
    os.makedirs(pdf_output_dir, exist_ok=True)
    os.makedirs(img_output_dir, exist_ok=True)
    
    # Open and process PDF
    pdf_document = fitz.open(os.path.join(gcp_public_url, original_filename))
    
    for page_idx in range(len(pdf_document)):
        page = pdf_document[page_idx]
        
        # Extract single page to new PDF
        output_pdf = fitz.open()
        output_pdf.insert_pdf(pdf_document, from_page=page_idx, to_page=page_idx)
        pdf_output_path = os.path.join(
            pdf_output_dir, 
            f"{original_filename}_page_{page_idx}.pdf"
        )
        output_pdf.save(pdf_output_path)
        output_pdf.close()
        
        # Extract images from page
        image_list = page.get_images()
        
        child_record = parent_file.to_dict()
        child_record.update({
            'child_pdf_file_url': f"{gcp_public_url}/{pdf_output_path}",
            'has_images': bool(image_list),
            'num_of_images': len(image_list),
            'page_number': page_idx,
            'image_urls_array': []
        })
        
        # Process images if they exist
        if image_list:
            for img_idx, img_info in enumerate(image_list):
                img_number = img_idx + 1
                
                # Extract image
                base_img = pdf_document.extract_image(img_info[0])
                image_bytes = base_img["image"]
                
                # Save image
                img_filename = f"{original_filename}_page_{page_idx}_image_{img_number}_of_{len(image_list)}.jpg"
                img_path = os.path.join(img_output_dir, img_filename)
                
                with open(img_path, 'wb') as img_file:
                    img_file.write(image_bytes)
                
                # Add image URL to array
                child_record['image_urls_array'].append(f"{gcp_public_url}/{img_path}")
        
        records.append(child_record)
    
    pdf_document.close()
    
    # Update the global DataFrame with new records
    new_df = pd.DataFrame(records)
    CHILD_FILES_PD = pd.concat([CHILD_FILES_PD, new_df], ignore_index=True)