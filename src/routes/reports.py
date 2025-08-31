from flask import Blueprint, request, jsonify, session
from src.models.user import User, db
from src.models.complaint import Complaint
from src.models.workforce import WorkforceEntry
from src.routes.auth import login_required
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_
import json

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard_data():
    try:
        # Date range for analysis
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Complaint statistics
        total_complaints = Complaint.query.count()
        open_complaints = Complaint.query.filter_by(status='Open').count()
        in_progress_complaints = Complaint.query.filter_by(status='In Progress').count()
        resolved_complaints = Complaint.query.filter_by(status='Resolved').count()
        
        # Today's resolved complaints
        today_resolved = Complaint.query.filter(
            func.date(Complaint.resolved_at) == today
        ).count()
        
        # Workforce statistics
        total_staff = User.query.filter_by(is_active=True, role='Staff').count()
        present_today = WorkforceEntry.query.filter(
            WorkforceEntry.shift_date == today,
            WorkforceEntry.status.in_(['Present', 'Late'])
        ).count()
        
        # Calculate trends (week over week)
        prev_week_resolved = Complaint.query.filter(
            func.date(Complaint.resolved_at) >= week_ago - timedelta(days=7),
            func.date(Complaint.resolved_at) < week_ago
        ).count()
        
        this_week_resolved = Complaint.query.filter(
            func.date(Complaint.resolved_at) >= week_ago,
            func.date(Complaint.resolved_at) <= today
        ).count()
        
        resolution_trend = 0
        if prev_week_resolved > 0:
            resolution_trend = ((this_week_resolved - prev_week_resolved) / prev_week_resolved) * 100
        
        # Recent complaints
        recent_complaints = Complaint.query.order_by(
            Complaint.created_at.desc()
        ).limit(5).all()
        
        # High priority open complaints
        high_priority_open = Complaint.query.filter(
            Complaint.priority.in_(['High', 'Critical']),
            Complaint.status.in_(['Open', 'In Progress'])
        ).count()
        
        return jsonify({
            'complaints': {
                'total': total_complaints,
                'open': open_complaints,
                'in_progress': in_progress_complaints,
                'resolved': resolved_complaints,
                'today_resolved': today_resolved,
                'high_priority_open': high_priority_open,
                'resolution_trend': round(resolution_trend, 1)
            },
            'workforce': {
                'total_staff': total_staff,
                'present_today': present_today,
                'attendance_rate': round((present_today / total_staff * 100), 1) if total_staff > 0 else 0
            },
            'recent_complaints': [complaint.to_dict() for complaint in recent_complaints]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reports_bp.route('/complaints/summary', methods=['GET'])
@login_required
def get_complaints_summary():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = date.today()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if not start_date:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        # Complaints by status
        status_counts = db.session.query(
            Complaint.status,
            func.count(Complaint.id).label('count')
        ).filter(
            func.date(Complaint.created_at) >= start_date,
            func.date(Complaint.created_at) <= end_date
        ).group_by(Complaint.status).all()
        
        # Complaints by priority
        priority_counts = db.session.query(
            Complaint.priority,
            func.count(Complaint.id).label('count')
        ).filter(
            func.date(Complaint.created_at) >= start_date,
            func.date(Complaint.created_at) <= end_date
        ).group_by(Complaint.priority).all()
        
        # Complaints by issue type
        issue_type_counts = db.session.query(
            Complaint.issue_type,
            func.count(Complaint.id).label('count')
        ).filter(
            func.date(Complaint.created_at) >= start_date,
            func.date(Complaint.created_at) <= end_date
        ).group_by(Complaint.issue_type).all()
        
        # Daily complaint trends
        daily_trends = db.session.query(
            func.date(Complaint.created_at).label('date'),
            func.count(Complaint.id).label('count')
        ).filter(
            func.date(Complaint.created_at) >= start_date,
            func.date(Complaint.created_at) <= end_date
        ).group_by(func.date(Complaint.created_at)).order_by('date').all()
        
        # Average resolution time
        resolved_complaints = Complaint.query.filter(
            Complaint.resolved_at.isnot(None),
            func.date(Complaint.created_at) >= start_date,
            func.date(Complaint.created_at) <= end_date
        ).all()
        
        avg_resolution_hours = 0
        if resolved_complaints:
            total_hours = sum([
                (c.resolved_at - c.created_at).total_seconds() / 3600
                for c in resolved_complaints
            ])
            avg_resolution_hours = total_hours / len(resolved_complaints)
        
        return jsonify({
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'status_distribution': [{'status': s.status, 'count': s.count} for s in status_counts],
            'priority_distribution': [{'priority': p.priority, 'count': p.count} for p in priority_counts],
            'issue_type_distribution': [{'issue_type': i.issue_type, 'count': i.count} for i in issue_type_counts],
            'daily_trends': [{'date': d.date.isoformat(), 'count': d.count} for d in daily_trends],
            'avg_resolution_hours': round(avg_resolution_hours, 2),
            'total_complaints': sum([s.count for s in status_counts])
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reports_bp.route('/workforce/summary', methods=['GET'])
@login_required
def get_workforce_summary():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = date.today()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if not start_date:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        # Attendance by status
        attendance_counts = db.session.query(
            WorkforceEntry.status,
            func.count(WorkforceEntry.id).label('count')
        ).filter(
            WorkforceEntry.shift_date >= start_date,
            WorkforceEntry.shift_date <= end_date
        ).group_by(WorkforceEntry.status).all()
        
        # Daily attendance trends
        daily_attendance = db.session.query(
            WorkforceEntry.shift_date,
            func.count(WorkforceEntry.id).label('total_entries'),
            func.sum(func.case([(WorkforceEntry.status.in_(['Present', 'Late']), 1)], else_=0)).label('present_count')
        ).filter(
            WorkforceEntry.shift_date >= start_date,
            WorkforceEntry.shift_date <= end_date
        ).group_by(WorkforceEntry.shift_date).order_by(WorkforceEntry.shift_date).all()
        
        # Department attendance
        dept_attendance = db.session.query(
            User.department,
            func.count(WorkforceEntry.id).label('total_entries'),
            func.sum(func.case([(WorkforceEntry.status.in_(['Present', 'Late']), 1)], else_=0)).label('present_count')
        ).join(User, WorkforceEntry.staff_id == User.id).filter(
            WorkforceEntry.shift_date >= start_date,
            WorkforceEntry.shift_date <= end_date
        ).group_by(User.department).all()
        
        # Average hours worked
        completed_shifts = WorkforceEntry.query.filter(
            WorkforceEntry.shift_date >= start_date,
            WorkforceEntry.shift_date <= end_date,
            WorkforceEntry.check_in_time.isnot(None),
            WorkforceEntry.check_out_time.isnot(None)
        ).all()
        
        avg_hours = 0
        if completed_shifts:
            total_hours = sum([entry.calculate_hours_worked() for entry in completed_shifts])
            avg_hours = total_hours / len(completed_shifts)
        
        # Late arrivals
        late_count = WorkforceEntry.query.filter(
            WorkforceEntry.shift_date >= start_date,
            WorkforceEntry.shift_date <= end_date,
            WorkforceEntry.status == 'Late'
        ).count()
        
        return jsonify({
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'attendance_distribution': [{'status': a.status, 'count': a.count} for a in attendance_counts],
            'daily_attendance': [{
                'date': d.shift_date.isoformat(),
                'total_entries': d.total_entries,
                'present_count': d.present_count or 0,
                'attendance_rate': round((d.present_count or 0) / d.total_entries * 100, 1) if d.total_entries > 0 else 0
            } for d in daily_attendance],
            'department_attendance': [{
                'department': d.department,
                'total_entries': d.total_entries,
                'present_count': d.present_count or 0,
                'attendance_rate': round((d.present_count or 0) / d.total_entries * 100, 1) if d.total_entries > 0 else 0
            } for d in dept_attendance],
            'avg_hours_worked': round(avg_hours, 2),
            'late_arrivals': late_count
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reports_bp.route('/performance', methods=['GET'])
@login_required
def get_performance_report():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = date.today()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if not start_date:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        # Staff performance (complaints handled)
        staff_performance = db.session.query(
            User.name,
            User.staff_number,
            User.department,
            func.count(Complaint.id).label('complaints_handled'),
            func.sum(func.case([(Complaint.status == 'Resolved', 1)], else_=0)).label('complaints_resolved')
        ).join(
            Complaint, Complaint.assigned_to_id == User.id
        ).filter(
            func.date(Complaint.created_at) >= start_date,
            func.date(Complaint.created_at) <= end_date
        ).group_by(User.id).order_by('complaints_handled desc').all()
        
        # Customer satisfaction
        satisfaction_data = db.session.query(
            func.avg(Complaint.customer_satisfaction).label('avg_satisfaction'),
            func.count(Complaint.customer_satisfaction).label('feedback_count')
        ).filter(
            Complaint.customer_satisfaction.isnot(None),
            func.date(Complaint.created_at) >= start_date,
            func.date(Complaint.created_at) <= end_date
        ).first()
        
        # Escalation statistics
        escalation_stats = db.session.query(
            Complaint.escalation_level,
            func.count(Complaint.id).label('count')
        ).filter(
            func.date(Complaint.created_at) >= start_date,
            func.date(Complaint.created_at) <= end_date
        ).group_by(Complaint.escalation_level).all()
        
        return jsonify({
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'staff_performance': [{
                'name': s.name,
                'staff_number': s.staff_number,
                'department': s.department,
                'complaints_handled': s.complaints_handled,
                'complaints_resolved': s.complaints_resolved or 0,
                'resolution_rate': round((s.complaints_resolved or 0) / s.complaints_handled * 100, 1) if s.complaints_handled > 0 else 0
            } for s in staff_performance],
            'customer_satisfaction': {
                'average_rating': round(satisfaction_data.avg_satisfaction, 2) if satisfaction_data.avg_satisfaction else 0,
                'feedback_count': satisfaction_data.feedback_count or 0
            },
            'escalation_stats': [{'level': e.escalation_level, 'count': e.count} for e in escalation_stats]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reports_bp.route('/export/complaints', methods=['GET'])
@login_required
def export_complaints():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        format_type = request.args.get('format', 'json')  # json, csv
        
        query = Complaint.query
        
        if start_date:
            start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(func.date(Complaint.created_at) >= start_obj)
        
        if end_date:
            end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(func.date(Complaint.created_at) <= end_obj)
        
        complaints = query.order_by(Complaint.created_at.desc()).all()
        
        if format_type == 'csv':
            # Return CSV format data
            csv_data = []
            headers = ['ID', 'Customer Name', 'Phone', 'Issue Type', 'Status', 'Priority', 'Created At', 'Resolved At']
            csv_data.append(headers)
            
            for complaint in complaints:
                row = [
                    complaint.complaint_id,
                    complaint.customer_name,
                    complaint.customer_phone,
                    complaint.issue_type,
                    complaint.status,
                    complaint.priority,
                    complaint.created_at.isoformat() if complaint.created_at else '',
                    complaint.resolved_at.isoformat() if complaint.resolved_at else ''
                ]
                csv_data.append(row)
            
            return jsonify({
                'format': 'csv',
                'data': csv_data,
                'filename': f'complaints_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }), 200
        
        else:
            # Return JSON format
            return jsonify({
                'format': 'json',
                'data': [complaint.to_dict() for complaint in complaints],
                'count': len(complaints),
                'exported_at': datetime.now().isoformat()
            }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reports_bp.route('/export/workforce', methods=['GET'])
@login_required
def export_workforce():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        format_type = request.args.get('format', 'json')
        
        query = WorkforceEntry.query
        
        if start_date:
            start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(WorkforceEntry.shift_date >= start_obj)
        
        if end_date:
            end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(WorkforceEntry.shift_date <= end_obj)
        
        entries = query.order_by(WorkforceEntry.shift_date.desc()).all()
        
        if format_type == 'csv':
            csv_data = []
            headers = ['Staff Number', 'Name', 'Date', 'Check In', 'Check Out', 'Status', 'Hours Worked']
            csv_data.append(headers)
            
            for entry in entries:
                row = [
                    entry.staff_member.staff_number if entry.staff_member else '',
                    entry.staff_member.name if entry.staff_member else '',
                    entry.shift_date.isoformat() if entry.shift_date else '',
                    entry.check_in_time.strftime('%H:%M') if entry.check_in_time else '',
                    entry.check_out_time.strftime('%H:%M') if entry.check_out_time else '',
                    entry.status,
                    str(round(entry.calculate_hours_worked(), 2))
                ]
                csv_data.append(row)
            
            return jsonify({
                'format': 'csv',
                'data': csv_data,
                'filename': f'workforce_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }), 200
        
        else:
            return jsonify({
                'format': 'json',
                'data': [entry.to_dict() for entry in entries],
                'count': len(entries),
                'exported_at': datetime.now().isoformat()
            }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

