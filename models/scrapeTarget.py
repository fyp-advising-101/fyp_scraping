from database.database import db

class ScrapeTarget(db.Model):
    __tablename__ = 'scrape_targets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(255), nullable=False)
    frequency = db.Column(db.Float)
    category = db.Column(db.String(255))
    created_at = db.Column(db.DateTime)