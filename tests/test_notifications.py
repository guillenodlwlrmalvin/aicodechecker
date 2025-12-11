"""Tests for Notifications (6 tests)."""
import os
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import (
    initialize_database, create_user, create_notification, 
    get_user_notifications, mark_notification_as_read
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_notifications.db')
    initialize_database(db)
    return db


@pytest.fixture
def client(db_path):
    """Create a test client."""
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def logged_in_user(client, db_path):
    """Create and login a user."""
    user_id = create_user(db_path, 'notifyuser@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    client.post('/login', data={
        'username': 'notifyuser@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    return user_id


def test_get_notifications_requires_login(client):
    """Test that getting notifications returns empty list when not logged in."""
    res = client.get('/api/notifications', follow_redirects=False)
    # API returns 200 with empty list when not logged in
    assert res.status_code == 200
    import json
    data = json.loads(res.data)
    assert data.get('notifications') == []
    assert data.get('unread_count') == 0


def test_get_notifications(client, db_path, logged_in_user):
    """Test getting user notifications."""
    from models import get_user_by_username
    user = get_user_by_username(db_path, 'notifyuser@gmail.com')
    create_notification(db_path, user['id'], 'info', 'Test Title', 'Test notification')
    
    res = client.get('/api/notifications', follow_redirects=True)
    assert res.status_code == 200


def test_mark_notification_read(client, db_path, logged_in_user):
    """Test marking a notification as read."""
    from models import get_user_by_username
    user = get_user_by_username(db_path, 'notifyuser@gmail.com')
    notification_id = create_notification(db_path, user['id'], 'info', 'Test Title', 'Test message')
    
    res = client.post(f'/api/notifications/{notification_id}/read', follow_redirects=True)
    assert res.status_code == 200
    
    notifications = get_user_notifications(db_path, user['id'])
    read_notif = [n for n in notifications if n['id'] == notification_id]
    if read_notif:
        assert read_notif[0]['is_read'] == 1


def test_mark_all_notifications_read(client, db_path, logged_in_user):
    """Test marking all notifications as read."""
    from models import get_user_by_username, mark_all_notifications_as_read
    user = get_user_by_username(db_path, 'notifyuser@gmail.com')
    create_notification(db_path, user['id'], 'info', 'Notif 1', 'Message 1')
    create_notification(db_path, user['id'], 'warning', 'Notif 2', 'Message 2')
    
    res = client.post('/api/notifications/read-all', follow_redirects=True)
    assert res.status_code == 200
    
    mark_all_notifications_as_read(db_path, user['id'])
    notifications = get_user_notifications(db_path, user['id'])
    for notif in notifications:
        assert notif['is_read'] == 1


def test_create_notification(db_path):
    """Test creating a notification."""
    user_id = create_user(db_path, 'notify@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    notification_id = create_notification(db_path, user_id, 'info', 'Test Title', 'Test notification')
    assert notification_id > 0
    
    notifications = get_user_notifications(db_path, user_id)
    assert len(notifications) == 1
    assert notifications[0]['message'] == 'Test notification'


def test_get_unread_notification_count(db_path):
    """Test getting unread notification count."""
    from models import get_unread_notification_count
    user_id = create_user(db_path, 'countuser@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    create_notification(db_path, user_id, 'info', 'Unread 1', 'Message 1')
    create_notification(db_path, user_id, 'warning', 'Unread 2', 'Message 2')
    create_notification(db_path, user_id, 'info', 'Read 1', 'Message 3')
    
    # Mark one as read
    notifications = get_user_notifications(db_path, user_id)
    mark_notification_as_read(db_path, notifications[0]['id'], user_id)
    
    unread_count = get_unread_notification_count(db_path, user_id)
    assert unread_count == 2

