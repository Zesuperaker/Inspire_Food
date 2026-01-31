"""
ProduceScanService: Main orchestration service for produce scanning

This service acts as the business logic layer, coordinating between:
- AIService: Analyzes produce from images using LangChain + OpenRouter vision AI
- DatabaseService: Persists scan results and session data

Architecture: Services → Database separation ensures clean dependency flow
"""

from uuid import uuid4
from backend.services.ai_service import AIService
from backend.database import DatabaseService
from typing import Dict, List


class ProduceScanService:
    """
    Main orchestration service for produce scanning operations.

    Coordinates AI analysis with database persistence. All business logic
    for scanning operations lives here.
    """

    def __init__(self):
        """Initialize service with AI and database dependencies"""
        self.ai_service = AIService()
        self.db_service = DatabaseService()

    def start_scan_session(self, user_id: int = None) -> str:
        """
        Create a new scanning session for a user.

        A session groups multiple scans together and tracks aggregate statistics
        like total items scanned, expiring items, etc.

        Args:
            user_id: Optional user ID to associate with the session
                     (allows retrieving user's historical sessions)

        Returns:
            str: Unique 8-character session ID (e.g., "a1b2c3d4")

        Example:
            session_id = service.start_scan_session(user_id=5)
            # Returns: "3f4g5h6i"
        """
        session_id = self.db_service.create_scan_session(user_id=user_id)
        return session_id

    def scan_single_produce(self, image_data: str, session_id: str, user_id: int = None) -> Dict:
        """
        Analyze a single produce item from an image.

        Flow:
        1. AI analyzes the image and extracts produce info (name, freshness, shelf life)
        2. Result is saved to database with unique scan ID
        3. Returns combined AI analysis + database record info

        Args:
            image_data: Base64 encoded image (can include data URI prefix)
            session_id: Current session to group this scan under
            user_id: Optional user ID for authorization tracking

        Returns:
            Dict with structure:
            {
                'success': bool,
                'data': {
                    'id': int (database ID),
                    'scan_id': str (unique scan ID),
                    'produce_name': str,
                    'shelf_life_days': int,
                    'is_expiring_soon': bool,
                    'is_expired': bool,
                    'notes': str,
                    'scanned_at': ISO datetime string
                },
                'error': str (if failed)
            }

        Example:
            result = service.scan_single_produce(
                image_data='data:image/jpeg;base64,/9j/4AAQSkZJ...',
                session_id='abc12345',
                user_id=5
            )
            if result['success']:
                print(result['data']['produce_name'])  # "Apple"
                print(result['data']['shelf_life_days'])  # 7
        """
        try:
            # Step 1: Analyze produce image with AI vision model
            # Returns: {'produce_name': str, 'shelf_life_days': int, ...}
            analysis = self.ai_service.analyze_produce_from_image(image_data)

            # Step 2: Generate unique ID for this scan record
            scan_id = str(uuid4())[:12]  # e.g., "a1b2c3d4e5f6"

            # Step 3: Prepare data for database storage
            # Combines AI analysis with session/user context
            produce_data = {
                'scan_id': scan_id,
                'session_id': session_id,
                'user_id': user_id,
                'produce_name': analysis['produce_name'],
                'shelf_life_days': analysis['shelf_life_days'],
                'is_expiring_soon': analysis['is_expiring_soon'],
                'is_expired': analysis['is_expired'],
                'notes': analysis['notes']
            }

            # Step 4: Persist scan to database
            db_record = self.db_service.save_produce_scan(produce_data)

            # Step 5: Return success response with all details
            return {
                'success': True,
                'data': {
                    'id': db_record.id,
                    'scan_id': scan_id,
                    'produce_name': analysis['produce_name'],
                    'shelf_life_days': analysis['shelf_life_days'],
                    'is_expiring_soon': analysis['is_expiring_soon'],
                    'is_expired': analysis['is_expired'],
                    'notes': analysis['notes'],
                    'scanned_at': db_record.scanned_at.isoformat()
                }
            }

        except Exception as e:
            # Return error response without raising (allows route to handle gracefully)
            return {
                'success': False,
                'error': str(e)
            }

    def scan_batch_produce(self, images: List[str], session_id: str, user_id: int = None) -> Dict:
        """
        Analyze multiple produce items in a single batch operation.

        Processes multiple images and aggregates statistics for efficient
        updates to the session record.

        Args:
            images: List of base64 encoded images
            session_id: Session to group all these scans under
            user_id: Optional user ID for tracking

        Returns:
            Dict with structure:
            {
                'success': bool,
                'session_id': str,
                'scans': [list of scan records],
                'summary': {
                    'total_scanned': int,
                    'expiring_soon_count': int,
                    'expired_count': int,
                    'healthy_count': int
                },
                'error': str (if failed)
            }

        Example:
            result = service.scan_batch_produce(
                images=[img1, img2, img3],
                session_id='abc12345'
            )
            # Scans all 3 images and updates session counts in one operation
        """
        try:
            # Step 1: Analyze all images with AI in batch
            # Returns: {'results': [...], 'summary': {...}}
            batch_analysis = self.ai_service.batch_analyze_produce_from_images(images)

            # Step 2: Save each result to database individually
            saved_results = []
            for analysis in batch_analysis['results']:
                # Generate unique ID for each scan
                scan_id = str(uuid4())[:12]

                # Prepare database record
                produce_data = {
                    'scan_id': scan_id,
                    'session_id': session_id,
                    'user_id': user_id,
                    'produce_name': analysis['produce_name'],
                    'shelf_life_days': analysis['shelf_life_days'],
                    'is_expiring_soon': analysis['is_expiring_soon'],
                    'is_expired': analysis['is_expired'],
                    'notes': analysis['notes']
                }

                # Save and collect result
                db_record = self.db_service.save_produce_scan(produce_data)
                saved_results.append(db_record.to_dict())

            # Step 3: Update session with aggregated counts
            # Avoid querying all scans by using pre-computed batch summary
            summary = batch_analysis['summary']
            self.db_service.update_scan_session(
                session_id,
                total_scanned=summary['total_scanned'],
                expiring_soon_count=summary['expiring_soon_count'],
                expired_count=summary['expired_count']
            )

            # Step 4: Return batch response with all results + summary
            return {
                'success': True,
                'session_id': session_id,
                'scans': saved_results,
                'summary': {
                    'total_scanned': summary['total_scanned'],
                    'expiring_soon_count': summary['expiring_soon_count'],
                    'expired_count': summary['expired_count'],
                    # Healthy = items not expiring and not expired
                    'healthy_count': summary['total_scanned'] - summary['expiring_soon_count'] - summary[
                        'expired_count']
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_session_results(self, session_id: str, user_id: int = None) -> Dict:
        """
        Retrieve all scans from a specific session.

        Includes authorization check: if user_id provided, verifies that
        the session belongs to that user (prevents users from viewing
        other users' session data).

        Args:
            session_id: The session ID to retrieve
            user_id: Optional user ID for authorization check
                    (if provided, only returns session if it belongs to this user)

        Returns:
            Dict with structure:
            {
                'success': bool,
                'session': {session data},
                'scans': [list of all scans in session],
                'error': str (if failed or unauthorized)
            }
        """
        try:
            # Step 1: Fetch session from database
            session = self.db_service.get_scan_session(session_id)

            if not session:
                return {
                    'success': False,
                    'error': f'Session {session_id} not found'
                }

            # Step 2: Authorization check
            # If user_id provided, verify session belongs to this user
            if user_id and session.user_id and session.user_id != user_id:
                return {
                    'success': False,
                    'error': 'Unauthorized access to this session'
                }

            # Step 3: Fetch all scans in the session
            scans = self.db_service.get_session_scans(session_id)

            # Step 4: Return combined response
            return {
                'success': True,
                'session': session.to_dict(),
                'scans': [scan.to_dict() for scan in scans]
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_recent_scans(self, limit: int = 50, user_id: int = None) -> Dict:
        """
        Retrieve recent produce scans.

        If user_id provided, only returns that user's scans (filtered query).
        Otherwise, returns most recent scans globally.

        Args:
            limit: Maximum number of scans to return (default 50, typically capped at 100)
            user_id: If provided, only return scans for this user
                    If None, return all recent scans (public/admin view)

        Returns:
            Dict with structure:
            {
                'success': bool,
                'count': int (number of scans returned),
                'scans': [list of scans],
                'error': str (if failed)
            }
        """
        try:
            # Query either user-specific or all scans, ordered by most recent first
            if user_id:
                # Personal history: scans for a specific user
                scans = self.db_service.get_user_recent_scans(user_id=user_id, limit=limit)
            else:
                # Global view: most recent scans from all users
                scans = self.db_service.get_all_recent_scans(limit=limit)

            return {
                'success': True,
                'count': len(scans),
                'scans': [scan.to_dict() for scan in scans]
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_storage_tips(self, produce_name: str) -> Dict:
        """
        Get AI-generated storage recommendations for a produce type.

        Uses LangChain to prompt the AI model for storage best practices.
        This is a public endpoint (no auth required).

        Args:
            produce_name: Name of the produce (e.g., "Apple", "Spinach")

        Returns:
            Dict with structure:
            {
                'success': bool,
                'produce': str,
                'recommendations': str (2-3 sentence recommendations),
                'error': str (if failed)
            }

        Example:
            result = service.get_storage_tips("Banana")
            # Returns recommendations on temperature, humidity, container type
        """
        try:
            # Call AI service to generate recommendations
            recommendations = self.ai_service.get_storage_recommendations(produce_name)

            return {
                'success': True,
                'produce': produce_name,
                'recommendations': recommendations
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }