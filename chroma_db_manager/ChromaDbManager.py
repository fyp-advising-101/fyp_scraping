import openai
from chromadb import HttpClient
import os
import base64
import requests
import logging

logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",  # Define the log message format
    datefmt="%Y-%m-%d %H:%M:%S",  # Define the date format
    filename="app.log",  # Specify a file to write logs to
    filemode="a",  # Append to the file (default is 'a')
)

class ChromaDBManager:
    def __init__(self, db_path, openai_api_key):
        # settings = Settings(
        #     chroma_server_host="127.0.0.1", ### CHANGE When deploying
        #     chroma_server_http_port=3005,
        #     )
        # admin_client = AdminClient(settings=settings)
        # try:
        #     admin_client.get_tenant(name=db_path)
        # except Exception as e: # Here I tried to use the 
        #                         # chromadb.errors.NotFoundError, but was not 
        #                         # working althought the exception raised was based
        #                         # on this type
        #     admin_client.create_tenant(name=db_path)
        #     admin_client.create_database(name=db_path, tenant=db_path)
        self.client = HttpClient(host='vectordb', port=8000)
        openai.api_key = openai_api_key

    def get_or_create_collection(self, collection_name):
        """Get or create a Chroma DB collection."""
        logging.info("Fetching collection", collection_name)
        return self.client.get_or_create_collection(name=collection_name)

    def generate_embedding(self, text):
        """Generate an embedding for a given text using OpenAI API."""
        response = openai.embeddings.create(input=text, model="text-embedding-3-large")
        return response.data[0].embedding

    def add_or_update_text_entry(self, collection_name, entry_id, text):
        """Add or update an entry in the Chroma DB."""
        collection = self.get_or_create_collection(collection_name)
        logging.info("collection found:", collection_name)
        embedding = self.generate_embedding(text.page_content)
        # Check if entry already exists
        existing_entries = collection.get(ids=[entry_id])['ids']

        if entry_id in existing_entries:
            logging.info(f"Updating entry with ID: {entry_id}")
            collection.delete(ids=[entry_id])

        # Add the new or updated entry
        collection.add(
            ids=[entry_id],
            embeddings=[embedding],
            documents=[text.page_content],
            metadatas=[{"info": "default"}]
        )
        logging.info(f"Entry with ID '{entry_id}' added/updated successfully!")

    def add_or_update_image_entry(self, collection_name, entry_id, image_path):
        collection = self.get_or_create_collection(collection_name)

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
                "text": "If this is an announcement, Generate a concise written announcement from it"
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
        #print(response.json())
        text = response.json()['choices'][0]['message']['content']

        embedding = self.generate_embedding(text)

        existing_entries = collection.get(ids=[entry_id])['ids']

        if entry_id in existing_entries:
            logging.info(f"Updating entry with ID: {entry_id}")
            collection.delete(ids=[entry_id])

        # Add the new or updated entry
        collection.add(
            ids=[entry_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{"info": "default"}]
        )
        logging.info(f"Entry with ID '{entry_id}' added/updated successfully!")
    # def persist(self):
    #     """Persist the database to ensure data is saved."""
    #     self.client.persist()
