from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import logging

# Configure logging to output informational messages to the console.
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Retrieve secrets from your Azure Key Vault, just as in your scraper.
VAULT_URL = "https://advising101vault.vault.azure.net"
credential = DefaultAzureCredential()
kv_client = SecretClient(vault_url=VAULT_URL, credential=credential)

# Get the connection string for Azure Blob Storage from Key Vault.
AZURE_BLOB_CONNECTION_STRING = kv_client.get_secret("AZURE-BLOB-CONNECTION-STRING").value

# Specify the container name (as used in your scraper).
CONTAINER_NAME = "web-scraper-output"

def delete_all_blobs(connection_string, container_name):
    try:
        # Create a BlobServiceClient using the connection string.
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        # Get a client for the specified container.
        container_client = blob_service_client.get_container_client(container_name)
        # List all blobs in the container.
        blobs = container_client.list_blobs()
        
        # Loop through each blob and delete it.
        for blob in blobs:
            container_client.delete_blob(blob.name)
            logging.info(f"Deleted blob: {blob.name}")
            
        logging.info("All blobs deleted successfully.")
    except Exception as e:
        logging.error(f"Error deleting blobs: {e}")

if __name__ == "__main__":
    delete_all_blobs(AZURE_BLOB_CONNECTION_STRING, CONTAINER_NAME)
