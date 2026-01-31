from flask import Blueprint, request, jsonify
from flask_security import login_required, current_user
from flask_security.utils import verify_password
from backend.services import ProduceScanService
from backend.services.auth_service import AuthService

# ==================== SCAN BLUEPRINT ====================

scan_bp = Blueprint('scan', __name__, url_prefix='/api/scan')
scan_service = ProduceScanService()



@scan_bp.route('/start-session', methods=['POST'])
@login_required  # Require authentication
def start_session():
    """
    Start a new produce scanning session (Protected - requires authentication)

    Returns:
        {
            "success": bool,
            "session_id": str
        }
    """
    try:
        session_id = scan_service.start_scan_session(user_id=current_user.id)
        return jsonify({
            'success': True,
            'session_id': session_id,
            'user_id': current_user.id
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/single', methods=['POST'])
@login_required  # Require authentication
def scan_single():
    """
    Scan a single produce item from image (Protected - requires authentication)

    Expected JSON:
    {
        "image_data": str (base64 image),
        "session_id": str
    }

    Returns:
        {
            "success": bool,
            "data": { produce analysis },
            "error": str (if failed)
        }
    """
    data = request.get_json()

    # Validate required fields
    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body is required'
        }), 400

    image_data = data.get('image_data')
    session_id = data.get('session_id')

    if not image_data or not session_id:
        return jsonify({
            'success': False,
            'error': 'image_data and session_id are required'
        }), 400

    try:
        result = scan_service.scan_single_produce(
            image_data,
            session_id,
            user_id=current_user.id
        )
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/batch', methods=['POST'])
@login_required  # Require authentication
def scan_batch():
    """
    Scan multiple produce items from images (Protected - requires authentication)

    Expected JSON:
    {
        "images": [base64_string, base64_string, ...],
        "session_id": str
    }

    Returns:
        {
            "success": bool,
            "session_id": str,
            "scans": [{ produce analysis }, ...],
            "summary": {
                "total_scanned": int,
                "expiring_soon_count": int,
                "expired_count": int,
                "healthy_count": int
            },
            "error": str (if failed)
        }
    """
    data = request.get_json()

    # Validate required fields
    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body is required'
        }), 400

    images = data.get('images', [])
    session_id = data.get('session_id')

    if not isinstance(images, list) or not session_id:
        return jsonify({
            'success': False,
            'error': 'images (array) and session_id are required'
        }), 400

    if len(images) == 0:
        return jsonify({
            'success': False,
            'error': 'images cannot be empty'
        }), 400

    try:
        result = scan_service.scan_batch_produce(
            images,
            session_id,
            user_id=current_user.id
        )
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/session/<session_id>', methods=['GET'])
@login_required  # Require authentication
def get_session_results(session_id):
    """
    Get all results from a specific scanning session (Protected - requires authentication)

    Returns:
        {
            "success": bool,
            "session": { session data },
            "scans": [{ produce analysis }, ...],
            "error": str (if failed)
        }
    """
    try:
        result = scan_service.get_session_results(session_id, user_id=current_user.id)
        status_code = 200 if result['success'] else 404
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/recent', methods=['GET'])
@login_required  # Require authentication
def get_recent():
    """
    Get recent produce scans for current user

    Query parameters:
    - limit: int (default: 50, max: 100)

    Returns:
        {
            "success": bool,
            "count": int,
            "scans": [{ produce analysis }, ...],
            "error": str (if failed)
        }
    """
    try:
        limit = request.args.get('limit', default=50, type=int)
        limit = min(limit, 100)  # Cap at 100

        result = scan_service.get_recent_scans(limit=limit, user_id=current_user.id)
        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/storage-tips', methods=['POST'])
def storage_tips():
    """
    Get storage recommendations for a produce type (Public endpoint)

    Expected JSON:
    {
        "produce_name": str
    }

    Returns:
        {
            "success": bool,
            "produce": str,
            "recommendations": str,
            "error": str (if failed)
        }
    """
    data = request.get_json()

    if not data or not data.get('produce_name'):
        return jsonify({
            'success': False,
            'error': 'produce_name is required'
        }), 400

    try:
        produce_name = data.get('produce_name')
        result = scan_service.get_storage_tips(produce_name)
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Produce Scan API'
    }), 200


# ==================== AUTH BLUEPRINT ====================

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user

    Expected JSON:
    {
        "email": "user@example.com",
        "password": "password123",
        "username": "username"
    }
    """
    data = request.get_json()

    if not all(['email' in data, 'password' in data, 'username' in data]):
        return jsonify({'error': 'Missing required fields: email, password, username'}), 400

    user, message = AuthService.create_user(
        email=data.get('email'),
        password=data.get('password'),
        username=data.get('username')
    )

    if not user:
        return jsonify({'error': message}), 400

    return jsonify({
        'message': message,
        'user_id': user.id,
        'email': user.email,
        'username': user.username
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login user and establish session

    Expected JSON:
    {
        "email": "user@example.com",
        "password": "password123"
    }
    """
    data = request.get_json()

    if not all(['email' in data, 'password' in data]):
        return jsonify({'error': 'Missing required fields: email, password'}), 400

    user = AuthService.get_user_by_email(data.get('email'))

    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401

    # Use Flask-Security's verify_password utility
    if not verify_password(data.get('password'), user.password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user.active:
        return jsonify({'error': 'User account is inactive'}), 403

    from flask_security import login_user
    login_user(user)

    return jsonify({
        'message': 'Logged in successfully',
        'user_id': user.id,
        'email': user.email,
        'username': user.username
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logout current user"""
    from flask_security import logout_user
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current authenticated user info"""
    return jsonify({
        'user_id': current_user.id,
        'email': current_user.email,
        'username': current_user.username,
        'active': current_user.active,
        'roles': [role.name for role in current_user.roles],
        'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
        'last_login_at': current_user.last_login_at.isoformat() if current_user.last_login_at else None
    }), 200
    
business_dashboard_bp = Blueprint(
    'business_dashboard',
    __name__,
    url_prefix='/api'
)

shopper_dashboard_bp = Blueprint(
    'shopper_dashboard',
    __name__,
    url_prefix='/api'
)

    
@business_dashboard_bp.route('/business/dashboard')
@login_required
@roles_required('business')
def business_dashboard():
    pass

@shopper_dashboard_bp.route('/shop/dashboard')
@login_required
@roles_required('shopper')
def shopper_dashboard():
    pass