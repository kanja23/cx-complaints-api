from src.models.user import db
from datetime import datetime, date
import json

class WorkforceEntry(db.Model):
    __tablename__ = 'workforce_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    shift_date = db.Column(db.Date, nullable=False, default=date.today)
    
    # Attendance tracking
    check_in_time = db.Column(db.Time, nullable=True)
    check_out_time = db.Column(db.Time, nullable=True)
    check_in_location = db.Column(db.String(200), nullable=True)
    check_out_location = db.Column(db.String(200), nullable=True)
    check_in_gps = db.Column(db.String(50), nullable=True)
    check_out_gps = db.Column(db.String(50), nullable=True)
    
    # Status tracking
    status = db.Column(db.String(50), nullable=False, default='Scheduled')  # Scheduled, Present, Absent, Late, On Leave
    
    # Task assignments (stored as JSON array)
    assigned_tasks = db.Column(db.Text, nullable=True)  # JSON array of tasks
    completed_tasks = db.Column(db.Text, nullable=True)  # JSON array of completed tasks
    
    # Work location
    work_location = db.Column(db.String(200), nullable=True)
    work_area_gps = db.Column(db.String(50), nullable=True)
    
    # Notes and comments
    notes = db.Column(db.Text, nullable=True)
    supervisor_notes = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    staff_member = db.relationship('User', backref='workforce_entries')
    
    def set_assigned_tasks(self, tasks):
        self.assigned_tasks = json.dumps(tasks) if tasks else None
    
    def get_assigned_tasks(self):
        return json.loads(self.assigned_tasks) if self.assigned_tasks else []
    
    def set_completed_tasks(self, tasks):
        self.completed_tasks = json.dumps(tasks) if tasks else None
    
    def get_completed_tasks(self):
        return json.loads(self.completed_tasks) if self.completed_tasks else []
    
    def calculate_hours_worked(self):
        if self.check_in_time and self.check_out_time:
            # Convert to datetime for calculation
            check_in = datetime.combine(self.shift_date, self.check_in_time)
            check_out = datetime.combine(self.shift_date, self.check_out_time)
            
            # Handle overnight shifts
            if check_out < check_in:
                check_out = datetime.combine(self.shift_date + timedelta(days=1), self.check_out_time)
            
            duration = check_out - check_in
            return duration.total_seconds() / 3600  # Return hours as float
        return 0
    
    def to_dict(self):
        # Get staff member info safely
        staff_name = None
        staff_number = None
        
        if self.staff_id:
            from src.models.user import User
            staff = User.query.get(self.staff_id)
            if staff:
                staff_name = staff.name
                staff_number = staff.staff_number
        
        return {
            'id': self.id,
            'staff_id': self.staff_id,
            'staff_name': staff_name,
            'staff_number': staff_number,
            'shift_date': self.shift_date.isoformat() if self.shift_date else None,
            'check_in_time': self.check_in_time.strftime('%H:%M') if self.check_in_time else None,
            'check_out_time': self.check_out_time.strftime('%H:%M') if self.check_out_time else None,
            'check_in_location': self.check_in_location,
            'check_out_location': self.check_out_location,
            'check_in_gps': self.check_in_gps,
            'check_out_gps': self.check_out_gps,
            'status': self.status,
            'assigned_tasks': self.get_assigned_tasks(),
            'completed_tasks': self.get_completed_tasks(),
            'work_location': self.work_location,
            'work_area_gps': self.work_area_gps,
            'notes': self.notes,
            'supervisor_notes': self.supervisor_notes,
            'hours_worked': self.calculate_hours_worked(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        staff_name = "Unknown"
        if self.staff_id:
            from src.models.user import User
            staff = User.query.get(self.staff_id)
            if staff:
                staff_name = staff.name
        return f'<WorkforceEntry {staff_name} - {self.shift_date}>'

