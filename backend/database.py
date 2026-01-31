"""
DatabaseService: Data persistence layer

Encapsulates all database operations using SQLAlchemy ORM.
Provides clean interface to the routes layer without exposing ORM details.

All methods are static (no instance state) for stateless query execution.
Error handling: catches SQLAlchemyError and re-raises as Exception with context.

Database Models:
- ProduceScan: Individual produce scan records
- ScanSession: Session grouping multiple scans
"""

from backend.extensions import business_user as db
from backend.models import ProduceScan, ScanSession
from sqlalchemy.exc import SQLAlchemyError
from uuid import uuid4


class DatabaseService:
    """
    Stateless data access service for scan and session operations.

    All methods are @staticmethod because:
    - No instance state needed
    - Clear that methods don't rely on initialization
    - Can be called directly without instantiation
    - Easier to unit test
    """

    @staticmethod
    def create_scan_session(user_id: int = None):
        """
        Create a new scan session and return its ID.

        A session is a container for grouping multiple produce scans.
        Sessions track:
        - Session ID: unique identifier
        - User ID: which user owns this session (optional for anonymous)
        - Created timestamp
        - Aggregate counts: total scans, expiring soon, expired

        The session ID is NOT a UUID - it's first 8 characters of UUID
        for shorter, more user-friendly IDs in URLs/sharing.

        Args:
            user_id: Optional user ID to associate session with
                    If None, session is anonymous (can still scan)

        Returns:
            str: 8-character session ID (e.g., "a1b2c3d4")

        Raises:
            Exception: If database commit fails (wraps SQLAlchemyError)

        Example:
            session_id = db_service.create_scan_session(user_id=5)
            # INSERT INTO scan_sessions (session_id, user_id, created_at)
            # VALUES ('a1b2c3d4', 5, now())
        """
        try:
            # Generate 8-character session ID from UUID
            # Full UUID is 36 chars; truncated to 8 for URLs/UX
            session_id = str(uuid4())[:8]

            # Create session record
            session = ScanSession(session_id=session_id, user_id=user_id)

            # Add to session and flush to database
            db.session.add(session)
            db.session.commit()

            return session_id

        except SQLAlchemyError as e:
            # Rollback on error to avoid transaction limbo
            db.session.rollback()
            raise Exception(f"Database error creating session: {str(e)}")

    @staticmethod
    def save_produce_scan(produce_data: dict):
        """
        Save a single produce scan record to database.

        Takes analysis output from AI and persists it with scan context.

        Args:
            produce_data: Dictionary with required fields:
                'scan_id': str (unique ID for this scan)
                'session_id': str (which session this scan belongs to)
                'user_id': int (optional, which user scanned this)
                'produce_name': str (what was scanned)
                'shelf_life_days': int (AI estimate)
                'is_expiring_soon': bool (derived from shelf_life_days)
                'is_expired': bool (derived from shelf_life_days)
                'notes': str (optional, AI assessment)

        Returns:
            ProduceScan: The saved ORM object (with auto-generated ID)

        Raises:
            Exception: If database insert fails

        Example:
            produce_data = {
                'scan_id': 'scan_abc123',
                'session_id': 'sess_xyz',
                'user_id': 5,
                'produce_name': 'Apple',
                'shelf_life_days': 7,
                'is_expiring_soon': False,
                'is_expired': False,
                'notes': 'Red apple, fresh'
            }
            scan = db_service.save_produce_scan(produce_data)
            print(scan.id)  # Auto-incremented ID: 42
        """
        try:
            # Create ORM object from provided data
            # Uses .get() for optional fields with defaults
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

            # Persist to database
            db.session.add(scan)
            db.session.commit()

            return scan

        except SQLAlchemyError as e:
            db.session.rollback()
            raise Exception(f"Database error saving scan: {str(e)}")

    @staticmethod
    def update_scan_session(session_id: str, total_scanned: int,
                            expiring_soon_count: int, expired_count: int):
        """
        Update scan session with aggregated scan statistics.

        Called after batch scanning to update session totals.
        Avoids recalculating counts from individual scans.

        Args:
            session_id: Which session to update
            total_scanned: Total scans in this session
            expiring_soon_count: How many scans are expiring soon
            expired_count: How many scans are already expired

        Returns:
            ScanSession: Updated session object

        Raises:
            Exception: If session not found or update fails

        Example:
            db_service.update_scan_session(
                session_id='abc123',
                total_scanned=10,
                expiring_soon_count=3,
                expired_count=1
            )
            # UPDATE scan_sessions SET total_scanned=10,
            # expiring_soon_count=3, expired_count=1 WHERE session_id='abc123'
        """
        try:
            # Find the session
            session = ScanSession.query.filter_by(session_id=session_id).first()

            if session:
                # Update aggregate fields
                session.total_scanned = total_scanned
                session.expiring_soon_count = expiring_soon_count
                session.expired_count = expired_count

                # Commit changes
                db.session.commit()
                return session
            else:
                raise Exception(f"Session {session_id} not found")

        except SQLAlchemyError as e:
            db.session.rollback()
            raise Exception(f"Database error updating session: {str(e)}")

    @staticmethod
    def get_scan_session(session_id: str):
        """
        Retrieve a single scan session by ID.

        Used to fetch session metadata and check ownership.

        Args:
            session_id: The session ID to retrieve

        Returns:
            ScanSession or None: The session object if found, else None

        Raises:
            Exception: If database query fails (unlikely but handled)

        Example:
            session = db_service.get_scan_session('abc123')
            if session:
                print(session.total_scanned)  # 10
                print(session.user_id)  # 5
        """
        try:
            session = ScanSession.query.filter_by(session_id=session_id).first()
            return session
        except SQLAlchemyError as e:
            raise Exception(f"Database error fetching session: {str(e)}")

    @staticmethod
    def get_session_scans(session_id: str):
        """
        Retrieve all scans belonging to a session.

        Used when displaying session results.

        Args:
            session_id: The session ID to fetch scans for

        Returns:
            list[ProduceScan]: List of scan records (empty list if no scans)

        Raises:
            Exception: If database query fails

        Example:
            scans = db_service.get_session_scans('abc123')
            for scan in scans:
                print(f"{scan.produce_name}: {scan.shelf_life_days} days")
        """
        try:
            scans = ProduceScan.query.filter_by(
                session_id=session_id
            ).all()
            return scans
        except SQLAlchemyError as e:
            raise Exception(f"Database error fetching scans: {str(e)}")

    @staticmethod
    def get_user_recent_scans(user_id: int, limit: int = 50):
        """
        Retrieve recent scans for a specific user.

        Used in dashboard to show user's scanning history.
        Orders by most recent first.

        Args:
            user_id: User to fetch scans for
            limit: Maximum number of scans to return (default 50)

        Returns:
            list[ProduceScan]: User's recent scans, newest first

        Raises:
            Exception: If database query fails

        Example:
            scans = db_service.get_user_recent_scans(user_id=5, limit=10)
            # SELECT * FROM produce_scans WHERE user_id=5
            # ORDER BY scanned_at DESC LIMIT 10
        """
        try:
            scans = ProduceScan.query.filter_by(
                user_id=user_id
            ).order_by(
                ProduceScan.scanned_at.desc()  # Newest first
            ).limit(limit).all()
            return scans
        except SQLAlchemyError as e:
            raise Exception(f"Database error fetching user scans: {str(e)}")

    @staticmethod
    def get_all_recent_scans(limit: int = 50):
        """
        Retrieve most recent scans globally (from all users).

        Used for admin/analytics views or public scan feed.

        Args:
            limit: Maximum number of scans to return

        Returns:
            list[ProduceScan]: Most recent scans, ordered newest first

        Raises:
            Exception: If database query fails

        Example:
            scans = db_service.get_all_recent_scans(limit=20)
            # SELECT * FROM produce_scans
            # ORDER BY scanned_at DESC LIMIT 20
        """
        try:
            scans = ProduceScan.query.order_by(
                ProduceScan.scanned_at.desc()  # Newest first
            ).limit(limit).all()
            return scans
        except SQLAlchemyError as e:
            raise Exception(f"Database error fetching recent scans: {str(e)}")

    @staticmethod
    def delete_old_sessions(days: int = 7):
        """
        Delete scan sessions older than specified number of days.

        Used for data cleanup/privacy - removes old anonymous sessions.
        Cascade delete removes all scans in those sessions (due to
        ORM cascade='all, delete-orphan' configuration).

        Args:
            days: Delete sessions older than this many days (default 7)

        Returns:
            bool: True if deletion successful

        Raises:
            Exception: If database operation fails

        Example:
            deleted = db_service.delete_old_sessions(days=30)
            # DELETE FROM scan_sessions WHERE created_at < (now() - 30 days)
            # Cascades to DELETE matching records from produce_scans
        """
        from datetime import datetime, timedelta
        try:
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Delete sessions older than cutoff
            # Cascade rules handle deleting associated scans
            ScanSession.query.filter(
                ScanSession.created_at < cutoff_date
            ).delete()

            db.session.commit()
            return True

        except SQLAlchemyError as e:
            db.session.rollback()
            raise Exception(f"Database error deleting old sessions: {str(e)}")