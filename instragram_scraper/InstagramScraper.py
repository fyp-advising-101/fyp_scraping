import os
import time
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
import logging

logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",  # Define the log message format
    datefmt="%Y-%m-%d %H:%M:%S",  # Define the date format
    filename="app.log",  # Specify a file to write logs to
    filemode="a",  # Append to the file (default is 'a')
)

load_dotenv()

access_token = 'EAAMP7plW2yMBO7eFc3VMgi9awrZB1gI6OV8AuzDS2ir1UW5GWjutCiqbEfj7iVBmxPY8ug4CMCv8TeyOSFZA1Av3Q4ZC25P6qg1ZBeNiZB6QGvxYLoW3EpMTJSsDZB7g1zdxTo5TmOwzSb1FYabwDyFpu8z0dTBZAZAcZATpKj9ktEiHqb1PnxIZC4ZClPSXZAk3O1MM'
container_name = "instagram-scraper-output"
text_container_name = "processed-instagram-scraper-output"

class InstagramScraper:
    def __init__(self, user_id, app_id, app_secret, connection_string):
        self.user_id = user_id
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = access_token
        self.base_url = f"https://graph.facebook.com/v20.0/{self.user_id}"
        self.fields_1 = "{followers_count,media_count,media"
        self.fields_2 = "{media_url,media_type,children{media_url, media_type},timestamp,paging, caption},follows_count}"
        self.output_dir = "pics"
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        os.makedirs(self.output_dir, exist_ok=True)

    def short_to_long_lived_token(self, access_token):
        """Exchange a short-lived token for a long-lived token."""
        url = "https://graph.instagram.com/access_token"
        params = {
            'grant_type': 'ig_exchange_token',
            'client_secret': self.app_secret,
            'access_token': access_token
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            long_lived_token = response.json().get('access_token')
            logging.info(f"New token expires in {response.json().get('expires_in')} seconds.")
            return long_lived_token
        else:
            logging.error(f"Error generating long-lived token: {response.status_code}, {response.text}")
            return None

    def refresh_access_token(self):
        """Refresh an expired or expiring access token."""
        url = "https://graph.facebook.com/v20.0/oauth/access_token"
        params = {
            'grant_type': 'fb_exchange_token',
            'fb_exchange_token': os.getenv("ACCESS_TOKEN"),
            'client_id': self.app_id,
            'client_secret': self.app_secret
        }
        response = requests.post(url, params=params)
        if response.status_code == 200:
            new_token = response.json().get('access_token')
            logging.info("Access token refreshed.")
            return new_token
        else:
            logging.error(f"Error refreshing token: {response.status_code}, {response.text}")
            return None

    def store_image(self, url, local_file_path, filename):
        """Download an image from a given URL and save it locally."""
        response = requests.get(url)
        if response.status_code == 200:
            with open(local_file_path, 'wb') as f:
                f.write(response.content)
            logging.info(f"Image saved locally: {local_file_path}")
        else:
            logging.error(f"Failed to download image from {url}")

        blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=filename)
        try:
            with open(local_file_path, "rb") as file:
                blob_client.upload_blob(file, overwrite=False)

            logging.info(f"Uploaded to Azure Blob storage: {url}")
        
        except ResourceExistsError:
            return 0
        except Exception as e:
            logging.error(f"failed to upload to Azure Blob storage: {url}")
            logging.error(f"Reason: {e}")
        os.remove(local_file_path)
        return 1

    def fetch_images_from_page(self, data, username, category):
        """Process a page of data and fetch images."""
        try:
            for post in data.get("business_discovery", {}).get("media", {}).get("data", []):
                post_timestamp = datetime.strptime(post["timestamp"], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
                if post_timestamp < datetime.utcnow() - timedelta(days=3):
                    logging.info("All posts within 3 days fetched")
                    return 0

                media_type = post.get('media_type')
                # Save caption to txt file on processed_instagram_scraper_output container
                caption = post.get('caption')
                post_id = post.get('id')
                local_filename = f'{category}_{username}_{post_id}.txt'
                with open(local_filename, 'w', encoding='utf-8') as caption_text_file:
                    caption_text_file.write(caption)

                blob_client = self.blob_service_client.get_blob_client(container=text_container_name, blob=local_filename)
                with open(local_filename, "rb") as file:
                    blob_client.upload_blob(file, overwrite=True)

                os.remove(local_filename)
                if media_type == "VIDEO":
                    continue
                
                if media_type == "CAROUSEL_ALBUM":
                    for carousel_child in post.get("children", {}).get("data", []):
                        if carousel_child.get("media_type") == "VIDEO":
                            continue
                        url = carousel_child.get("media_url")
                        child_id = carousel_child.get("id")
                        post_id = post.get('id')
                        filename = f"{category}_{username}_{post_id}_{child_id}.jpg"
                        file_path = os.path.join(self.output_dir, f"{category}_{username}_{post_id}_{child_id}.jpg")
                        if not self.store_image(url, file_path, filename):
                            logging.info("All up to date")
                            return 0
                else:
                    url = post.get("media_url")
                    post_id = post.get("id")
                    filename = f"{category}_{username}_{post_id}_.jpg"
                    file_path = os.path.join(self.output_dir, f"{category}_{username}_{post_id}_.jpg")
                    if not self.store_image(url, file_path, filename):
                        logging.info("All up to date")
                        return 0
            return 1
        except Exception as e:
            logging.error(f"Unexpected error in fetch_images_from_page: {e}")

    def get_user_posts(self, target):
        """Fetch posts for a specific username."""
        username = target[0]
        category = target[1]
        try:
            params = {
                "fields": f'business_discovery.username({username}){self.fields_1}{self.fields_2}',
                "access_token": self.access_token,
            }

            response = requests.get(self.base_url, params=params)
            if response.status_code == 200:
                data = response.json()
                if not self.fetch_images_from_page(data, username, category):
                    return

                try:
                    cursors = data.get("business_discovery", {}).get('media', {}).get('paging', {}).get('cursors', {})
                    while 'after' in cursors:
                        next_page = cursors.get('after')
                        params['fields'] = f'business_discovery.username({username}){self.fields_1}.after({next_page}){self.fields_2}'
                        response = requests.get(self.base_url, params=params)
                        if response.status_code == 200:
                            data = response.json()
                            if not self.fetch_images_from_page(data, username, category):
                                break
                        else:
                            logging.error(f"Error fetching next page: {response.status_code}, {response.text}")
                            break
                except Exception as e:
                    logging.error(f"Unexpected error during pagination: {e}")
            else:
                logging.error(f"Error fetching user posts: {response.status_code}, {response.text}")
        except Exception as e:
            logging.error(f"Unexpected error in get_user_posts: {e}")

    def get_posts(self, targets):
        """Fetch posts for a list of usernames using multithreading."""
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(self.get_user_posts, targets)
