"""
SQLAlchemy Models: ORM definitions for database schema

Three main models:
1. Role: Authorization roles for users (admin, user, etc.)
2. User: User accounts with authentication
3. ProduceScan: Individual scan records
4. ScanSession: Session grouping multiple scans

Relationships:
- User ↔ Role: Many-to-many via roles_users junction table
- User ↔ ProduceScan: One-to-many (user has many scans)
- ScanSession ↔ ProduceScan: One-to-many (session has many scans)
"""

from datetime import datetime
from uuid import uuid4
from backend.extensions import business_user as db
from flask_security import UserMixin, RoleMixin

# ==================== JUNCTION TABLE ====================

roles_users = db.Table(
    'roles_users',
    # Foreign key to user.id
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    # Foreign key to role.id
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)
"""
Junction table for many-to-many relationship between User and Role.

Example:
- User 1 has roles: ['admin', 'user']
- User 2 has roles: ['user']

Table structure:
user_id | role_id
--------|--------
1       | 1 (admin)
1       | 2 (user)
2       | 2 (user)
"""


# ==================== AUTHENTICATION MODELS ====================

class Role(db.Model, RoleMixin):
    """
    Authorization role model.

    Defines different access levels:
    - admin: Full system access
    - user: Standard user access

    RoleMixin: Provides Flask-Security required attributes
    """

    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))

    def __repr__(self):
        return f'<Role {self.name}>'


class User(db.Model, UserMixin):
    """
    User account model with authentication credentials.

    Inherits from UserMixin: Provides Flask-Security required methods
    - is_authenticated: True if user is logged in
    - is_active: True if user account is active
    - is_anonymous: Always False
    - get_id(): Returns user ID as string

    Fields:
    - id: Primary key (auto-increment)
    - email: Unique email, used for login
    - username: Unique display name
    - password: Hashed password (Flask-Security hashes before storing)
    - active: Whether account is enabled (can deactivate without deleting)
    - fs_uniquifier: Flask-Security specific field (unique identifier)
    - created_at: Timestamp when account created
    - last_login_at: Timestamp of most recent login
    - roles: Relationship to Role via junction table
    - scans: Relationship to ProduceScan (all scans this user made)
    """

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean(), default=True, nullable=False)
    fs_uniquifier = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        default=lambda: str(uuid4())
    )
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime())

    # Relationship: User has many Roles (many-to-many)
    roles = db.relationship(
        'Role',
        secondary=roles_users,  # Use junction table
        backref=db.backref('users', lazy='dynamic')  # Reverse relation
    )

    # Relationship: User has many ProduceScan records
    scans = db.relationship(
        'ProduceScan',
        backref='user',  # Can access user from scan: scan.user
        lazy=True,  # Load scans when user accessed
        cascade='all, delete-orphan'  # Delete scans when user deleted
    )

    def __repr__(self):
        return f'<User {self.email}>'

    def to_dict(self):
        """Convert user to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'active': self.active,
            'roles': [role.name for role in self.roles],
            'created_at': self.created_at.isoformat(),
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None
        }


# ==================== PRODUCE SCANNING MODELS ====================

class ProduceScan(db.Model):
    """
    Individual produce scan record.

    Stores the result of analyzing one produce item.
    Links to both a user (who scanned) and session (grouping).

    Fields:
    - id: Primary key (auto-increment, used in responses)
    - scan_id: Unique identifier for this scan (short UUID)
    - session_id: Foreign key to ScanSession (groups multiple scans)
    - user_id: Foreign key to User (who performed scan)
    - produce_name: What produce was identified (e.g., 'Apple')
    - shelf_life_days: Estimated days until expiration
    - is_expiring_soon: Derived flag (days <= 3)
    - is_expired: Derived flag (days <= 0)
    - scanned_at: Timestamp of when scan was performed
    - notes: AI assessment of freshness/condition
    """

    __tablename__ = 'produce_scans'

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.String(50), unique=True, nullable=False)
    session_id = db.Column(
        db.String(50),
        db.ForeignKey('scan_sessions.session_id'),
        nullable=True  # Scans can exist without session (edge case)
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True  # Scans can exist without user (anonymous)
    )
    produce_name = db.Column(db.String(100), nullable=False)
    shelf_life_days = db.Column(db.Integer, nullable=False)
    is_expiring_soon = db.Column(db.Boolean, default=False)
    is_expired = db.Column(db.Boolean, default=False)
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)

    def to_dict(self):
        """Convert scan to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'produce_name': self.produce_name,
            'shelf_life_days': self.shelf_life_days,
            'is_expiring_soon': self.is_expiring_soon,
            'is_expired': self.is_expired,
            'scanned_at': self.scanned_at.isoformat(),
            'notes': self.notes
        }


class ScanSession(db.Model):
    """
    Scan session model - groups multiple scans together.

    Purpose:
    - Group related scans (e.g., scanning groceries in one session)
    - Track aggregate statistics (total, expiring, expired)
    - Enable user to view results from one "scanning event"

    Fields:
    - id: Primary key (auto-increment)
    - session_id: User-friendly ID (short UUID for URLs)
    - user_id: Which user owns this session (optional)
    - total_scanned: Aggregate count of scans in session
    - expiring_soon_count: How many items expiring soon
    - expired_count: How many items already expired
    - created_at: When session was created
    - scans: Relationship to all ProduceScan records in this session

    Statistics:
    These counts are pre-computed and stored for fast queries.
    Updated after batch scans complete (efficiency optimization).
    Avoids recalculating from individual scans every time.
    """

    __tablename__ = 'scan_sessions'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True  # Sessions can be anonymous
    )
    total_scanned = db.Column(db.Integer, default=0)
    expiring_soon_count = db.Column(db.Integer, default=0)
    expired_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship: Session has many ProduceScan records
    scans = db.relationship(
        'ProduceScan',
        backref='session',  # Can access session from scan: scan.session
        lazy=True,  # Load scans when session accessed
        cascade='all, delete-orphan'  # Delete scans when session deleted
    )

    def to_dict(self):
        """Convert session to dictionary for JSON serialization."""
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'total_scanned': self.total_scanned,
            'expiring_soon_count': self.expiring_soon_count,
            'expired_count': self.expired_count,
            'created_at': self.created_at.isoformat()
        }