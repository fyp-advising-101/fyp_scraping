import openai
from chromadb import HttpClient
import os
import base64
import requests
import logging
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
from datetime import datetime
import chromadb.utils.embedding_functions as embedding_functions

logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",  # Define the log message format
    datefmt="%Y-%m-%d %H:%M:%S",  # Define the date format
    filename="app.log",  # Specify a file to write logs to
    filemode="a",  # Append to the file (default is 'a')
)

VAULT_URL = "https://advising101vault.vault.azure.net"
credential = DefaultAzureCredential()
client = SecretClient(vault_url=VAULT_URL, credential=credential)
AZURE_BLOB_CONNECTION_STRING = client.get_secret("AZURE-BLOB-CONNECTION-STRING").value
text_container_name = "processed-instagram-scraper-output"

class ChromaDBManager:
    def __init__(self, db_path, openai_api_key):
        self.client = HttpClient(host='20.203.61.164', port=8000)
        openai.api_key = openai_api_key
        self.blob_service_client = BlobServiceClient.from_connection_string(AZURE_BLOB_CONNECTION_STRING)
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=openai_api_key,
            model_name="text-embedding-3-large"
        )

    def get_or_create_collection(self, collection_name):
        """Get or create a Chroma DB collection."""
        return self.client.get_or_create_collection(name=collection_name,embedding_function=self.embedding_function)

    # def generate_embedding(self, text):
    #     """Generate an embedding for a given text using OpenAI API."""
    #     response = openai.embeddings.create(input=text, model="text-embedding-3-large")
    #     return response.data[0].embedding

    def add_or_update_text_entry(self, collection_name, entry_id, text):
        """Add or update an entry in the Chroma DB."""
        collection = self.get_or_create_collection(collection_name)
        logging.info("collection found: "+ collection_name)
        # embedding = self.generate_embedding(text.page_content)
        # Check if entry already exists
        existing_entries = collection.get(ids=[entry_id])['ids']

        if entry_id in existing_entries:
            logging.info("Updating entry with ID:" + entry_id)
            collection.delete(ids=[entry_id])

        # Add the new or updated entry
        collection.add(
            ids=[entry_id],
            documents=[text.page_content],
            metadatas=[{"date_added": datetime.now().isoformat(), "category": "info"}]
        )
        logging.info("Entry with ID: " + entry_id + " added/updated successfully!")
        print("Entry with ID: " + entry_id + " added/updated successfully!")

    def add_or_update_image_entry(self, collection_name, filename, text):
        """Add or update an entry in the Chroma DB."""
        split_filename = filename.split('_', 1)
        entry_id = split_filename[1]
        category = split_filename[0]
        collection = self.get_or_create_collection(collection_name)
        logging.info("collection found: "+ collection_name)
        # Check if entry already exists
        existing_entries = collection.get(ids=[entry_id])['ids']

        if entry_id in existing_entries:
            logging.info("Updating entry with ID:" + entry_id)
            collection.delete(ids=[entry_id])

        # Add the new or updated entry
        collection.add(
            ids=[entry_id],
            documents=[text.page_content],
            metadatas=[{"date_added": datetime.now().isoformat(), "category": category }]
        )
        logging.info("Entry with ID" + entry_id + " added/updated successfully!")

    def convert_image_to_text(self, image_path, image_name):
        # get description
        with open(image_path, "rb") as image_file:
             base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai.api_key}"
        }

        payload = {
        "model": "gpt-4o",
        "messages": [
            {
            "role": "user",
            "content": [
                {
                "type": "text",
                "text": "If this is an announcement, Generate a one sentence written announcement from it in third person pov. If this is a meme or relatable content, write one sentence explaining it."
                },
                {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
                }
            ]
            }
        ],
        "max_tokens": 300
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        text = response.json()['choices'][0]['message']['content']
        #append to file in blob
        text_file = image_name.rsplit('_', 1)[0] + '.txt'
        blob_client = self.blob_service_client.get_blob_client(container=text_container_name, blob=text_file)
        existing_content = blob_client.download_blob().readall().decode("utf-8")
        new_content = existing_content + '\n' + text
        blob_client.upload_blob(new_content, overwrite=True)
        

