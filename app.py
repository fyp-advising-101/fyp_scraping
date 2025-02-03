from flask import Flask, request, jsonify 
from flask_cors import CORS
import datetime
from concurrent.futures import ThreadPoolExecutor
from database.database import db
from website_crawler.website_crawler.spiders.scraper import run_spider
from instagram_content_getter.get_posts import get_posts
from text_file_processor.TextFileProcessor import TextFileProcessor
from instragram_scraper.InstagramScraper import InstagramScraper
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

db_path = 'chroma_db'


from dotenv import load_dotenv
import os
import logging

# Configure the logging
logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",  # Define the log message format
    datefmt="%Y-%m-%d %H:%M:%S",  # Define the date format
    filename="app.log",  # Specify a file to write logs to
    filemode="a",  # Append to the file (default is 'a')
)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

VAULT_URL = "https://advising101vault.vault.azure.net"
credential = DefaultAzureCredential()
client = SecretClient(vault_url=VAULT_URL, credential=credential)
app.config['SQLALCHEMY_DATABASE_URI'] =  client.get_secret("MYSQL-CONNECTION-STRING").value

db.init_app(app)

load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID")
APP_SECRET = os.getenv("APP_SECRET")
APP_ID = os.getenv("APP_ID")
AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
debug = os.getenv("DEBUG", "False")  


with app.app_context():
    from models.jobScheduler import JobScheduler
    from models.scrapeTarget import ScrapeTarget

    if app.config["SQLALCHEMY_DATABASE_URI"]:
        db.create_all()
    

@app.route('/website_scrape', methods=['GET'])
def scrape():
        try:
            scrape_targets = ScrapeTarget.query.filter_by(type='website').all()
            urls_to_scrape = [target.url for target in scrape_targets]

            # if not urls_to_scrape:
            #     return jsonify({'error': 'No websites to scrape found in the database.'}), 404 #REMOVE

            today = datetime.date.today()
            # task : JobScheduler = JobScheduler.query.filter_by(task_name='Website Scrape').filter(
            #     db.func.date(JobScheduler.scheduled_date) == today).first() # REMOVE

            task : JobScheduler = JobScheduler.query.filter_by(task_name='Website Scrape').first() # REMOVE

            if task:
                # Update the status to 'running'
                task.status = 'Running'
                db.session.commit()
            else:
                return jsonify({'error': 'No website scrapping task scheduled'}), 404

            # Start the scraper in a separate thread to avoid blocking
            def run_scraper():
                with app.app_context():
                    try:
                        run_spider(urls_to_scrape, task.id, AZURE_BLOB_CONNECTION_STRING)
                    except Exception as e:
                        logging.error(f"Error while starting spider: {e}")
    
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(run_scraper)

            def run_text_file_processor():
                with app.app_context():
                    try:
                        TextFileProcessor(db_path, OPENAI_API_KEY, task.id, AZURE_BLOB_CONNECTION_STRING).process_text_files()
                    except Exception as e:
                        logging.error(f"Error while starting text file processor: {e}")

            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(run_text_file_processor)
            

                
            return jsonify({'message': f'Scraping started for URLs: {urls_to_scrape}', 'task_name': task.task_name}), 200
        except Exception as e:
            logging.error(f'Error while scraping websites: {e}')
            db.session.rollback()
            return jsonify({'message': f'Error while scrapping websites: {e}'}), 200
    
        
@app.route("/instagram_scrape", methods = ['GET'])
def instagram_scrape():
    try:
        scrape_targets = ScrapeTarget.query.filter_by(type='instagram').all()
        accounts_to_scrape = [target.url for target in scrape_targets]

        if not accounts_to_scrape:
            return jsonify({'error': 'No accounts to get posts from found in the database.'}), 404
        

        today = datetime.date.today()
        task : JobScheduler = JobScheduler.query.filter_by(task_name='Get Instagram Content').filter(
            db.func.date(JobScheduler.scheduled_date) == today).first()
    
        if task:
                # Update the status to 'running'
                task.status = 'Running'
                db.session.commit()
                job_id = task.id
        else:
            return jsonify({'error': 'No instagram content fetching task scheduled'}), 404


        instagram_scraper = InstagramScraper(INSTAGRAM_USER_ID, APP_ID, APP_SECRET, AZURE_BLOB_CONNECTION_STRING)
        instagram_scraper.get_posts(accounts_to_scrape)

        def run_image_file_processor():
                with app.app_context():
                    try:
                        TextFileProcessor(db_path, OPENAI_API_KEY, task.id, AZURE_BLOB_CONNECTION_STRING).process_image_files()
                    except Exception as e:
                        logging.error(f"Error in image image processing: {e}")

        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(run_image_file_processor)

        return jsonify({'message': f'Fetching started for Accounts: {accounts_to_scrape}', 'task_name': 'Get Instagram Content'}), 200
        #return jsonify({'message': f'Fetching started for Accounts: {target_accounts}', 'task_name': {task.task_name}}), 200
    except Exception as e:
        logging.error(f'Error while scraping websites: {e}')
        db.session.rollback()
        return jsonify({'message': f'Error while scrapping websites: {e}'}), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80)