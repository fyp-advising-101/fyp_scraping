import openai
import os
from chroma_db_manager.ChromaDbManager import ChromaDBManager
from database.database import db
from models.jobScheduler import JobScheduler
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

output_folder_name = "scraper_output"
pic_folder_name = "pics"
db_path = "aub_embeddings"

class TextFileProcessor:
    def __init__(self, chroma_db_path, openai_api_key, job_id):
        openai.api_key = openai_api_key
        self.job_id = job_id
        self.chroma_db_path = chroma_db_path

    def process_text_files(self): 
        """
        Process files while there are files in the folder and the scheduler is not terminated.
        """
        job : JobScheduler = JobScheduler.query.get(self.job_id)

        while job.status != 'Terminated':  # Continue unless the scheduler is terminated
            files = [file for file in os.listdir(output_folder_name) if os.path.isfile(os.path.join(output_folder_name, file))]
            
            if not files:
                if job.status == 'Completed':
                    print("Scheduler completed and no more files to process.")
                    break
                print("No files left to process. Waiting for new files...")
                continue  # Wait for new files if the scheduler is still running
            
            for file in files:
                file_path = os.path.join(output_folder_name, file)
                print(f"Processing file: {file_path}")
                # Simulate file processing
                # Assuming a cleaned up file

                manager = ChromaDBManager(db_path=db_path, openai_api_key=openai.api_key)

                try:
                    with open(file_path, 'r') as f: 
                        content = f.read()
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
                        entry_id = f"{file_path}-{index}"
                        text = item # Document object
                        manager.add_or_update_text_entry(collection_name, entry_id, text)

                except FileNotFoundError:
                    print(f"File not found: {file_path}")
                except Exception as e:
                    print(f"An error occurred: {e}")

                os.remove(file_path)  # Remove the file after processing
                print(f"File processed and removed: {file_path}")

            if job.status == 'Completed':
                print("Scheduler completed but there are still files to process.")
                continue  # Continue processing remaining files

            job = JobScheduler.query.get(self.job_id)

        print(f"Exiting: Scheduler status is '{job.status}'. All files processed or terminated.")

    def process_image_files(self):

        job : JobScheduler = JobScheduler.query.get(self.job_id)

        while job.status != 'Terminated':  # Continue unless the scheduler is terminated
            files = [file for file in os.listdir(pic_folder_name) if os.path.isfile(os.path.join(pic_folder_name, file))]

            if not files:
                if job.status == 'Completed':
                    print("Scheduler completed and no more files to process.")
                    break
                print("No files left to process. Waiting for new files...")
                continue  # Wait for new files if the scheduler is still running

            collection_name = "aub_embeddings"
            manager = ChromaDBManager(db_path=db_path, openai_api_key=openai.api_key)

            for file in files:
                file_path = os.path.join(pic_folder_name, file)
                print(f"Processing file: {file_path}")

                try:
                    entry_id = file
                    manager.add_or_update_image_entry(collection_name, entry_id, file_path)
                except Exception as e:
                    print(f"An error occurred in image embeddings generation: {e}")

                
            break ##### REMOVE
