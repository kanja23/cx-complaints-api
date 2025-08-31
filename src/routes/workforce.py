from flask import Blueprint, request, jsonify, session
from src.models.user import User, db
from src.models.workforce import WorkforceEntry
from src.routes.auth import login_required
from datetime import datetime, date, time, timedelta
from sqlalchemy import func

workforce_bp = Blueprint('workforce', __name__)

@workforce_bp.route('/entries', methods=['GET'])
@login_required
def get_workforce_entries():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        shift_date = request.args.get('date')
        status = request.args.get('status')
        staff_id = request.args.get('staff_id')
        
        query = WorkforceEntry.query
        
        # Apply filters
        if shift_date:
            try:
                date_obj = datetime.strptime(shift_date, '%Y-%m-%d').date()
                query = query.filter(WorkforceEntry.shift_date == date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            # Default to today
            query = query.filter(WorkforceEntry.shift_date == date.today())
        
        if status and status != 'All':
            query = query.filter(WorkforceEntry.status == status)
        
        if staff_id:
            query = query.filter(WorkforceEntry.staff_id == staff_id)
        
        # Order by staff name
        query = query.join(User).order_by(User.name)
        
        # Paginate
        entries = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'entries': [entry.to_dict() for entry in entries.items],
            'total': entries.total,
            'pages': entries.pages,
            'current_page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@workforce_bp.route('/entries', methods=['POST'])
@login_required
def create_workforce_entry():
    try:
        data = request.get_json()
        
        required_fields = ['staff_id', 'shift_date']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse shift date
        try:
            shift_date = datetime.strptime(data['shift_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Check if entry already exists for this staff and date
        existing = WorkforceEntry.query.filter_by(
            staff_id=data['staff_id'],
            shift_date=shift_date
        ).first()
        
        if existing:
            return jsonify({'error': 'Workforce entry already exists for this staff and date'}), 400
        
        entry = WorkforceEntry(
            staff_id=data['staff_id'],
            shift_date=shift_date,
            status=data.get('status', 'Scheduled'),
            work_location=data.get('work_location'),
            work_area_gps=data.get('work_area_gps'),
            notes=data.get('notes')
        )
        
        # Set assigned tasks
        if data.get('assigned_tasks'):
            entry.set_assigned_tasks(data['assigned_tasks'])
        
        # Set check-in time if provided
        if data.get('check_in_time'):
            try:
                entry.check_in_time = datetime.strptime(data['check_in_time'], '%H:%M').time()
                entry.check_in_location = data.get('check_in_location')
                entry.check_in_gps = data.get('check_in_gps')
                if entry.status == 'Scheduled':
                    entry.status = 'Present'
            except ValueError:
                return jsonify({'error': 'Invalid check-in time format. Use HH:MM'}), 400
        
        db.session.add(entry)
        db.session.commit()
        
        return jsonify({
            'message': 'Workforce entry created successfully',
            'entry': entry.to_dict()
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@workforce_bp.route('/entries/<int:entry_id>', methods=['PUT'])
@login_required
def update_workforce_entry(entry_id):
    try:
        entry = WorkforceEntry.query.get_or_404(entry_id)
        data = request.get_json()
        
        # Update allowed fields
        if 'status' in data:
            entry.status = data['status']
        
        if 'check_in_time' in data and data['check_in_time']:
            try:
                entry.check_in_time = datetime.strptime(data['check_in_time'], '%H:%M').time()
                entry.check_in_location = data.get('check_in_location')
                entry.check_in_gps = data.get('check_in_gps')
                if entry.status == 'Scheduled':
                    entry.status = 'Present'
            except ValueError:
                return jsonify({'error': 'Invalid check-in time format. Use HH:MM'}), 400
        
        if 'check_out_time' in data and data['check_out_time']:
            try:
                entry.check_out_time = datetime.strptime(data['check_out_time'], '%H:%M').time()
                entry.check_out_location = data.get('check_out_location')
                entry.check_out_gps = data.get('check_out_gps')
            except ValueError:
                return jsonify({'error': 'Invalid check-out time format. Use HH:MM'}), 400
        
        if 'assigned_tasks' in data:
            entry.set_assigned_tasks(data['assigned_tasks'])
        
        if 'completed_tasks' in data:
            entry.set_completed_tasks(data['completed_tasks'])
        
        if 'work_location' in data:
            entry.work_location = data['work_location']
        
        if 'work_area_gps' in data:
            entry.work_area_gps = data['work_area_gps']
        
        if 'notes' in data:
            entry.notes = data['notes']
        
        if 'supervisor_notes' in data:
            entry.supervisor_notes = data['supervisor_notes']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Workforce entry updated successfully',
            'entry': entry.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@workforce_bp.route('/check-in', methods=['POST'])
@login_required
def check_in():
    """Allow staff to check in for their shift"""
    try:
        data = request.get_json()
        staff_id = session.get('user_id')  # Use current logged-in user
        today = date.today()
        
        # Find or create workforce entry for today
        entry = WorkforceEntry.query.filter_by(
            staff_id=staff_id,
            shift_date=today
        ).first()
        
        if not entry:
            # Create new entry
            entry = WorkforceEntry(
                staff_id=staff_id,
                shift_date=today,
                status='Present'
            )
            db.session.add(entry)
        
        # Set check-in details
        entry.check_in_time = datetime.now().time()
        entry.check_in_location = data.get('location')
        entry.check_in_gps = data.get('gps_coordinates')
        entry.status = 'Present'
        
        # Check if late (assuming 8:00 AM is standard start time)
        standard_start = time(8, 0)
        if entry.check_in_time > standard_start:
            entry.status = 'Late'
        
        db.session.commit()
        
        return jsonify({
            'message': 'Check-in successful',
            'entry': entry.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@workforce_bp.route('/check-out', methods=['POST'])
@login_required
def check_out():
    """Allow staff to check out from their shift"""
    try:
        data = request.get_json()
        staff_id = session.get('user_id')
        today = date.today()
        
        entry = WorkforceEntry.query.filter_by(
            staff_id=staff_id,
            shift_date=today
        ).first()
        
        if not entry:
            return jsonify({'error': 'No check-in record found for today'}), 404
        
        if entry.check_out_time:
            return jsonify({'error': 'Already checked out for today'}), 400
        
        # Set check-out details
        entry.check_out_time = datetime.now().time()
        entry.check_out_location = data.get('location')
        entry.check_out_gps = data.get('gps_coordinates')
        
        db.session.commit()
        
        return jsonify({
            'message': 'Check-out successful',
            'entry': entry.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@workforce_bp.route('/stats', methods=['GET'])
@login_required
def get_workforce_stats():
    try:
        target_date = request.args.get('date')
        if target_date:
            try:
                date_obj = datetime.strptime(target_date, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            date_obj = date.today()
        
        # Total staff count
        total_staff = User.query.filter_by(is_active=True, role='Staff').count()
        
        # Today's attendance
        present_count = WorkforceEntry.query.filter(
            WorkforceEntry.shift_date == date_obj,
            WorkforceEntry.status.in_(['Present', 'Late'])
        ).count()
        
        absent_count = WorkforceEntry.query.filter(
            WorkforceEntry.shift_date == date_obj,
            WorkforceEntry.status == 'Absent'
        ).count()
        
        on_leave_count = WorkforceEntry.query.filter(
            WorkforceEntry.shift_date == date_obj,
            WorkforceEntry.status == 'On Leave'
        ).count()
        
        # Calculate attendance percentage
        attendance_percentage = (present_count / total_staff * 100) if total_staff > 0 else 0
        
        # Late arrivals
        late_count = WorkforceEntry.query.filter(
            WorkforceEntry.shift_date == date_obj,
            WorkforceEntry.status == 'Late'
        ).count()
        
        # Average hours worked (for completed shifts)
        completed_entries = WorkforceEntry.query.filter(
            WorkforceEntry.shift_date == date_obj,
            WorkforceEntry.check_in_time.isnot(None),
            WorkforceEntry.check_out_time.isnot(None)
        ).all()
        
        avg_hours = 0
        if completed_entries:
            total_hours = sum([entry.calculate_hours_worked() for entry in completed_entries])
            avg_hours = total_hours / len(completed_entries)
        
        return jsonify({
            'date': date_obj.isoformat(),
            'total_staff': total_staff,
            'present_count': present_count,
            'absent_count': absent_count,
            'on_leave_count': on_leave_count,
            'late_count': late_count,
            'attendance_percentage': round(attendance_percentage, 1),
            'avg_hours_worked': round(avg_hours, 2)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@workforce_bp.route('/departments', methods=['GET'])
@login_required
def get_department_stats():
    try:
        target_date = request.args.get('date')
        if target_date:
            try:
                date_obj = datetime.strptime(target_date, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            date_obj = date.today()
        
        # Get department statistics
        dept_stats = db.session.query(
            User.department,
            func.count(User.id).label('total_staff'),
            func.count(WorkforceEntry.id).label('present_staff')
        ).outerjoin(
            WorkforceEntry,
            (WorkforceEntry.staff_id == User.id) & 
            (WorkforceEntry.shift_date == date_obj) &
            (WorkforceEntry.status.in_(['Present', 'Late']))
        ).filter(
            User.is_active == True,
            User.role == 'Staff'
        ).group_by(User.department).all()
        
        departments = []
        for dept in dept_stats:
            departments.append({
                'department': dept.department,
                'total_staff': dept.total_staff,
                'present_staff': dept.present_staff or 0,
                'attendance_rate': round((dept.present_staff or 0) / dept.total_staff * 100, 1) if dept.total_staff > 0 else 0
            })
        
        return jsonify({
            'date': date_obj.isoformat(),
            'departments': departments
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@workforce_bp.route('/my-schedule', methods=['GET'])
@login_required
def get_my_schedule():
    """Get current user's workforce schedule"""
    try:
        staff_id = session.get('user_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = WorkforceEntry.query.filter_by(staff_id=staff_id)
        
        if start_date:
            try:
                start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(WorkforceEntry.shift_date >= start_obj)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
        
        if end_date:
            try:
                end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(WorkforceEntry.shift_date <= end_obj)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
        
        if not start_date and not end_date:
            # Default to current week
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            query = query.filter(
                WorkforceEntry.shift_date >= start_of_week,
                WorkforceEntry.shift_date <= end_of_week
            )
        
        entries = query.order_by(WorkforceEntry.shift_date).all()
        
        return jsonify({
            'schedule': [entry.to_dict() for entry in entries]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

