from database.database import db

class ScrapeTarget(db.Model):
    __tablename__ = 'scrape_targets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    url = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime)