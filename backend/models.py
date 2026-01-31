from datetime import datetime
from uuid import uuid4
from backend.extensions import business_user as db
from flask_security import UserMixin, RoleMixin

# ==================== AUTHENTICATION MODELS ====================

roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)


class Role(db.Model, RoleMixin):
    """Model for user roles"""
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))

    def __repr__(self):
        return f'<Role {self.name}>'


class User(db.Model, UserMixin):
    """Model for user accounts"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean(), default=True, nullable=False)
    fs_uniquifier = db.Column(db.String(255), unique=True, nullable=False, default=lambda: str(uuid4()))
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime())

    # Relationship to roles
    roles = db.relationship(
        'Role',
        secondary=roles_users,
        backref=db.backref('users', lazy='dynamic')
    )

    # Relationship to produce scans (user can have many scans)
    scans = db.relationship('ProduceScan', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.email}>'

    def to_dict(self):
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
    """Model for storing produce scan results"""
    __tablename__ = 'produce_scans'

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.String(50), unique=True, nullable=False)
    session_id = db.Column(db.String(50), db.ForeignKey('scan_sessions.session_id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    produce_name = db.Column(db.String(100), nullable=False)
    shelf_life_days = db.Column(db.Integer, nullable=False)
    is_expiring_soon = db.Column(db.Boolean, default=False)
    is_expired = db.Column(db.Boolean, default=False)
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)

    def to_dict(self):
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
    """Model for storing scan session metadata"""
    __tablename__ = 'scan_sessions'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    total_scanned = db.Column(db.Integer, default=0)
    expiring_soon_count = db.Column(db.Integer, default=0)
    expired_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to scans
    scans = db.relationship('ProduceScan', backref='session', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'total_scanned': self.total_scanned,
            'expiring_soon_count': self.expiring_soon_count,
            'expired_count': self.expired_count,
            'created_at': self.created_at.isoformat()
        }