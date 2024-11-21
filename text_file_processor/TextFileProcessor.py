import openai
import os
from chroma_db_manager.ChromaDbManager import ChromaDBManager
from database.database import db
from models.jobScheduler import JobScheduler

output_folder_name = "scraper_output"

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
                os.remove(file_path)  # Remove the file after processing
                print(f"File processed and removed: {file_path}")

            if job.status == 'Completed':
                print("Scheduler completed but there are still files to process.")
                continue  # Continue processing remaining files

            job = JobScheduler.query.get(self.job_id)

        print(f"Exiting: Scheduler status is '{job.status}'. All files processed or terminated.")

