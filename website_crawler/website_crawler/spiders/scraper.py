# scraper.py

from scrapy import Spider
from scrapy.linkextractors import LinkExtractor
from scrapy.crawler import CrawlerProcess , CrawlerRunner 
from scrapy.utils.project import get_project_settings
from scrapy.http import HtmlResponse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import scrapy
from twisted.internet import reactor, defer
import os
from models.job import Job
from database.database import db
from PyPDF2 import PdfReader  # for extracting text from PDFs
import requests
from azure.storage.blob import BlobServiceClient
import logging
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from urllib.parse import urlparse
import sqlite3


# Configure the logging
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

output_folder_name = "scraper_output"
container_name = "web-scraper-output"
standalone_chrome_url= client.get_secret("SELENIUM-URL").value 
#standalone_chrome_url = https://selenium.bluedune-c06522b4.uaenorth.azurecontainerapps.io/wd/hub





class DynamicTextSpider(Spider):
    name = 'dynamic_text_spider'
    allowed_domains = ['aub.edu.lb']
    def __init__(self, start_urls, job_id, connection_string ,*args, **kwargs):
        super(DynamicTextSpider, self).__init__(*args, **kwargs)
        self.start_urls = start_urls
        #self.start_urls = ['https://www.aub.edu.lb/registrar/Documents/catalogue/undergraduate22-23/ece.pdf']
        self.job_id = job_id
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.visited_urls = self.load_visited_urls()

        os.makedirs(output_folder_name, exist_ok=True)

        options = webdriver.ChromeOptions()
        options.add_argument("--headless") 
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # comment when testing
        options.add_argument('--ignore-ssl-errors=yes')
        options.add_argument('--ignore-certificate-errors') 
        # self.driver = webdriver.Chrome(
        #     service=Service(ChromeDriverManager().install()),
        #     options=options
        # )
        self.driver = webdriver.Remote(
            command_executor=standalone_chrome_url,
            options=options
        )

    def closed(self, reason):     
        """Close the Selenium WebDriver when spider is closed."""
        print("Scraping finished!")
        logging.info("Closing")
        if self.driver:
            self.driver.quit()
        job = Job.query.get(self.job_id)
        if job:
            job.status = 2
            job.error_message = reason
            db.session.commit()
        logging.info("Spider closed: %s", reason)

    def init_visited_db(self):
        conn = sqlite3.connect("visited_urls.db")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS visited (url TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

    def load_visited_urls(self):
        self.init_visited_db()
        conn = sqlite3.connect("visited_urls.db")
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM visited")
        rows = cursor.fetchall()
        conn.close()
        return set(row[0] for row in rows)

    def save_visited_url(self, url):
        try:
            conn = sqlite3.connect("visited_urls.db")
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO visited (url) VALUES (?)", (url,))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error saving visited url {url}: {e}")


    def handle_pdf(self, pdf_url):
        logging.info(f"Processing PDF: {pdf_url}")
        try:
            response = requests.get(pdf_url, stream=True)
            response.raise_for_status()
            filename = f'{response.url.replace("https://", "").replace("www.","").replace("http://", "").replace("/", "_").replace(":", "")}'
            # Save the PDF
            pdf_filename = f'{output_folder_name}/scraped_text_{filename}.pdf'

            with open(pdf_filename, 'wb') as pdf_file:
                for chunk in response.iter_content(chunk_size=1024):
                    pdf_file.write(chunk)
            logging.info(f"Saved PDF to {pdf_filename}")

            # Extract text from the PDF
            extracted_text = self.extract_text_from_pdf(pdf_filename)

            # Save the extracted text
            local_filename = f'{output_folder_name}/scraped_text_{filename}.txt'
            with open(local_filename, 'w', encoding='utf-8') as text_file:
                text_file.write(extracted_text)

            logging.info(f"Saved extracted text to {local_filename}")
            #Save to Azure Blob storage
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=f'{filename}.txt')
            with open(local_filename, "rb") as file:
                blob_client.upload_blob(file, overwrite=True)

            logging.info(f"Saved extracted text to Azure Blob storage, file name: {filename}.txt")
            # Delete local copies
            os.remove(pdf_filename)
            os.remove(local_filename)

        except Exception as e:
            logging.error(f"Error processing PDF {pdf_url}: {e}")

    @staticmethod
    def extract_text_from_pdf(pdf_path):
        try:
            reader = PdfReader(pdf_path)
            extracted_text = ""
            for page in reader.pages:
                extracted_text += page.extract_text()
            return extracted_text
        except Exception as e:
            logging.error(f"Error extracting text from PDF {pdf_path}: {e}")
            return ""

    def parse(self, response):
        logging.info(f"Processing URL: {response.url}")
        
        if response.url.endswith('.pdf') or "application/pdf" in response.headers.get('Content-Type', '').decode():
            self.handle_pdf(response.url)
            return

        try:
            self.driver.get(response.url)
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
        except Exception as e:
            logging.error(f"Error loading page {response.url}: {e}")
            return

        html = self.driver.page_source
        # with open("debug.html", "a", encoding="utf-8") as f:
        #     f.write(f"Page URL: {response.url}\n\n")
        #     f.write(html)
        selenium_response = HtmlResponse(
            url=response.url,
            body=html,
            encoding='utf-8',
            request=response.request
        )
        detected_links = selenium_response.css('a::attr(href)').getall()
        for link in detected_links:
            logging.info(f"Detected page: {link}")

        try:
            main_container = selenium_response.css("#DeltaPlaceHolderMain")
            container = main_container if main_container else selenium_response.css("body")
            all_text = container.xpath(
                './/text()['
                'not(ancestor::header) and '
                'not(ancestor::footer) and '
                'not(ancestor::nav) and '
                'not(ancestor::*[contains(@class, "breadcrumb")]) and '
                'not(ancestor::*[contains(@class, "quick-access")]) and '
                'not(ancestor::*[contains(@class, "ms-notif")]) and '
                'not(ancestor::*[contains(@class, "footerlinks")]) and '
                'not(ancestor::*[contains(@class, "nav-social")]) and '
                'not(ancestor::script) and '
                'not(ancestor::style)'
                ']'
            ).getall()
            cleaned_text = [text.strip() for text in all_text if text.strip()]
            full_text = '\n'.join(cleaned_text)

            def sanitize_filename(filename: str) -> str:
                invalid_chars = ['?', '/', '\\', ':', '*', '"', '<', '>', '|']
                for ch in invalid_chars:
                    filename = filename.replace(ch, '_')
                return filename

            filename = f'{response.url.replace("https://", "").replace("www.","").replace("http://", "").replace("/", "_").replace(":", "")}.txt'
            filename = sanitize_filename(filename)
            local_filename = f'{output_folder_name}/scraped_text_{filename}'

            with open(local_filename, 'w', encoding='utf-8') as f:
                f.write(full_text)
            logging.info(f"Saved scraped text to {local_filename}")

            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=filename)
            with open(local_filename, "rb") as file:
                blob_client.upload_blob(file, overwrite=True)
            logging.info(f"Uploaded scraped text to Azure Blob Storage as {filename}")

            os.remove(local_filename)
        except Exception as e:
            logging.error(f"Error processing page content from {response.url}: {e}")

        for next_page in selenium_response.css('a::attr(href)').getall():
            if next_page:
                if next_page.startswith("mailto:") or next_page.startswith("tel:"):
                    continue
                full_url = response.urljoin(next_page)
                parsed = urlparse(full_url)
                domain = parsed.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                if domain != "aub.edu.lb":
                    self.logger.debug(f"Skipping non-target domain: {full_url}")
                    continue
                if full_url not in self.visited_urls:
                    self.visited_urls.add(full_url)
                    self.save_visited_url(full_url)
                    yield scrapy.Request(full_url, callback=self.parse)






# Function to run the spider
def run_spider(start_urls, job_id, azure_blob_connection_string):
    try:

        process : CrawlerProcess = CrawlerProcess(get_project_settings())
        process.crawl(DynamicTextSpider, start_urls=start_urls, job_id = job_id, connection_string = azure_blob_connection_string)
        process.start()  

    except Exception as e:
        logging.error(e)
        job = Job.query.get(job_id)
        if job:
            job.status = -1
            job.error_message = str(e)
            db.session.commit()