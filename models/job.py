from database.database import db

class Job(db.Model):
    __tablename__ = 'job'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_name = db.Column(db.String(255), nullable=False)
    task_id = db.Column(db.String(255), nullable=False)
    scheduled_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Integer, nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
