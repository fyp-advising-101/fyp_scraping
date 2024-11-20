import openai
from chromadb import Client
from chromadb.config import Settings


class ChromaDBManager:
    def __init__(self, db_path, openai_api_key):
        self.client = Client(Settings(persist_directory=db_path))
        openai.api_key = openai_api_key

    def get_or_create_collection(self, collection_name):
        """Get or create a Chroma DB collection."""
        return self.client.get_or_create_collection(name=collection_name)

    def generate_embedding(self, text):
        """Generate an embedding for a given text using OpenAI API."""
        response = openai.Embedding.create(input=text, model="text-embedding-3-large")
        return response['data'][0]['embedding']

    def add_or_update_entry(self, collection_name, entry_id, text):
        """Add or update an entry in the Chroma DB."""
        collection = self.get_or_create_collection(collection_name)
        embedding = self.generate_embedding(text)

        # Check if entry already exists
        existing_entries = collection.get(ids=[entry_id])['ids']

        if entry_id in existing_entries:
            print(f"Updating entry with ID: {entry_id}")
            collection.delete(ids=[entry_id])

        # Add the new or updated entry
        collection.add(
            ids=[entry_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{}]
        )
        print(f"Entry with ID '{entry_id}' added/updated successfully!")

    def persist(self):
        """Persist the database to ensure data is saved."""
        self.client.persist()
