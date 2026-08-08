from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class AnalysisHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    input_file = db.Column(db.String(255), nullable=False)
    pdf_path = db.Column(db.String(255))
    metrics = db.Column(db.Text)  # JSON string of metrics
    rows_original = db.Column(db.Integer, nullable=True)
    rows_cleaned = db.Column(db.Integer, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AnalysisHistory {self.input_file}>"

