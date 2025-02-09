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
from models.jobScheduler import JobScheduler
from database.database import db
from PyPDF2 import PdfReader  # for extracting text from PDFs
import requests
from azure.storage.blob import BlobServiceClient
import logging
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

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
        self.visited_urls = set()

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
        logging.info("Closing")
        if self.driver:
            self.driver.quit()
        job = JobScheduler.query.get(self.job_id)
        if job:
            job.status = "Completed"
            job.error_message = reason
            db.session.commit()
        logging.info("Spider closed: %s", reason)

    def handle_pdf(self, pdf_url):
        logging.info(f"Processing PDF: {pdf_url}")
        try:
            response = requests.get(pdf_url, stream=True)
            response.raise_for_status()
            filename = f'{response.url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "")}'
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
        
        # If this is a PDF, handle it separately and do not continue with text extraction or link following.
        if response.url.endswith('.pdf') or "application/pdf" in response.headers.get('Content-Type', '').decode():
            self.handle_pdf(response.url)
            return

        # Use Selenium to render the page
        self.driver.get(response.url)
        try:
            # Wait for the <body> element to load (adjust the timeout if necessary)
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
        except Exception as e:
            logging.error(f"Error loading page {response.url}: {e}")
            return

        # Get the rendered HTML from Selenium and create a Scrapy response object
        html = self.driver.page_source
        selenium_response = HtmlResponse(
            url=response.url,
            body=html,
            encoding='utf-8',
            request=response.request
        )

        # Attempt to narrow down the extraction to a common main content container if it exists
        main_container = selenium_response.css("#DeltaPlaceHolderMain")
        container = main_container if main_container else selenium_response

        # Use a refined XPath expression to extract text while excluding boilerplate elements.
        all_text = container.xpath(
            './/text()['
            'not(ancestor::header) and '
            'not(ancestor::footer) and '
            'not(ancestor::nav) and '
            'not(ancestor::aside) and '
            'not(ancestor::*[contains(@class, "breadcrumb")]) and '
            'not(ancestor::*[contains(@class, "quick-access")]) and '
            'not(ancestor::*[contains(@class, "ms-webpart")]) and '
            'not(ancestor::*[contains(@class, "ms-notif")]) and '
            'not(ancestor::*[contains(@class, "footerlinks")]) and '
            'not(ancestor::*[contains(@class, "nav-social")]) and '
            'not(ancestor::script) and '
            'not(ancestor::style)'
            ']'
        ).getall()

        # Clean up the text: remove extra whitespace and empty strings
        cleaned_text = [text.strip() for text in all_text if text.strip()]
        full_text = '\n'.join(cleaned_text)

        # Helper function to sanitize the filename (removes illegal characters)
        def sanitize_filename(filename: str) -> str:
            invalid_chars = ['?', '/', '\\', ':', '*', '"', '<', '>', '|']
            for ch in invalid_chars:
                filename = filename.replace(ch, '_')
            return filename

        # Generate a filename based on the URL by stripping protocol and replacing problematic characters
        filename = f'{response.url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "")}.txt'
        filename = sanitize_filename(filename)
        local_filename = f'{output_folder_name}/scraped_text_{filename}'

        # Save the scraped text locally
        with open(local_filename, 'w', encoding='utf-8') as f:
            f.write(full_text)
        logging.info(f"Saved scraped text to {local_filename}")

        # Upload the text file to Azure Blob Storage
        blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=filename)
        with open(local_filename, "rb") as file:
            blob_client.upload_blob(file, overwrite=True)
        logging.info(f"Uploaded scraped text to Azure Blob Storage as {filename}")

        # Delete the local file copy after upload
        os.remove(local_filename)

        # Now, extract all links from the rendered page and follow them
        for next_page in selenium_response.css('a::attr(href)').getall():
            if next_page:
                # Convert relative URLs to absolute URLs
                next_page = response.urljoin(next_page)
                # Follow links that belong to the domain 'aub.edu.lb' and haven't been visited yet.
                if "aub.edu.lb" in next_page and next_page not in self.visited_urls:
                    self.visited_urls.add(next_page)
                    yield scrapy.Request(next_page, callback=self.parse)



# Function to run the spider
def run_spider(start_urls, job_id, azure_blob_connection_string):
    try:

        process : CrawlerProcess = CrawlerProcess(get_project_settings())
        process.crawl(DynamicTextSpider, start_urls=start_urls, job_id = job_id, connection_string = azure_blob_connection_string)
        process.start()  

    except Exception as e:
        logging.error(e)
        job = JobScheduler.query.get(job_id)
        if job:
            job.status = "Terminated"
            job.error_message = str(e)
            db.session.commit()