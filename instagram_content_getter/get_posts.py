import requests
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",  # Define the log message format
    datefmt="%Y-%m-%d %H:%M:%S",  # Define the date format
    filename="app.log",  # Specify a file to write logs to
    filemode="a",  # Append to the file (default is 'a')
)

load_dotenv()

INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID")

def download_image(url, file_path):
    response = requests.get(url)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            f.write(response.content)
        logging.info(f"Image saved: {file_path}")
    else:
        logging.error(f"Failed to download image from {url}")

# Because the responses are paginated
def fetch_images_from_page(data, username):
    for post in data["business_discovery"]["media"]["data"]:
        post_timestamp = datetime.strptime(post["timestamp"], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
        if post_timestamp < datetime.utcnow() - timedelta(days=30):
            logging.info("All posts within 30 days fetched")
            return 0
        media_type = post['media_type']
        if media_type == "CAROUSEL_ALBUM":
            for carousel_child in post["children"]["data"]:
                url = carousel_child["media_url"]
                child_id = carousel_child["id"]
                post_id = post['id']
                file_path = os.path.join("pics", f"{username}_{post_id}_{child_id}.jpg")
                if os.path.isfile(file_path):
                    logging.info("All up to date")
                    return 0
                download_image(url, file_path)
        else:
            url = post["media_url"]
            id = post["id"]
            file_path = os.path.join("pics", f"{username}_{id}.jpg")
            if os.path.isfile(file_path):
                logging.info("All up to date")
                return 0
            download_image(url, file_path)

    return 1

def get_user_posts(username):
    try:
        # Base URL for the Graph API call
        url = f"https://graph.facebook.com/v20.0/{INSTAGRAM_USER_ID}"

        fields_1 = "{followers_count,media_count, media"
        fields_2 = "{media_url, media_type, children{media_url}, timestamp, paging}, follows_count}"
        # Query parameters
        params = {
            "fields": f'business_discovery.username({username}){fields_1}{fields_2}',
            "access_token": "EAAMP7plW2yMBO48UAE88ilZAUZCCZBsdZAHyNqJxtEfpwsKbem5pDF604kRCLC3pO2oLtWNmiMyr37NbOdg4yZBEmt0wtZA3dQEszyWZCcAKPQpqcmxIwqpUZCFcBn6yPi2osyW7MarbnbbMxRjRORinbZBvKuaphyVvzn1dt4f6fAbevnSyBLwZBwWqIuJ4B1EK7AyfH0SZCpx"
        }

        # Make the GET request to the Instagram Graph API
        response = requests.get(url, params=params)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            if not fetch_images_from_page(data, username):
                return
            try:
                cursors = data["business_discovery"]['media']['paging']['cursors']
                while 'after' in cursors:
                    next_page = cursors['after']
                    params['fields'] = f'business_discovery.username({username}){fields_1}.after({next_page}){fields_2}'
                    response = requests.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if not fetch_images_from_page(data, username):
                            break
                    else:
                        logging.error(f"Error: {response.status_code}, {response.text}")
            except Exception as e:
                logging.error(e)
            
            
        else:
            # Handle errors
            logging.error(f"Error: {response.status_code}, {response.text}")
    except Exception as e:
        logging.error(e)

def get_posts(accounts):
    # Using ThreadPoolExecutor for concurrent execution
    username_list = [target.username for target in accounts]
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(get_user_posts, username_list)

