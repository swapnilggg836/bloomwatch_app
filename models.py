from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class AnalysisHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    input_file = db.Column(db.String(255), nullable=False)
    pdf_path = db.Column(db.String(255))
    metrics = db.Column(db.Text)  # JSON string of metrics
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_metrics_dict(self):
        if self.metrics:
            try:
                return json.loads(self.metrics)
            except Exception:
                return {}
        return {}

    def __repr__(self):
        return f"<AnalysisHistory {self.input_file}>"
