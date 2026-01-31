"""
Flask Routes: HTTP API endpoints for the produce scanning application

Two Blueprints:
1. scan_bp: Scanning operations (protected & public endpoints)
2. auth_bp: Authentication (register, login, logout, me)

Design Principles:
- Routes are thin: validation + service call + response formatting
- Business logic lives in services, not routes
- Database access is ONLY through services
- Logging at route level for debugging request flow
- Error responses include meaningful messages
"""

from flask import Blueprint, request, jsonify
from flask_security import login_required, current_user
from flask_security.utils import verify_password
from backend.services import ProduceScanService
from backend.services.auth_service import AuthService
import logging

logger = logging.getLogger(__name__)

# ==================== SCAN BLUEPRINT ====================
# Protected scanning endpoints + public storage tips endpoint

scan_bp = Blueprint('scan', __name__, url_prefix='/api/scan')
scan_service = ProduceScanService()


@scan_bp.route('/start-session', methods=['POST'])
@login_required  # Decorator: requires user to be authenticated
def start_session():
    """
    Create a new scanning session for the authenticated user.

    Protected Endpoint: Requires authentication
    Purpose: Initialize a session to group multiple scans together

    Request:
        POST /api/scan/start-session
        (No body required, user_id comes from session)

    Response (201 Created):
        {
            "success": true,
            "session_id": "a1b2c3d4",
            "user_id": 5
        }

    Error (500):
        {
            "success": false,
            "error": "Database error..."
        }

    Flow:
    1. User is authenticated (checked by @login_required)
    2. Service creates session with user_id
    3. Returns session ID for subsequent scans

    Example:
        fetch('/api/scan/start-session', {method: 'POST'})
        .then(r => r.json())
        .then(data => console.log(data.session_id))
    """
    try:
        logger.debug(f"Starting session for user: {current_user.id}")

        # Call service to create session
        # current_user is available from Flask-Security
        session_id = scan_service.start_scan_session(user_id=current_user.id)

        logger.debug(f"Session created: {session_id}")

        return jsonify({
            'success': True,
            'session_id': session_id,
            'user_id': current_user.id
        }), 201  # 201 Created

    except Exception as e:
        logger.error(f"Error starting session: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/single', methods=['POST'])
@login_required
def scan_single():
    """
    Analyze a single produce item from an image.

    Protected Endpoint: Requires authentication
    Purpose: Send one image, get produce analysis result

    Request:
        POST /api/scan/single
        Content-Type: application/json
        {
            "image_data": "data:image/jpeg;base64,/9j/4AAQSk...",
            "session_id": "a1b2c3d4"
        }

    Response (200 OK):
        {
            "success": true,
            "data": {
                "id": 42,
                "scan_id": "a1b2c3d4e5",
                "produce_name": "Apple",
                "shelf_life_days": 7,
                "is_expiring_soon": false,
                "is_expired": false,
                "notes": "Fresh red apple...",
                "scanned_at": "2025-01-31T12:34:56"
            }
        }

    Response (400 Bad Request):
        {
            "success": false,
            "error": "image_data and session_id are required"
        }

    Response (500 Server Error):
        {
            "success": false,
            "error": "Error analyzing produce image: ..."
        }

    Flow:
    1. Validate request has required fields
    2. Call service to analyze image (calls AI)
    3. Service saves result to database
    4. Return analysis + database ID

    Notes:
    - image_data is base64 encoded (can be large - 50MB limit on Flask)
    - session_id groups scan in a session for user's history
    """
    data = request.get_json()
    logger.debug(f"scan_single request body keys: {list(data.keys()) if data else 'None'}")

    # Validate request body exists
    if not data:
        logger.warning("scan_single: Request body is empty")
        return jsonify({
            'success': False,
            'error': 'Request body is required'
        }), 400

    # Extract fields from request
    image_data = data.get('image_data')
    session_id = data.get('session_id')

    logger.debug(f"scan_single: image_data present={bool(image_data)}, session_id={session_id}")
    logger.debug(f"scan_single: image_data length={len(image_data) if image_data else 0} chars")

    # Validate required fields are present
    if not image_data or not session_id:
        logger.warning(f"scan_single: Missing fields - image_data: {bool(image_data)}, session_id: {bool(session_id)}")
        return jsonify({
            'success': False,
            'error': 'image_data and session_id are required'
        }), 400

    try:
        logger.debug(f"Calling scan_single_produce for session: {session_id}")

        # Call service to analyze produce
        # Service handles: AI analysis + database save
        result = scan_service.scan_single_produce(
            image_data,
            session_id,
            user_id=current_user.id
        )

        # Return appropriate status code based on result
        status_code = 200 if result['success'] else 400
        logger.debug(f"scan_single result: success={result['success']}")

        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"scan_single exception: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/batch', methods=['POST'])
@login_required
def scan_batch():
    """
    Analyze multiple produce items in one batch request.

    Protected Endpoint: Requires authentication
    Purpose: Efficient scanning of multiple items

    Request:
        POST /api/scan/batch
        {
            "images": [
                "data:image/jpeg;base64,/9j/4AAQ...",
                "data:image/jpeg;base64,/9j/4AAQ...",
                ...
            ],
            "session_id": "a1b2c3d4"
        }

    Response (200 OK):
        {
            "success": true,
            "session_id": "a1b2c3d4",
            "scans": [
                {"produce_name": "Apple", "shelf_life_days": 7, ...},
                {"produce_name": "Banana", "shelf_life_days": 2, ...},
                ...
            ],
            "summary": {
                "total_scanned": 2,
                "expiring_soon_count": 1,
                "expired_count": 0,
                "healthy_count": 1
            }
        }

    Response (400 Bad Request):
        {
            "success": false,
            "error": "images cannot be empty"
        }

    Advantages over multiple /single calls:
    - Single session update instead of N updates
    - Aggregated statistics in one response
    - Better for analytics (batch vs individual)
    - Can batch across multiple scans efficiently
    """
    data = request.get_json()
    logger.debug(f"scan_batch request body keys: {list(data.keys()) if data else 'None'}")

    # Validate request body
    if not data:
        logger.warning("scan_batch: Request body is empty")
        return jsonify({
            'success': False,
            'error': 'Request body is required'
        }), 400

    # Extract fields
    images = data.get('images', [])
    session_id = data.get('session_id')

    logger.debug(f"scan_batch: images count={len(images)}, session_id={session_id}")

    # Validate format and required fields
    if not isinstance(images, list) or not session_id:
        logger.warning(
            f"scan_batch: Invalid format - images type={type(images)}, session_id present={bool(session_id)}")
        return jsonify({
            'success': False,
            'error': 'images (array) and session_id are required'
        }), 400

    # Validate images list is not empty
    if len(images) == 0:
        logger.warning("scan_batch: Empty images list")
        return jsonify({
            'success': False,
            'error': 'images cannot be empty'
        }), 400

    try:
        logger.debug(f"Calling scan_batch_produce for session: {session_id}")

        # Call service to analyze batch
        # Service handles: AI analysis for each + database saves + session update
        result = scan_service.scan_batch_produce(
            images,
            session_id,
            user_id=current_user.id
        )

        status_code = 200 if result['success'] else 400
        logger.debug(f"scan_batch result: success={result['success']}, count={len(result.get('scans', []))}")

        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"scan_batch exception: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/session/<session_id>', methods=['GET'])
@login_required
def get_session_results(session_id):
    """
    Retrieve all scans from a specific session.

    Protected Endpoint: Requires authentication
    Authorization: User can only view their own sessions

    Request:
        GET /api/scan/session/a1b2c3d4

    Response (200 OK):
        {
            "success": true,
            "session": {
                "session_id": "a1b2c3d4",
                "user_id": 5,
                "total_scanned": 3,
                "expiring_soon_count": 1,
                "expired_count": 0,
                "created_at": "2025-01-31T12:00:00"
            },
            "scans": [
                {"produce_name": "Apple", ...},
                {"produce_name": "Banana", ...},
                {"produce_name": "Spinach", ...}
            ]
        }

    Response (404 Not Found):
        {
            "success": false,
            "error": "Session abc123 not found"
        }

    Response (403 Forbidden):
        {
            "success": false,
            "error": "Unauthorized access to this session"
        }

    Authorization:
    - Service checks if session.user_id matches current_user.id
    - Prevents users from viewing other users' scans
    """
    logger.debug(f"Getting session results for: {session_id}")
    try:
        # Call service with user_id for authorization check
        result = scan_service.get_session_results(session_id, user_id=current_user.id)

        # Determine status code based on result
        status_code = 200 if result['success'] else 404
        logger.debug(f"get_session_results: success={result['success']}")

        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"get_session_results exception: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/recent', methods=['GET'])
@login_required
def get_recent():
    """
    Get recent scans for the authenticated user.

    Protected Endpoint: Requires authentication

    Request:
        GET /api/scan/recent?limit=10

    Query Parameters:
        limit: (optional) Max scans to return, default 50, max 100

    Response (200 OK):
        {
            "success": true,
            "count": 3,
            "scans": [
                {"produce_name": "Apple", "shelf_life_days": 7, ...},
                {"produce_name": "Banana", "shelf_life_days": 2, ...},
                {"produce_name": "Spinach", "shelf_life_days": 1, ...}
            ]
        }

    Purpose:
    - Dashboard history: show user's recent scan activity
    - Provides quick access to recent results
    - Ordered newest first (most recent scans first)
    """
    try:
        # Parse and validate limit parameter
        limit = request.args.get('limit', default=50, type=int)
        limit = min(limit, 100)  # Cap at 100 to prevent large queries
        logger.debug(f"Getting recent scans for user {current_user.id}, limit={limit}")

        # Get user's recent scans
        result = scan_service.get_recent_scans(limit=limit, user_id=current_user.id)
        logger.debug(f"get_recent: found {result.get('count', 0)} scans")

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"get_recent exception: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/storage-tips', methods=['POST'])
def storage_tips():
    """
    Get AI-generated storage recommendations for a produce type.

    PUBLIC Endpoint: No authentication required
    Purpose: Anyone can request storage tips (doesn't require login)

    Request:
        POST /api/scan/storage-tips
        {
            "produce_name": "Apple"
        }

    Response (200 OK):
        {
            "success": true,
            "produce": "Apple",
            "recommendations": "Store apples in the refrigerator in a plastic
                bag to maintain humidity. Separate from ethylene-producing
                fruits like bananas and avocados..."
        }

    Response (400 Bad Request):
        {
            "success": false,
            "error": "produce_name is required"
        }

    Why Public?
    - Educational content (storage tips help reduce waste)
    - Accessible to all users and anonymous visitors
    - Encourages better food storage practices
    """
    data = request.get_json()
    logger.debug(f"storage_tips request body keys: {list(data.keys()) if data else 'None'}")

    # Validate produce_name field
    if not data or not data.get('produce_name'):
        logger.warning("storage_tips: Missing produce_name")
        return jsonify({
            'success': False,
            'error': 'produce_name is required'
        }), 400

    try:
        produce_name = data.get('produce_name')
        logger.debug(f"Getting storage tips for: {produce_name}")

        # Service calls AI to generate recommendations
        result = scan_service.get_storage_tips(produce_name)

        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"storage_tips exception: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scan_bp.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint.

    PUBLIC Endpoint: No authentication required
    Purpose: Verify API is running (for uptime monitoring)

    Request:
        GET /api/scan/health

    Response (200 OK):
        {
            "status": "healthy",
            "service": "Produce Scan API"
        }

    Usage:
    - Monitoring tools check this endpoint
    - Kubernetes/Docker health probes use this
    - Simple way to verify service is up
    """
    return jsonify({
        'status': 'healthy',
        'service': 'Produce Scan API'
    }), 200


# ==================== AUTH BLUEPRINT ====================
# Authentication: register, login, logout, me

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user account.

    PUBLIC Endpoint: No authentication required

    Request:
        POST /api/auth/register
        {
            "email": "user@example.com",
            "username": "username",
            "password": "password123"
        }

    Response (201 Created):
        {
            "message": "User created successfully",
            "user_id": 5,
            "email": "user@example.com",
            "username": "username"
        }

    Response (400 Bad Request):
        {
            "error": "User with this email already exists"
        }
        or
        {
            "error": "Username already taken"
        }
        or
        {
            "error": "Missing required fields: email, password, username"
        }

    Password Handling:
    - Password is NOT returned in response
    - Flask-Security hashes password with PBKDF2 (configurable)
    - Never store plaintext passwords

    Validation:
    - Email: Checked for uniqueness
    - Username: Checked for uniqueness
    - Password: Validated by Flask-Security
    """
    data = request.get_json()
    logger.debug(f"Register attempt for email: {data.get('email') if data else 'None'}")

    # Validate all required fields present
    if not all(['email' in data, 'password' in data, 'username' in data]):
        logger.warning("Register: Missing required fields")
        return jsonify({'error': 'Missing required fields: email, password, username'}), 400

    # Call auth service to create user
    user, message = AuthService.create_user(
        email=data.get('email'),
        password=data.get('password'),
        username=data.get('username')
    )

    # Check if creation succeeded
    if not user:
        logger.warning(f"Register failed: {message}")
        return jsonify({'error': message}), 400

    logger.debug(f"User registered: {user.email}")

    return jsonify({
        'message': message,
        'user_id': user.id,
        'email': user.email,
        'username': user.username
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and create session.

    PUBLIC Endpoint: No authentication required

    Request:
        POST /api/auth/login
        {
            "email": "user@example.com",
            "password": "password123"
        }

    Response (200 OK):
        {
            "message": "Logged in successfully",
            "user_id": 5,
            "email": "user@example.com",
            "username": "username"
        }

    Response (401 Unauthorized):
        {
            "error": "Invalid email or password"
        }

    Response (403 Forbidden):
        {
            "error": "User account is inactive"
        }

    Session Creation:
    - Flask-Security creates session cookie
    - Cookie stored in browser (secure, httponly)
    - Session tracked server-side in Flask
    - Subsequent requests include session cookie

    Password Verification:
    - Uses Flask-Security's verify_password (bcrypt/pbkdf2)
    - Compares provided password against hashed version
    - Constant-time comparison to prevent timing attacks
    """
    data = request.get_json()
    logger.debug(f"Login attempt for email: {data.get('email') if data else 'None'}")

    # Validate required fields
    if not all(['email' in data, 'password' in data]):
        logger.warning("Login: Missing required fields")
        return jsonify({'error': 'Missing required fields: email, password'}), 400

    # Find user by email
    user = AuthService.get_user_by_email(data.get('email'))

    if not user:
        logger.warning(f"Login failed: User not found - {data.get('email')}")
        return jsonify({'error': 'Invalid email or password'}), 401

    # Verify password using Flask-Security utility
    if not verify_password(data.get('password'), user.password):
        logger.warning(f"Login failed: Invalid password - {data.get('email')}")
        return jsonify({'error': 'Invalid email or password'}), 401

    # Check if user is active
    if not user.active:
        logger.warning(f"Login failed: User inactive - {data.get('email')}")
        return jsonify({'error': 'User account is inactive'}), 403

    # Create session for this user
    from flask_security import login_user
    login_user(user)
    logger.debug(f"User logged in: {user.email}")

    return jsonify({
        'message': 'Logged in successfully',
        'user_id': user.id,
        'email': user.email,
        'username': user.username
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """
    Destroy user session and logout.

    Protected Endpoint: Requires authentication

    Request:
        POST /api/auth/logout
        (User session in cookie)

    Response (200 OK):
        {
            "message": "Logged out successfully"
        }

    Effect:
    - Destroys user session
    - Clears session cookie (browser deletes it)
    - Subsequent requests no longer authenticated
    - Redirects to login if accessing protected routes
    """
    from flask_security import logout_user
    logger.debug(f"User logging out: {current_user.email}")

    logout_user()

    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """
    Get current authenticated user info.

    Protected Endpoint: Requires authentication
    Purpose: Verify authentication and get user details

    Request:
        GET /api/auth/me
        (User session in cookie)

    Response (200 OK):
        {
            "user_id": 5,
            "email": "user@example.com",
            "username": "username",
            "active": true,
            "roles": ["user"],
            "created_at": "2025-01-31T10:00:00",
            "last_login_at": "2025-01-31T12:30:00"
        }

    Response (401 Unauthorized):
        (If not authenticated, Flask-Security redirects to login)

    Usage:
    - Dashboard checks this on page load
    - Confirms user is still authenticated
    - Gets user info for UI display
    - Verifies session cookie is valid
    """
    return jsonify({
        'user_id': current_user.id,
        'email': current_user.email,
        'username': current_user.username,
        'active': current_user.active,
        'roles': [role.name for role in current_user.roles],
        'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
        'last_login_at': current_user.last_login_at.isoformat() if current_user.last_login_at else None
    }), 200