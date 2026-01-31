from flask import Flask, jsonify, render_template, redirect
from flask_cors import CORS
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

from backend.extensions import business_user as db, security, init_user_datastore
from backend.models import User, Role
from backend.routes import scan_bp, auth_bp


def create_app(config_name: str = 'development'):
    """
    Application factory for creating Flask app instance

    Args:
        config_name: Configuration environment (development, testing, production)

    Returns:
        Flask application instance
    """

    app = Flask(__name__)

    # ==================== LOGGING CONFIGURATION ====================
    if config_name == 'development':
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        app.logger.setLevel(logging.DEBUG)
        # Get loggers for routes
        logging.getLogger('backend.routes').setLevel(logging.DEBUG)

    # ==================== CONFIGURATION ====================

    # Database configuration
    if config_name == 'testing':
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['TESTING'] = False
    elif config_name == 'production':
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
            'DATABASE_URL',
            'sqlite:///produce_scan.db'
        )
    else:  # development
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///produce_scan.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JSON_SORT_KEYS'] = False

    # ==================== JSON & REQUEST SIZE LIMITS ====================
    # Allow larger JSON payloads for image data (base64 encoded)
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max
    app.config['JSON_MAX_SIZE'] = 50 * 1024 * 1024  # 50MB max for JSON

    # Flask-Security configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SECURITY_PASSWORD_SALT'] = os.getenv('SECURITY_PASSWORD_SALT', 'dev-salt-change-in-production')
    app.config['WTF_CSRF_ENABLED'] = False  # For API usage
    app.config['SECURITY_TOKEN_AUTHENTICATION_HEADER'] = 'Authorization'
    app.config['SECURITY_TOKEN_AUTHENTICATION_SCHEME'] = 'Bearer'
    app.config['SECURITY_SESSION_COOKIE_HTTPONLY'] = True
    app.config['SECURITY_SESSION_COOKIE_SAMESITE'] = 'Lax'

    # ==================== EXTENSIONS INITIALIZATION ====================

    # Initialize SQLAlchemy
    db.init_app(app)

    # Setup Flask-Security with user datastore
    init_user_datastore(app)

    # ==================== BLUEPRINTS ====================

    # Register blueprints
    app.register_blueprint(auth_bp)  # Auth endpoints
    app.register_blueprint(scan_bp)  # Scan endpoints

    # ==================== DATABASE INITIALIZATION ====================

    with app.app_context():
        # Create all tables
        db.create_all()

        # Create default roles if they don't exist
        from backend.extensions import user_datastore
        if user_datastore and not user_datastore.find_role('admin'):
            user_datastore.create_role(
                name='admin',
                description='Administrator with full access'
            )

        if user_datastore and not user_datastore.find_role('user'):
            user_datastore.create_role(
                name='user',
                description='Standard user'
            )

        db.session.commit()

    # ==================== ROUTES ====================

    # Root route - Serve index.html
    @app.route('/', methods=['GET'])
    def root():
        return render_template('index.html')

    # Dashboard route - Serve dashboard.html (requires authentication)
    @app.route('/dashboard', methods=['GET'])
    def dashboard():
        from flask_security import current_user
        if not current_user.is_authenticated:
            return redirect('/')
        return render_template('dashboard.html')

    # API info endpoint
    @app.route('/api', methods=['GET'])
    def api_info():
        return {
            'message': 'Food Scanning API with Authentication',
            'version': '1.0.0',
            'auth_endpoints': {
                'register': 'POST /api/auth/register',
                'login': 'POST /api/auth/login',
                'logout': 'POST /api/auth/logout',
                'me': 'GET /api/auth/me'
            },
            'scan_endpoints': {
                'start_session': 'POST /api/scan/start-session',
                'scan_single': 'POST /api/scan/single',
                'scan_batch': 'POST /api/scan/batch',
                'get_session': 'GET /api/scan/session/<session_id>',
                'get_recent': 'GET /api/scan/recent',
                'storage_tips': 'POST /api/scan/storage-tips',
                'health': 'GET /api/scan/health'
            }
        }, 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Endpoint not found'
        }), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({
            'success': False,
            'error': 'Request payload too large. Max size is 50MB.'
        }), 413

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'error': 'Bad request. Check your JSON format.'
        }), 400

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

    return app


if __name__ == '__main__':
    app = create_app('development')
    app.run(debug=False, host='0.0.0.0', port=5000)