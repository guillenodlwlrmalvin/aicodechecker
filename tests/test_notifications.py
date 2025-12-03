"""
Unit tests for notification functionality.
"""
import os
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app
from models import (
    initialize_database, create_user, create_notification,
    get_user_notifications, get_unread_notification_count,
    mark_notification_as_read, mark_all_notifications_as_read
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_notifications.db')
    initialize_database(db)
    return db


@pytest.fixture
def client(db_path, monkeypatch):
    """Create a test client with isolated database."""
    monkeypatch.setenv('FLASK_ENV', 'testing')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key'
    
    with flask_app.test_client() as client:
        with flask_app.app_context():
            yield client


@pytest.fixture
def logged_in_user(client, db_path):
    """Create and login a test user."""
    password_hash = generate_password_hash('password123')
    user_id = create_user(db_path, 'test@test.com', password_hash, is_approved=1)
    
    client.post('/login', data={
        'username': 'test@test.com',
        'password': 'password123'
    })
    
    return user_id


class TestNotifications:
    """Tests for notification functionality."""
    
    def test_create_notification(self, db_path, logged_in_user):
        """Test creating a notification."""
        notification_id = create_notification(
            db_path, logged_in_user, 'test_type', 'Test Title',
            'Test message', logged_in_user, 'user'
        )
        
        assert notification_id > 0
    
    def test_get_user_notifications(self, db_path, logged_in_user):
        """Test retrieving user notifications."""
        # Create some notifications
        create_notification(db_path, logged_in_user, 'type1', 'Title 1', 'Message 1', 
                          logged_in_user, 'user')
        create_notification(db_path, logged_in_user, 'type2', 'Title 2', 'Message 2',
                          logged_in_user, 'user')
        
        notifications = get_user_notifications(db_path, logged_in_user)
        assert len(notifications) >= 2
    
    def test_get_unread_count(self, db_path, logged_in_user):
        """Test getting unread notification count."""
        # Create unread notifications
        create_notification(db_path, logged_in_user, 'type1', 'Title 1', 'Message 1',
                          logged_in_user, 'user')
        create_notification(db_path, logged_in_user, 'type2', 'Title 2', 'Message 2',
                          logged_in_user, 'user')
        
        count = get_unread_notification_count(db_path, logged_in_user)
        assert count >= 2
    
    def test_mark_notification_as_read(self, db_path, logged_in_user):
        """Test marking a notification as read."""
        notification_id = create_notification(
            db_path, logged_in_user, 'type1', 'Title', 'Message',
            logged_in_user, 'user'
        )
        
        mark_notification_as_read(db_path, notification_id, logged_in_user)
        
        # Verify it's marked as read
        notifications = get_user_notifications(db_path, logged_in_user, unread_only=True)
        unread_ids = [n['id'] for n in notifications]
        assert notification_id not in unread_ids
    
    def test_mark_all_notifications_as_read(self, db_path, logged_in_user):
        """Test marking all notifications as read."""
        # Create multiple notifications
        create_notification(db_path, logged_in_user, 'type1', 'Title 1', 'Message 1',
                          logged_in_user, 'user')
        create_notification(db_path, logged_in_user, 'type2', 'Title 2', 'Message 2',
                          logged_in_user, 'user')
        
        mark_all_notifications_as_read(db_path, logged_in_user)
        
        # Verify all are read
        count = get_unread_notification_count(db_path, logged_in_user)
        assert count == 0

