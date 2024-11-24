import os
import time
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

access_token = 'EAAMP7plW2yMBO7eFc3VMgi9awrZB1gI6OV8AuzDS2ir1UW5GWjutCiqbEfj7iVBmxPY8ug4CMCv8TeyOSFZA1Av3Q4ZC25P6qg1ZBeNiZB6QGvxYLoW3EpMTJSsDZB7g1zdxTo5TmOwzSb1FYabwDyFpu8z0dTBZAZAcZATpKj9ktEiHqb1PnxIZC4ZClPSXZAk3O1MM'

class InstagramScraper:
    def __init__(self, user_id, app_id, app_secret):
        self.user_id = user_id
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = access_token
        self.base_url = f"https://graph.facebook.com/v20.0/{self.user_id}"
        self.fields_1 = "{followers_count,media_count,media"
        self.fields_2 = "{media_url,media_type,children{media_url},timestamp,paging},follows_count}"
        self.output_dir = "pics"
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
            print(f"New token expires in {response.json().get('expires_in')} seconds.")
            return long_lived_token
        else:
            print(f"Error generating long-lived token: {response.status_code}, {response.text}")
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
            print("Access token refreshed.")
            return new_token
        else:
            print(f"Error refreshing token: {response.status_code}, {response.text}")
            return None

    def download_image(self, url, file_path):
        """Download an image from a given URL and save it locally."""
        response = requests.get(url)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            print(f"Image saved: {file_path}")
        else:
            print(f"Failed to download image from {url}")

    def fetch_images_from_page(self, data, username):
        """Process a page of data and fetch images."""
        try:
            for post in data.get("business_discovery", {}).get("media", {}).get("data", []):
                post_timestamp = datetime.strptime(post["timestamp"], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
                if post_timestamp < datetime.utcnow() - timedelta(days=30):
                    print("All posts within 30 days fetched")
                    return 0

                media_type = post.get('media_type')
                if media_type == "CAROUSEL_ALBUM":
                    for carousel_child in post.get("children", {}).get("data", []):
                        url = carousel_child.get("media_url")
                        child_id = carousel_child.get("id")
                        post_id = post.get('id')
                        file_path = os.path.join(self.output_dir, f"{username}_{post_id}_{child_id}.jpg")
                        if os.path.isfile(file_path):
                            print("All up to date")
                            return 0
                        self.download_image(url, file_path)
                else:
                    url = post.get("media_url")
                    post_id = post.get("id")
                    file_path = os.path.join(self.output_dir, f"{username}_{post_id}.jpg")
                    if os.path.isfile(file_path):
                        print("All up to date")
                        return 0
                    self.download_image(url, file_path)
            return 1
        except Exception as e:
            print(f"Unexpected error in fetch_images_from_page: {e}")

    def get_user_posts(self, username):
        """Fetch posts for a specific username."""
        try:
            params = {
                "fields": f'business_discovery.username({username}){self.fields_1}{self.fields_2}',
                "access_token": self.access_token,
            }

            response = requests.get(self.base_url, params=params)
            if response.status_code == 200:
                data = response.json()
                if not self.fetch_images_from_page(data, username):
                    return

                try:
                    cursors = data.get("business_discovery", {}).get('media', {}).get('paging', {}).get('cursors', {})
                    while 'after' in cursors:
                        next_page = cursors.get('after')
                        params['fields'] = f'business_discovery.username({username}){self.fields_1}.after({next_page}){self.fields_2}'
                        response = requests.get(self.base_url, params=params)
                        if response.status_code == 200:
                            data = response.json()
                            if not self.fetch_images_from_page(data, username):
                                break
                            print("Fetched from next page")
                        else:
                            print(f"Error fetching next page: {response.status_code}, {response.text}")
                            break
                except Exception as e:
                    print(f"Unexpected error during pagination: {e}")
            else:
                print(f"Error fetching user posts: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"Unexpected error in get_user_posts: {e}")

    def get_posts(self, usernames):
        """Fetch posts for a list of usernames using multithreading."""
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(self.get_user_posts, usernames)
