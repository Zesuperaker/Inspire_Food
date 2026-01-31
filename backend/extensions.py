from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore

business_user = SQLAlchemy()
security = Security()
user_datastore = None


def init_user_datastore(app):
    """Initialize user_datastore after models are defined"""
    global user_datastore
    from backend.models import User, Role
    user_datastore = SQLAlchemyUserDatastore(business_user, User, Role)
    security.init_app(app, user_datastore)
    return user_datastore