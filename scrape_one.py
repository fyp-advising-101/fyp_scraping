import os
import logging
import requests
from PyPDF2 import PdfReader
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Configure logging (same as in your scraper.py)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename="app.log",
    filemode="a"
)

# Key Vault and storage configurations (using your naming scheme)
VAULT_URL = "https://advising101vault.vault.azure.net"
credential = DefaultAzureCredential()
client = SecretClient(vault_url=VAULT_URL, credential=credential)
AZURE_BLOB_CONNECTION_STRING = client.get_secret("AZURE-BLOB-CONNECTION-STRING").value

output_folder_name = "scraper_output"
container_name = "web-scraper-output"

# The specific PDF URL to scrape
PDF_URL = "https://www.aub.edu.lb/Registrar/catalogue/Documents/g-catalogue-24-25.pdf"

def handle_pdf(pdf_url, blob_service_client):
    logging.info(f"Processing PDF: {pdf_url}")
    try:
        response = requests.get(pdf_url, stream=True)
        response.raise_for_status()
        # Create a filename similar to your existing code
        filename = f'{response.url.replace("https://", "").replace("www.","").replace("http://", "").replace("/", "_").replace(":", "")}'
        pdf_filename = f'{output_folder_name}/scraped_text_{filename}.pdf'

        # Save the PDF locally
        with open(pdf_filename, 'wb') as pdf_file:
            for chunk in response.iter_content(chunk_size=1024):
                pdf_file.write(chunk)
        logging.info(f"Saved PDF to {pdf_filename}")

        # Extract text from the PDF
        extracted_text = extract_text_from_pdf(pdf_filename)

        # Save the extracted text locally
        local_filename = f'{output_folder_name}/scraped_text_{filename}.txt'
        with open(local_filename, 'w', encoding='utf-8') as text_file:
            text_file.write(extracted_text)
        logging.info(f"Saved extracted text to {local_filename}")

        # Upload the text file to Azure Blob Storage
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=f'{filename}.txt')
        with open(local_filename, "rb") as file:
            blob_client.upload_blob(file, overwrite=True)
        logging.info(f"Uploaded extracted text to Azure Blob Storage as {filename}.txt")

        # Delete local copies
        os.remove(pdf_filename)
        os.remove(local_filename)

    except Exception as e:
        logging.error(f"Error processing PDF {pdf_url}: {e}")

def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        extracted_text = ""
        for page in reader.pages:
            page_text = page.extract_text() or ""
            extracted_text += page_text
        return extracted_text
    except Exception as e:
        logging.error(f"Error extracting text from PDF {pdf_path}: {e}")
        return ""

def main():
    os.makedirs(output_folder_name, exist_ok=True)
    
    # Replace with your actual connection string or retrieve it similarly as in your scraper.py
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_BLOB_CONNECTION_STRING)

    handle_pdf(PDF_URL, blob_service_client)

if __name__ == "__main__":
    main()
