import openai
import os
from chroma_db_manager.ChromaDbManager import ChromaDBManager
from database.database import db
from models.job import Job
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from azure.storage.blob import BlobServiceClient
import logging

logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",  # Define the log message format
    datefmt="%Y-%m-%d %H:%M:%S",  # Define the date format
    filename="app.log",  # Specify a file to write logs to
    filemode="a",  # Append to the file (default is 'a')
)

output_folder_name = "scraper_output"
pic_folder_name = "pics"
db_path = "aub_embeddings"
text_container_name = "web-scraper-output"
image_container_name = "instagram-scraper-output"
processed_image_container_name = "processed-instagram-scraper-output"
temp_photos_directory = "pics"

class TextFileProcessor:
    def __init__(self, chroma_db_path, openai_api_key, job_id, scraper_output_connection_string):
        openai.api_key = openai_api_key
        self.job_id = job_id
        self.chroma_db_path = chroma_db_path
        self.blob_service_client = BlobServiceClient.from_connection_string(scraper_output_connection_string)
        self.text_container_client = self.blob_service_client.get_container_client(text_container_name)
        self.image_container_client = self.blob_service_client.get_container_client(image_container_name)
        self.processed_image_container_client = self.blob_service_client.get_container_client(processed_image_container_name)

    def process_text_files(self): 
        """
        Process files while there are files in the folder and the scheduler is not terminated.
        """
        job : Job = Job.query.get(self.job_id)

        while True:
            blob_paginator = self.text_container_client.list_blobs(results_per_page=1000)  # Fetch 100 blobs per page
            paged_blobs = blob_paginator.by_page()

            for page in paged_blobs:
                files = [blob.name for blob in page]
                if not files:
                    if job.status == 2:
                        logging.info("Scheduler completed and no more files to process.")
                        break
                    logging.info("No files left to process. Waiting for new files...")
                    continue  # Wait for new files if the scheduler is still running
                
                for file in files:
                    logging.info(f"Processing file: {file}")
                    # Simulate file processing
                    # Assuming a cleaned up file

                    manager = ChromaDBManager(db_path=db_path, openai_api_key=openai.api_key)

                    try:
                        blob_client = self.text_container_client.get_blob_client(file)
                        content = blob_client.download_blob().readall().decode('utf-8')
                        text_splitter = RecursiveCharacterTextSplitter( # Params probably need adjustment
                            chunk_size = 100,
                            chunk_overlap  = 20,
                            length_function = len,
                            is_separator_regex = False,
                        )
                        document = Document(page_content=content, metadata={"source": "example_source"})
                        data = text_splitter.split_documents([document])
                        
                        collection_name = "aub_embeddings"
                        for index, item in enumerate(data):
                            entry_id = f"{file}-{index}"
                            text = item # Document object
                            manager.add_or_update_text_entry(collection_name, entry_id, text)

                    except FileNotFoundError:
                        logging.error(f"File not found: {file}")
                    except Exception as e:
                        logging.error(f"An error occurred: {e}")

                    logging.info(f"File processed: {file}")

                if job.status == 2:
                    logging.info("Scheduler completed but there are still files to process.")
                    continue  # Continue processing remaining files

                job = Job.query.get(self.job_id)

            break # REMOVE ?

        logging.info(f"Exiting: Scheduler status is '{job.status}'. All files processed or terminated.")

    def process_image_files(self):

        job : Job = Job.query.get(self.job_id)
        collection_name = "aub_embeddings"
        while True: #job.status != 'Terminated':  # Continue unless the scheduler is terminated # REMOVE
            blob_paginator = self.image_container_client.list_blobs(results_per_page=100)  # Fetch 100 blobs per page
            paged_blobs = blob_paginator.by_page()
            for page in paged_blobs:
                files = [blob.name for blob in page]
                if not files:
                    if job.status == 2:
                        logging.info("Scheduler completed and no more files to process.")
                        break
                    logging.info("No files left to process. Waiting for new files...")
                    continue  # Wait for new files if the scheduler is still running

                manager = ChromaDBManager(db_path=db_path, openai_api_key=openai.api_key)

                for file in files:
                    blob_client = self.image_container_client.get_blob_client(file)
                    logging.info(f"Processing file: {file}")
                    downloaded_bytes = blob_client.download_blob().readall()
                    # Save the binary data as an image into folder temporarily
                    local_file_path = os.path.join(temp_photos_directory, os.path.basename(file))
                    with open(local_file_path, 'wb') as f:
                        f.write(downloaded_bytes)  # Write the raw bytes to the file
                    try:
                        entry_id = file
                        #process images into text
                        manager.convert_image_to_text(local_file_path, file) 
                        os.remove(local_file_path)
                    except Exception as e:
                        logging.error(f"An error occurred in image embeddings generation: {e}")

            # Embed text files that contain image descriptions

            blob_paginator = self.processed_image_container_client.list_blobs(results_per_page=1000)  # Fetch 100 blobs per page
            paged_blobs = blob_paginator.by_page()
            for page in paged_blobs:
                files = [blob.name for blob in page]
                if not files:
                    if job.status == 2:
                        logging.info("Scheduler completed and no more text files from images to process.")
                        break
                    logging.info("No text files from images left to process. Waiting for new files...")
                    continue  # Wait for new files if the scheduler is still running

                manager = ChromaDBManager(db_path=db_path, openai_api_key=openai.api_key)
                for file in files:
                    blob_client = self.processed_image_container_client.get_blob_client(file)
                    logging.info(f"Processing file: {file}")
                    downloaded_text = blob_client.download_blob().readall().decode("utf-8")
                    # Save the binary data as an image into folder temporarily
                    document = Document(page_content=downloaded_text, metadata={"source": "example_source"})
                    manager.add_or_update_image_entry(collection_name, file, document)

            break ##### REMOVE
