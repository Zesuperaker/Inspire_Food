from uuid import uuid4
from backend.services.ai_service import AIService
from backend.database import DatabaseService
from typing import Dict, List


class ProduceScanService:
    """Main service orchestrating produce scanning operations"""

    def __init__(self):
        self.ai_service = AIService()
        self.db_service = DatabaseService()

    def start_scan_session(self, user_id: int = None) -> str:
        """
        Start a new scanning session

        Args:
            user_id: Optional user ID to associate with session

        Returns:
            session_id: Unique identifier for the scan session
        """
        session_id = self.db_service.create_scan_session(user_id=user_id)
        return session_id

    def scan_single_produce(self, produce_description: str, session_id: str, user_id: int = None) -> Dict:
        """
        Scan a single produce item

        Args:
            produce_description: Description of the produce
            session_id: Current session ID
            user_id: Optional user ID to associate with scan

        Returns:
            Dict with produce analysis and database ID
        """
        try:
            # Analyze produce with AI
            analysis = self.ai_service.analyze_produce(produce_description)

            # Generate unique scan ID for this item
            scan_id = str(uuid4())[:12]

            # Prepare data for database
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

            # Save to database
            db_record = self.db_service.save_produce_scan(produce_data)

            # Return result with database record info
            return {
                'success': True,
                'data': {
                    'id': db_record.id,
                    'scan_id': scan_id,
                    'produce_name': analysis['produce_name'],
                    'shelf_life_days': analysis['shelf_life_days'],
                    'is_expiring_soon': analysis['is_expiring_soon'],
                    'is_expired': analysis['is_expired'],
                    'notes': analysis['notes']
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def scan_batch_produce(self, produce_list: List[str], session_id: str, user_id: int = None) -> Dict:
        """
        Scan multiple produce items in a batch

        Args:
            produce_list: List of produce descriptions
            session_id: Current session ID
            user_id: Optional user ID to associate with scans

        Returns:
            Dict with all results and aggregated statistics
        """
        try:
            # Analyze all produce with AI
            batch_analysis = self.ai_service.batch_analyze_produce(produce_list)

            # Save each result to database
            saved_results = []
            for analysis in batch_analysis['results']:
                scan_id = str(uuid4())[:12]

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

                db_record = self.db_service.save_produce_scan(produce_data)
                saved_results.append(db_record.to_dict())

            # Update session with aggregated counts
            summary = batch_analysis['summary']
            self.db_service.update_scan_session(
                session_id,
                total_scanned=summary['total_scanned'],
                expiring_soon_count=summary['expiring_soon_count'],
                expired_count=summary['expired_count']
            )

            return {
                'success': True,
                'session_id': session_id,
                'scans': saved_results,
                'summary': {
                    'total_scanned': summary['total_scanned'],
                    'expiring_soon_count': summary['expiring_soon_count'],
                    'expired_count': summary['expired_count'],
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
        Retrieve all results from a scanning session

        Args:
            session_id: The session ID to retrieve
            user_id: Optional user ID for authorization check

        Returns:
            Dict with session data and all scans
        """
        try:
            session = self.db_service.get_scan_session(session_id)

            if not session:
                return {
                    'success': False,
                    'error': f'Session {session_id} not found'
                }

            # Check authorization if user_id provided
            if user_id and session.user_id and session.user_id != user_id:
                return {
                    'success': False,
                    'error': 'Unauthorized access to this session'
                }

            scans = self.db_service.get_session_scans(session_id)

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
        Get recent produce scans

        Args:
            limit: Maximum number of scans to retrieve
            user_id: If provided, only get scans for this user

        Returns:
            Dict with list of recent scans
        """
        try:
            if user_id:
                scans = self.db_service.get_user_recent_scans(user_id=user_id, limit=limit)
            else:
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
        Get storage recommendations for a produce type

        Args:
            produce_name: Name of the produce

        Returns:
            Dict with storage recommendations
        """
        try:
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