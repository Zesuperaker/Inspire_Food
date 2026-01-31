import pytest
import json
from unittest.mock import patch, MagicMock
from app import create_app
from backend.extensions import business_user as db
from backend.models import User


@pytest.fixture
def app():
    """Create and configure test app"""
    app = create_app('testing')

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def auth_user(app, client):
    """Create authenticated test user and login via API"""
    # Register user via the API
    client.post(
        '/api/auth/register',
        json={
            'email': 'test@example.com',
            'password': 'password123',
            'username': 'testuser'
        }
    )

    # Login via API to establish session
    client.post(
        '/api/auth/login',
        json={
            'email': 'test@example.com',
            'password': 'password123'
        }
    )

    # Get the created user from database for reference
    with app.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        return user


class TestAIScanningRoutes:
    """Tests for AI scanning routes"""

    def test_start_session_requires_auth(self, client):
        """Test that start-session requires authentication"""
        response = client.post('/api/scan/start-session')
        assert response.status_code == 302

    def test_start_session_authenticated(self, client, auth_user, app):
        """Test starting a scan session with authentication"""
        response = client.post('/api/scan/start-session', json={})

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'session_id' in data
        assert data['user_id'] == auth_user.id

    @patch('backend.services.ai_service.ChatOpenAI')
    def test_scan_single_produce(self, mock_chat_openai, client, auth_user, app):
        """Test scanning a single produce item"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'produce_name': 'Apple',
            'shelf_life_days': 7,
            'is_expiring_soon': False,
            'is_expired': False,
            'notes': 'Fresh apple in good condition'
        })

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm

        with app.app_context():
            from backend.services import ProduceScanService
            scan_service = ProduceScanService()
            scan_service.ai_service.llm = mock_llm
            session_id = scan_service.start_scan_session(user_id=auth_user.id)

        response = client.post(
            '/api/scan/single',
            json={
                'produce_description': 'Red apple, firm, no bruises',
                'session_id': session_id
            }
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['produce_name'] == 'Apple'
        assert data['data']['shelf_life_days'] == 7

    @patch('backend.services.ai_service.ChatOpenAI')
    def test_scan_single_missing_fields(self, mock_chat_openai, client, auth_user, app):
        """Test scan_single with missing required fields"""
        response = client.post(
            '/api/scan/single',
            json={'produce_description': 'Apple'}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    @patch('backend.services.ai_service.ChatOpenAI')
    def test_scan_batch_produce(self, mock_chat_openai, client, auth_user, app):
        """Test scanning multiple produce items in batch"""
        mock_responses = [
            json.dumps({
                'produce_name': 'Apple',
                'shelf_life_days': 7,
                'is_expiring_soon': False,
                'is_expired': False,
                'notes': 'Fresh'
            }),
            json.dumps({
                'produce_name': 'Banana',
                'shelf_life_days': 2,
                'is_expiring_soon': True,
                'is_expired': False,
                'notes': 'Expiring soon'
            })
        ]

        mock_responses_iter = iter(mock_responses)

        def mock_invoke(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.content = next(mock_responses_iter)
            return mock_response

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = mock_invoke
        mock_chat_openai.return_value = mock_llm

        with app.app_context():
            from backend.services import ProduceScanService
            scan_service = ProduceScanService()
            scan_service.ai_service.llm = mock_llm
            session_id = scan_service.start_scan_session(user_id=auth_user.id)

        response = client.post(
            '/api/scan/batch',
            json={
                'produce_list': ['Red apple', 'Yellow banana'],
                'session_id': session_id
            }
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['scans']) == 2
        assert data['summary']['total_scanned'] == 2
        assert data['summary']['expiring_soon_count'] == 1

    @patch('backend.services.ai_service.ChatOpenAI')
    def test_scan_batch_empty_list(self, mock_chat_openai, client, auth_user, app):
        """Test batch scan with empty list"""
        with app.app_context():
            from backend.services import ProduceScanService
            scan_service = ProduceScanService()
            session_id = scan_service.start_scan_session(user_id=auth_user.id)

        response = client.post(
            '/api/scan/batch',
            json={
                'produce_list': [],
                'session_id': session_id
            }
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_get_session_results(self, client, auth_user, app):
        """Test retrieving session results"""
        with app.app_context():
            from backend.services import ProduceScanService
            scan_service = ProduceScanService()
            session_id = scan_service.start_scan_session(user_id=auth_user.id)

        response = client.get(f'/api/scan/session/{session_id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['session']['session_id'] == session_id
        assert data['session']['user_id'] == auth_user.id

    def test_get_session_not_found(self, client, auth_user, app):
        """Test getting non-existent session"""
        response = client.get('/api/scan/session/nonexistent')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False

    @patch('backend.services.ai_service.ChatOpenAI')
    def test_get_recent_scans(self, mock_chat_openai, client, auth_user, app):
        """Test getting recent scans for user"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'produce_name': 'Apple',
            'shelf_life_days': 7,
            'is_expiring_soon': False,
            'is_expired': False,
            'notes': 'Fresh'
        })

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm

        with app.app_context():
            from backend.services import ProduceScanService
            scan_service = ProduceScanService()
            scan_service.ai_service.llm = mock_llm
            session_id = scan_service.start_scan_session(user_id=auth_user.id)
            scan_service.scan_single_produce('Apple', session_id, user_id=auth_user.id)

        response = client.get('/api/scan/recent')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['count'] >= 1

    @patch('backend.services.ai_service.ChatOpenAI')
    def test_storage_tips(self, mock_chat_openai, client):
        """Test getting storage tips (public endpoint)"""
        mock_response = MagicMock()
        mock_response.content = "Store at room temperature away from direct sunlight."

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm

        with patch('backend.services.ai_service.ChatOpenAI', return_value=mock_llm):
            response = client.post(
                '/api/scan/storage-tips',
                json={'produce_name': 'Apple'}
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'recommendations' in data

    def test_storage_tips_missing_produce_name(self, client):
        """Test storage tips without produce name"""
        response = client.post(
            '/api/scan/storage-tips',
            json={}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get('/api/scan/health')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'