from backend.extensions import business_user as db
from backend.models import ProduceScan, ScanSession
from sqlalchemy.exc import SQLAlchemyError
from uuid import uuid4


class DatabaseService:
    """Service for handling all database operations"""

    @staticmethod
    def create_scan_session(user_id: int = None):
        """
        Create a new scan session and return session_id

        Args:
            user_id: Optional user ID to associate with session
        """
        try:
            session_id = str(uuid4())[:8]
            session = ScanSession(session_id=session_id, user_id=user_id)
            db.session.add(session)
            db.session.commit()
            return session_id
        except SQLAlchemyError as e:
            db.session.rollback()
            raise Exception(f"Database error creating session: {str(e)}")

    @staticmethod
    def save_produce_scan(produce_data: dict):
        """
        Save a single produce scan to database

        Args:
            produce_data: dict with keys {
                'scan_id': str,
                'session_id': str,
                'user_id': int (optional),
                'produce_name': str,
                'shelf_life_days': int,
                'is_expiring_soon': bool,
                'is_expired': bool,
                'notes': str (optional)
            }

        Returns:
            ProduceScan object
        """
        try:
            scan = ProduceScan(
                scan_id=produce_data['scan_id'],
                session_id=produce_data.get('session_id'),
                user_id=produce_data.get('user_id'),
                produce_name=produce_data['produce_name'],
                shelf_life_days=produce_data['shelf_life_days'],
                is_expiring_soon=produce_data.get('is_expiring_soon', False),
                is_expired=produce_data.get('is_expired', False),
                notes=produce_data.get('notes', None)
            )
            db.session.add(scan)
            db.session.commit()
            return scan
        except SQLAlchemyError as e:
            db.session.rollback()
            raise Exception(f"Database error saving scan: {str(e)}")

    @staticmethod
    def update_scan_session(session_id: str, total_scanned: int,
                            expiring_soon_count: int, expired_count: int):
        """Update scan session with aggregated counts"""
        try:
            session = ScanSession.query.filter_by(session_id=session_id).first()
            if session:
                session.total_scanned = total_scanned
                session.expiring_soon_count = expiring_soon_count
                session.expired_count = expired_count
                db.session.commit()
                return session
            else:
                raise Exception(f"Session {session_id} not found")
        except SQLAlchemyError as e:
            db.session.rollback()
            raise Exception(f"Database error updating session: {str(e)}")

    @staticmethod
    def get_scan_session(session_id: str):
        """Retrieve scan session by ID"""
        try:
            session = ScanSession.query.filter_by(session_id=session_id).first()
            return session
        except SQLAlchemyError as e:
            raise Exception(f"Database error fetching session: {str(e)}")

    @staticmethod
    def get_session_scans(session_id: str):
        """Retrieve all scans for a session"""
        try:
            scans = ProduceScan.query.filter_by(
                session_id=session_id
            ).all()
            return scans
        except SQLAlchemyError as e:
            raise Exception(f"Database error fetching scans: {str(e)}")

    @staticmethod
    def get_user_recent_scans(user_id: int, limit: int = 50):
        """Get recent scans for a specific user"""
        try:
            scans = ProduceScan.query.filter_by(
                user_id=user_id
            ).order_by(
                ProduceScan.scanned_at.desc()
            ).limit(limit).all()
            return scans
        except SQLAlchemyError as e:
            raise Exception(f"Database error fetching user scans: {str(e)}")

    @staticmethod
    def get_all_recent_scans(limit: int = 50):
        """Get all recent scans"""
        try:
            scans = ProduceScan.query.order_by(
                ProduceScan.scanned_at.desc()
            ).limit(limit).all()
            return scans
        except SQLAlchemyError as e:
            raise Exception(f"Database error fetching recent scans: {str(e)}")

    @staticmethod
    def delete_old_sessions(days: int = 7):
        """Delete scan sessions older than specified days"""
        from datetime import datetime, timedelta
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            ScanSession.query.filter(
                ScanSession.created_at < cutoff_date
            ).delete()
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            raise Exception(f"Database error deleting old sessions: {str(e)}")