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

output_folder_name = "scraper_output"
container_name = "web-scraper-output"

class DynamicTextSpider(Spider):
    name = 'dynamic_text_spider'
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
        # options.add_argument('--ignore-ssl-errors=yes')
        # options.add_argument('--ignore-certificate-errors') 
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        # driver = webdriver.Remote(
        #     command_executor=standalone_chrome_url,
        #     options=options
        # )

    def closed(self, reason):     
        """Close the Selenium WebDriver when spider is closed."""
        print("Closing")
        if self.driver:
            self.driver.quit()
        job = JobScheduler.query.get(self.job_id)
        if job:
            job.status = "Completed"
            job.error_message = reason
            db.session.commit()
        print("Spider closed: %s", reason)

    def handle_pdf(self, pdf_url):
        print(f"Processing PDF: {pdf_url}")
        try:
            response = requests.get(pdf_url, stream=True)
            response.raise_for_status()
            filename = f'{response.url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "")}'
            # Save the PDF
            pdf_filename = f'{output_folder_name}/scraped_text_{filename}.pdf'

            with open(pdf_filename, 'wb') as pdf_file:
                for chunk in response.iter_content(chunk_size=1024):
                    pdf_file.write(chunk)
            print(f"Saved PDF to {pdf_filename}")

            # Extract text from the PDF
            extracted_text = self.extract_text_from_pdf(pdf_filename)

            # Save the extracted text
            local_filename = f'{output_folder_name}/scraped_text_{filename}.txt'
            with open(local_filename, 'w', encoding='utf-8') as text_file:
                text_file.write(extracted_text)

            print(f"Saved extracted text to {local_filename}")
            #Save to Azure Blob storage
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=f'{filename}.txt')
            with open(local_filename, "rb") as file:
                blob_client.upload_blob(file, overwrite=True)

            print(f"Saved extracted text to Azure Blob storage, file name: {filename}.txt")
            # Delete local copies
            os.remove(pdf_filename)
            os.remove(local_filename)

        except Exception as e:
            print(f"Error processing PDF {pdf_url}: {e}")

    @staticmethod
    def extract_text_from_pdf(pdf_path):
        try:
            reader = PdfReader(pdf_path)
            extracted_text = ""
            for page in reader.pages:
                extracted_text += page.extract_text()
            return extracted_text
        except Exception as e:
            print(f"Error extracting text from PDF {pdf_path}: {e}")
            return ""

    def parse(self, response):
        print(f"Processing URL: {response.url}")
        if response.url.endswith('.pdf') or "application/pdf" in response.headers.get('Content-Type', '').decode():
            self.handle_pdf(response.url)
            return 
        
        # Use Selenium to open the URL
        self.driver.get(response.url)

        try:
            # Wait for the <body> element to load as an example
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )

        except Exception as e:
            print(f"Error loading page {response.url}: {e}")
            return

        # Get the rendered HTML
        html = self.driver.page_source

        # Create a Scrapy response from the rendered HTML
        selenium_response = HtmlResponse(url=response.url, body=html, encoding='utf-8', request=response.request)

        # Extract all text from the page excluding scripts and styles
        all_text = selenium_response.xpath('//body//text()[not(ancestor::script or ancestor::style)]').getall()
        cleaned_text = [text.strip() for text in all_text if text.strip()]
        full_text = '\n'.join(cleaned_text)

        # Save the scraped text
        filename = f'{response.url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "")}.txt'
        local_filename = f'{output_folder_name}/scraped_text_{filename}'
        with open(local_filename, 'w', encoding='utf-8') as f:
            f.write(full_text)
        
        print(f"Saved scraped text to {local_filename}")
        # Upload to Azure blob storage
        blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=filename)
        with open(local_filename, "rb") as file:
            blob_client.upload_blob(file, overwrite=True)

        # Delete local copy
        os.remove(local_filename)
        return # REMOVE
        for next_page in selenium_response.css('a::attr(href)').getall():
            if next_page:
                next_page = response.urljoin(next_page)
                if self.start_urls[0] in next_page and next_page not in self.visited_urls:
                    self.visited_urls.add(next_page)
                    yield scrapy.Request(next_page, callback=self.parse)

# Function to run the spider
def run_spider(start_urls, job_id, azure_blob_connection_string):
    try:

        process : CrawlerProcess = CrawlerProcess(get_project_settings())
        process.crawl(DynamicTextSpider, start_urls=start_urls, job_id = job_id, connection_string = azure_blob_connection_string)
        process.start()  

    except Exception as e:
        print("Error")
        job = JobScheduler.query.get(job_id)
        if job:
            job.status = "Terminated"
            job.error_message = str(e)
            db.session.commit()