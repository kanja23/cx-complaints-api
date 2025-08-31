import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
from src.models.user import db
from src.routes.auth import auth_bp
from src.routes.complaints import complaints_bp
from src.routes.workforce import workforce_bp
from src.routes.reports import reports_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'kplc-field-workforce-management-2025'

# Enable CORS for all routes with credentials support
CORS(app, supports_credentials=True, origins=[
    'http://localhost:5174',
    'http://localhost:3000',
    'https://workforcemanagements.netlify.app'
])

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(complaints_bp, url_prefix='/api/complaints')
app.register_blueprint(workforce_bp, url_prefix='/api/workforce')
app.register_blueprint(reports_bp, url_prefix='/api/reports')

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()
    
    # Seed initial data
    from src.models.user import User
    from src.models.complaint import Complaint
    from src.models.workforce import WorkforceEntry
    
    # Create initial users if they don't exist
    if User.query.count() == 0:
        users = [
            User(staff_number='85891', name='Martin Karanja', role='Admin', 
                 email='MKaranja2@kplc.co.ke', department='Administration'),
            User(staff_number='85915', name='Patrick Moenga', role='Staff', 
                 email='pmoenga@kplc.co.ke', department='Operations'),
            User(staff_number='53050', name='Martin Mackenzie', role='Staff', 
                 email='mmackenzie@kplc.co.ke', department='Technical'),
            User(staff_number='86002', name='Samwel Nyamori', role='Staff', 
                 email='snyamori@kplc.co.ke', department='Customer Service'),
            User(staff_number='80909', name='Ronald Omweri', role='Staff', 
                 email='romweri@kplc.co.ke', department='Maintenance'),
            User(staff_number='16957', name='Godfrey Kopilo', role='Staff', 
                 email='gkopilo@kplc.co.ke', department='Operations')
        ]
        
        for user in users:
            user.set_password(user.staff_number[-4:])  # Use last 4 digits as password
            db.session.add(user)
        
        db.session.commit()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

@app.route('/api/health')
def health_check():
    return {'status': 'healthy', 'message': 'KPLC Field & Workforce Management System API'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

