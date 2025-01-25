import openai
import os
from chroma_db_manager.ChromaDbManager import ChromaDBManager
from database.database import db
from models.jobScheduler import JobScheduler
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from azure.storage.blob import BlobServiceClient

output_folder_name = "scraper_output"
pic_folder_name = "pics"
db_path = "aub_embeddings"
text_container_name = "web-scraper-output"
image_container_name = "instagram-scraper-output"
temp_photos_directory = "pics"

class TextFileProcessor:
    def __init__(self, chroma_db_path, openai_api_key, job_id, scraper_output_connection_string):
        openai.api_key = openai_api_key
        self.job_id = job_id
        self.chroma_db_path = chroma_db_path
        self.blob_service_client = BlobServiceClient.from_connection_string(scraper_output_connection_string)
        self.text_container_client = self.blob_service_client.get_container_client(text_container_name)
        self.image_container_client = self.blob_service_client.get_container_client(image_container_name)

    def process_text_files(self): 
        """
        Process files while there are files in the folder and the scheduler is not terminated.
        """
        job : JobScheduler = JobScheduler.query.get(self.job_id)

        while job.status != 'Terminated':  # Continue unless the scheduler is terminated
            blob_paginator = self.text_container_client.list_blobs(results_per_page=1000)  # Fetch 100 blobs per page
            paged_blobs = blob_paginator.by_page()

            for page in paged_blobs:
                files = [blob.name for blob in page]
                if not files:
                    if job.status == 'Completed':
                        print("Scheduler completed and no more files to process.")
                        break
                    print("No files left to process. Waiting for new files...")
                    continue  # Wait for new files if the scheduler is still running
                
                for file in files:
                    print(f"Processing file: {file}")
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
                        print(f"File not found: {file}")
                    except Exception as e:
                        print(f"An error occurred: {e}")

                    print(f"File processed: {file}")

                if job.status == 'Completed':
                    print("Scheduler completed but there are still files to process.")
                    continue  # Continue processing remaining files

                job = JobScheduler.query.get(self.job_id)

            break # REMOVE ?

        print(f"Exiting: Scheduler status is '{job.status}'. All files processed or terminated.")

    def process_image_files(self):

        job : JobScheduler = JobScheduler.query.get(self.job_id)

        while job.status != 'Terminated':  # Continue unless the scheduler is terminated
            blob_paginator = self.image_container_client.list_blobs(results_per_page=100)  # Fetch 100 blobs per page
            paged_blobs = blob_paginator.by_page()
            for page in paged_blobs:
                files = [blob.name for blob in page]
                if not files:
                    if job.status == 'Completed':
                        print("Scheduler completed and no more files to process.")
                        break
                    print("No files left to process. Waiting for new files...")
                    continue  # Wait for new files if the scheduler is still running

                collection_name = "aub_embeddings"
                manager = ChromaDBManager(db_path=db_path, openai_api_key=openai.api_key)

                for file in files:
                    blob_client = self.image_container_client.get_blob_client(file)
                    print(f"Processing file: {file}")
                    downloaded_bytes = blob_client.download_blob().readall()
                    # Save the binary data as an image into folder temporarily
                    local_file_path = os.path.join(temp_photos_directory, os.path.basename(file))
                    with open(local_file_path, 'wb') as f:
                        f.write(downloaded_bytes)  # Write the raw bytes to the file
                    try:
                        entry_id = file
                        manager.add_or_update_image_entry(collection_name, entry_id, local_file_path)
                        os.remove(local_file_path)
                    except Exception as e:
                        print(f"An error occurred in image embeddings generation: {e}")

                
            break ##### REMOVE
