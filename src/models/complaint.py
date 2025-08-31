from src.models.user import db
from datetime import datetime
import json

class Complaint(db.Model):
    __tablename__ = 'complaints'
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(20), unique=True, nullable=False)  # e.g., 2025-0001
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_email = db.Column(db.String(120), nullable=True)
    issue_type = db.Column(db.String(100), nullable=False)  # Faulty Meter, Illegal Connection, etc.
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Open')  # Open, In Progress, Resolved, Closed
    priority = db.Column(db.String(20), nullable=False, default='Medium')  # Low, Medium, High, Critical
    location = db.Column(db.String(200), nullable=True)
    gps_coordinates = db.Column(db.String(50), nullable=True)
    
    # Relationships
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Escalation tracking
    escalation_level = db.Column(db.Integer, default=0)  # 0=None, 1=Supervisor, 2=Manager
    escalated_at = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # File attachments (stored as JSON array of file paths)
    attachments = db.Column(db.Text, nullable=True)  # JSON array of file paths
    
    # Customer feedback
    customer_satisfaction = db.Column(db.Integer, nullable=True)  # 1-5 rating
    customer_feedback = db.Column(db.Text, nullable=True)
    
    def set_attachments(self, file_paths):
        self.attachments = json.dumps(file_paths) if file_paths else None
    
    def get_attachments(self):
        return json.loads(self.attachments) if self.attachments else []
    
    def to_dict(self):
        # Get creator and assignee names safely
        creator_name = None
        assignee_name = None
        
        if self.created_by_id:
            from src.models.user import User
            creator = User.query.get(self.created_by_id)
            creator_name = creator.name if creator else None
            
        if self.assigned_to_id:
            from src.models.user import User
            assignee = User.query.get(self.assigned_to_id)
            assignee_name = assignee.name if assignee else None
        
        return {
            'id': self.id,
            'complaint_id': self.complaint_id,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'customer_email': self.customer_email,
            'issue_type': self.issue_type,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'location': self.location,
            'gps_coordinates': self.gps_coordinates,
            'created_by': creator_name,
            'assigned_to': assignee_name,
            'escalation_level': self.escalation_level,
            'escalated_at': self.escalated_at.isoformat() if self.escalated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'attachments': self.get_attachments(),
            'customer_satisfaction': self.customer_satisfaction,
            'customer_feedback': self.customer_feedback
        }
    
    def __repr__(self):
        return f'<Complaint {self.complaint_id}: {self.customer_name}>'

