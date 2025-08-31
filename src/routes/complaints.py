from flask import Blueprint, request, jsonify, session
from src.models.user import User, db
from src.models.complaint import Complaint
from src.routes.auth import login_required
from datetime import datetime, timedelta
import os

complaints_bp = Blueprint('complaints', __name__)

def generate_complaint_id():
    """Generate unique complaint ID in format YYYY-NNNN"""
    year = datetime.now().year
    last_complaint = Complaint.query.filter(
        Complaint.complaint_id.like(f'{year}-%')
    ).order_by(Complaint.complaint_id.desc()).first()
    
    if last_complaint:
        last_number = int(last_complaint.complaint_id.split('-')[1])
        new_number = last_number + 1
    else:
        new_number = 1
    
    return f'{year}-{new_number:04d}'

@complaints_bp.route('/', methods=['GET'])
@login_required
def get_complaints():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        priority = request.args.get('priority')
        search = request.args.get('search')
        
        query = Complaint.query
        
        # Apply filters
        if status and status != 'All':
            query = query.filter(Complaint.status == status)
        if priority and priority != 'All':
            query = query.filter(Complaint.priority == priority)
        if search:
            query = query.filter(
                (Complaint.customer_name.contains(search)) |
                (Complaint.complaint_id.contains(search)) |
                (Complaint.description.contains(search))
            )
        
        # Order by creation date (newest first)
        query = query.order_by(Complaint.created_at.desc())
        
        # Paginate
        complaints = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'complaints': [complaint.to_dict() for complaint in complaints.items],
            'total': complaints.total,
            'pages': complaints.pages,
            'current_page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@complaints_bp.route('/', methods=['POST'])
@login_required
def create_complaint():
    try:
        data = request.get_json()
        
        required_fields = ['customer_name', 'customer_phone', 'issue_type', 'description']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        complaint = Complaint(
            complaint_id=generate_complaint_id(),
            customer_name=data['customer_name'],
            customer_phone=data['customer_phone'],
            customer_email=data.get('customer_email'),
            issue_type=data['issue_type'],
            description=data['description'],
            priority=data.get('priority', 'Medium'),
            location=data.get('location'),
            gps_coordinates=data.get('gps_coordinates'),
            created_by_id=session['user_id']
        )
        
        # Set assigned user if provided
        if data.get('assigned_to_id'):
            complaint.assigned_to_id = data['assigned_to_id']
        
        # Handle file attachments
        if data.get('attachments'):
            complaint.set_attachments(data['attachments'])
        
        db.session.add(complaint)
        db.session.commit()
        
        return jsonify({
            'message': 'Complaint created successfully',
            'complaint': complaint.to_dict()
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@complaints_bp.route('/<int:complaint_id>', methods=['GET'])
@login_required
def get_complaint(complaint_id):
    try:
        complaint = Complaint.query.get_or_404(complaint_id)
        return jsonify({'complaint': complaint.to_dict()}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@complaints_bp.route('/<int:complaint_id>', methods=['PUT'])
@login_required
def update_complaint(complaint_id):
    try:
        complaint = Complaint.query.get_or_404(complaint_id)
        data = request.get_json()
        
        # Update allowed fields
        if 'customer_name' in data:
            complaint.customer_name = data['customer_name']
        if 'customer_phone' in data:
            complaint.customer_phone = data['customer_phone']
        if 'customer_email' in data:
            complaint.customer_email = data['customer_email']
        if 'issue_type' in data:
            complaint.issue_type = data['issue_type']
        if 'description' in data:
            complaint.description = data['description']
        if 'status' in data:
            complaint.status = data['status']
            if data['status'] == 'Resolved':
                complaint.resolved_at = datetime.utcnow()
        if 'priority' in data:
            complaint.priority = data['priority']
        if 'location' in data:
            complaint.location = data['location']
        if 'gps_coordinates' in data:
            complaint.gps_coordinates = data['gps_coordinates']
        if 'assigned_to_id' in data:
            complaint.assigned_to_id = data['assigned_to_id']
        if 'attachments' in data:
            complaint.set_attachments(data['attachments'])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Complaint updated successfully',
            'complaint': complaint.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@complaints_bp.route('/<int:complaint_id>/escalate', methods=['POST'])
@login_required
def escalate_complaint(complaint_id):
    try:
        complaint = Complaint.query.get_or_404(complaint_id)
        
        if complaint.escalation_level >= 2:
            return jsonify({'error': 'Complaint already at maximum escalation level'}), 400
        
        complaint.escalation_level += 1
        complaint.escalated_at = datetime.utcnow()
        
        # Auto-assign based on escalation level
        if complaint.escalation_level == 1:
            # Escalate to supervisor
            supervisor = User.query.filter_by(role='Supervisor').first()
            if supervisor:
                complaint.assigned_to_id = supervisor.id
        elif complaint.escalation_level == 2:
            # Escalate to admin
            admin = User.query.filter_by(role='Admin').first()
            if admin:
                complaint.assigned_to_id = admin.id
        
        db.session.commit()
        
        return jsonify({
            'message': f'Complaint escalated to level {complaint.escalation_level}',
            'complaint': complaint.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@complaints_bp.route('/<int:complaint_id>/feedback', methods=['POST'])
def submit_feedback(complaint_id):
    """Allow customers to submit feedback without authentication"""
    try:
        complaint = Complaint.query.get_or_404(complaint_id)
        data = request.get_json()
        
        satisfaction = data.get('satisfaction')
        feedback = data.get('feedback')
        
        if satisfaction is not None:
            if not (1 <= satisfaction <= 5):
                return jsonify({'error': 'Satisfaction rating must be between 1 and 5'}), 400
            complaint.customer_satisfaction = satisfaction
        
        if feedback:
            complaint.customer_feedback = feedback
        
        db.session.commit()
        
        return jsonify({'message': 'Feedback submitted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@complaints_bp.route('/stats', methods=['GET'])
@login_required
def get_complaint_stats():
    try:
        total_complaints = Complaint.query.count()
        open_complaints = Complaint.query.filter_by(status='Open').count()
        in_progress_complaints = Complaint.query.filter_by(status='In Progress').count()
        resolved_complaints = Complaint.query.filter_by(status='Resolved').count()
        
        # Today's resolved complaints
        today = datetime.now().date()
        today_resolved = Complaint.query.filter(
            Complaint.resolved_at >= today,
            Complaint.resolved_at < today + timedelta(days=1)
        ).count()
        
        # High priority complaints
        high_priority = Complaint.query.filter(
            Complaint.priority.in_(['High', 'Critical']),
            Complaint.status != 'Resolved'
        ).count()
        
        # Escalated complaints
        escalated = Complaint.query.filter(Complaint.escalation_level > 0).count()
        
        # Average resolution time (in hours)
        resolved_with_time = Complaint.query.filter(
            Complaint.resolved_at.isnot(None)
        ).all()
        
        avg_resolution_hours = 0
        if resolved_with_time:
            total_hours = sum([
                (c.resolved_at - c.created_at).total_seconds() / 3600
                for c in resolved_with_time
            ])
            avg_resolution_hours = total_hours / len(resolved_with_time)
        
        return jsonify({
            'total_complaints': total_complaints,
            'open_complaints': open_complaints,
            'in_progress_complaints': in_progress_complaints,
            'resolved_complaints': resolved_complaints,
            'today_resolved': today_resolved,
            'high_priority': high_priority,
            'escalated': escalated,
            'avg_resolution_hours': round(avg_resolution_hours, 2)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@complaints_bp.route('/overdue', methods=['GET'])
@login_required
def get_overdue_complaints():
    """Get complaints that are overdue for escalation"""
    try:
        # Complaints open for more than 48 hours without escalation
        cutoff_time = datetime.utcnow() - timedelta(hours=48)
        
        overdue = Complaint.query.filter(
            Complaint.created_at < cutoff_time,
            Complaint.status.in_(['Open', 'In Progress']),
            Complaint.escalation_level == 0
        ).all()
        
        return jsonify({
            'overdue_complaints': [complaint.to_dict() for complaint in overdue]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

