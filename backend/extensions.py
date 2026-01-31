"""
Flask Extensions: Initialization of Flask-SQLAlchemy and Flask-Security

These objects are created here and initialized with the app in app.py.
Separating extension creation from app creation allows:
- Avoiding circular imports (models import extensions, app imports models)
- Reusing extensions in multiple tests/environments
- Clean initialization order

Initialization Flow:
1. Extensions created here (not yet initialized with app)
2. Models import extensions and use them
3. app.py creates Flask app
4. app.py initializes extensions with app
5. Routes import extensions and use initialized instances
"""

from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore

# Create SQLAlchemy instance (not yet bound to an app)
business_user = SQLAlchemy()

# Create Flask-Security instance (not yet initialized)
security = Security()

# Global reference to user datastore
# Will be set during app initialization (see init_user_datastore function below)
user_datastore = None


def init_user_datastore(app):
    """
    Initialize Flask-Security's user datastore after models are defined.

    This function must be called AFTER models are imported and defined,
    but before routes are created. The order matters because:

    1. Models need SQLAlchemy instance (imported from extensions)
    2. User datastore needs User and Role models
    3. Routes need user_datastore to be fully initialized

    Args:
        app: Flask application instance

    Returns:
        SQLAlchemyUserDatastore: The initialized user datastore

    Example in app.py:
        from backend.extensions import business_user as db, security, init_user_datastore
        from backend.models import User, Role

        app = Flask(__name__)
        db.init_app(app)
        init_user_datastore(app)  # Must come after db.init_app()

        # Now user_datastore is available globally
        from backend.extensions import user_datastore
    """
    global user_datastore

    # Import models here to ensure they're defined
    # (avoids circular imports - models import extensions)
    from backend.models import User, Role

    # Create user datastore
    # SQLAlchemyUserDatastore is Flask-Security's interface to the database
    # It knows how to create users, find users, add roles, etc.
    user_datastore = SQLAlchemyUserDatastore(business_user, User, Role)

    # Initialize Flask-Security with the app and datastore
    # This sets up:
    # - Authentication views (@login_required decorator)
    # - Session management
    # - Password hashing
    # - Role-based access control
    security.init_app(app, user_datastore)

    return user_datastore