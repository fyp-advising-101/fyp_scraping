from flask import Flask, request, jsonify 
from flask_cors import CORS
import threading
import datetime
from database.database import db
from website_crawler.website_crawler.spiders.scraper import run_spider
from instagram_content_getter.get_posts import get_posts

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DB_CONFIG = "sqlite:///database.db"
app.config["SQLALCHEMY_DATABASE_URI"] = DB_CONFIG
db.init_app(app)

with app.app_context():
    from models.jobScheduler import JobScheduler
    from models.scrapeTarget import ScrapeTarget
    from models.instagramTarget import InstagramTarget

    if app.config["SQLALCHEMY_DATABASE_URI"]:
        db.create_all()
    
def run_scraper_in_thread(urls_to_scrape, job_id):
    thread = threading.Thread(target=run_spider_in_context, args=(urls_to_scrape, job_id))
    thread.start()

def run_spider_in_context(urls_to_scrape, job_id):
    with app.app_context():
        run_spider(urls_to_scrape, job_id)

@app.route('/website_scrape', methods=['GET'])
def scrape():
        try:
            scrape_targets = ScrapeTarget.query.filter_by(type='website').all()
            urls_to_scrape = [target.url for target in scrape_targets]

            if not urls_to_scrape:
                return jsonify({'error': 'No websites to scrape found in the database.'}), 404

            today = datetime.date.today()
            task : JobScheduler = JobScheduler.query.filter_by(task_name='Website Scrape').filter(
                db.func.date(JobScheduler.scheduled_date) == today).first()

            if task:
                # Update the status to 'running'
                task.status = 'Running'
                db.session.commit()
                job_id = task.id
            else:
                return jsonify({'error': 'No website scrapping task scheduled'}), 404

            # Start the scraper in a separate thread to avoid blocking
            run_scraper_in_thread(urls_to_scrape, job_id)

            return jsonify({'message': f'Scraping started for URLs: {urls_to_scrape}', 'task_name': task.task_name}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': f'Error while starting scrape, Exception {e}'}), 200
        
@app.route("/instagram_content_getter", methods = ['GET'])
def instagram_content_getter():
    try:
        target_accounts = InstagramTarget.query.all()
        print(target_accounts)

        if not target_accounts:
            return jsonify({'error': 'No accounts to get posts from found in the database.'}), 404
        
        #Commented Out for testing..

        # today = datetime.date.today()
        # task : JobScheduler = JobScheduler.query.filter_by(task_name='Get Instagram Content').filter(
        #     db.func.date(JobScheduler.scheduled_date) == today).first()
    
        # if task:
        #         # Update the status to 'running'
        #         task.status = 'Running'
        #         db.session.commit()
        #         job_id = task.id
        # else:
        #     return jsonify({'error': 'No instagram content fetching task scheduled'}), 404

        
        get_posts(target_accounts)

        return jsonify({'message': f'Fetching started for Accounts: {target_accounts}', 'task_name': 'Get Instagram Content'}), 200
    except Exception as e:
        print(e)
        db.session.rollback()
        return jsonify({'message': f'Error while starting scrape, Exception {e}'}), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3001)