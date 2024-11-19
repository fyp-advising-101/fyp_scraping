import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

APP_SECRET = os.getenv("APP_SECRET")
APP_ID = os.getenv("APP_ID")
debug = os.getenv("DEBUG", "False")  

access_token = 'EAAMP7plW2yMBO7eFc3VMgi9awrZB1gI6OV8AuzDS2ir1UW5GWjutCiqbEfj7iVBmxPY8ug4CMCv8TeyOSFZA1Av3Q4ZC25P6qg1ZBeNiZB6QGvxYLoW3EpMTJSsDZB7g1zdxTo5TmOwzSb1FYabwDyFpu8z0dTBZAZAcZATpKj9ktEiHqb1PnxIZC4ZClPSXZAk3O1MM'

def short_to_long_lived_token(access_token):
    url = "https://graph.instagram.com/access_token"
    params = {
        'grant_type' : 'ig_exchange_token',
        'client_secret' : APP_SECRET,
        'access_token' : access_token
    }
    response = requests.get(url, params)
    if response.status_code == 200:
        long_lived_token = response.json().get('access_token')
        print(f"New token expires in {response.json().get('expires_in')}")
        return long_lived_token
    else:
        print(f"Error generating long lived token: {response.status_code}, {response.text}")
        return None

def refresh_access_token(access_token):
    url = f"https://graph.facebook.com/v20.0/oauth/access_token"
    params = {
        'grant_type': 'fb_exchange_token',
        'fb_exchange_token': access_token,
        'client_id': APP_ID,
        'client_secret': APP_SECRET
    }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        new_token = response.json().get('access_token')
        return new_token
    else:
        print(f"Error refreshing token: {response.status_code}, {response.text}")
        return None


while True:
    # Here you might want to add logic to check if the token is about to expire
    print("Refreshing access token...")
    access_token = refresh_access_token(access_token)
    if access_token:
        print(f"New Access Token: {access_token}")
    time.sleep(90000)  # Sleep for 25 hours

#print(short_to_long_lived_token(access_token))