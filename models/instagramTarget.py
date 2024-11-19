from database.database import db

class InstagramTarget(db.Model):
    __tablename__ = 'instagram_targets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    username = db.Column(db.String, nullable=False)
