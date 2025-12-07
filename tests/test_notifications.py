import os
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import (
    initialize_database, create_user, get_user_by_username, create_notification,
    get_user_notifications, get_unread_notification_count, mark_notification_as_read,
    mark_all_notifications_as_read, mark_user_verified
)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'notifyuser@gmail.com', generate_password_hash('Test123!'),
                          is_approved=True)
    mark_user_verified(db_path, user_id)
    
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'notifyuser@gmail.com'
        yield c


def test_get_notifications(client):
    """Test getting user notifications."""
    db_path = flask_app.config['DATABASE']
    user = get_user_by_username(db_path, 'notifyuser@gmail.com')
    create_notification(db_path, user['id'], 'Test Notification', 'This is a test', 'info')
    
    res = client.get('/api/notifications')
    assert res.status_code == 200
    data = res.get_json()
    assert data is not None
    assert len(data) > 0 or 'notifications' in str(data).lower()


def test_get_unread_count(client):
    """Test getting unread notification count."""
    db_path = flask_app.config['DATABASE']
    user = get_user_by_username(db_path, 'notifyuser@gmail.com')
    create_notification(db_path, user['id'], 'Unread 1', 'Message 1', 'info')
    create_notification(db_path, user['id'], 'Unread 2', 'Message 2', 'info')
    
    count = get_unread_notification_count(db_path, user['id'])
    assert count >= 2


def test_mark_notification_as_read(client):
    """Test marking a notification as read."""
    db_path = flask_app.config['DATABASE']
    user = get_user_by_username(db_path, 'notifyuser@gmail.com')
    notif_id = create_notification(db_path, user['id'], 'Read Test', 'Message', 'info')
    
    res = client.post(f'/api/notifications/{notif_id}/read', follow_redirects=True)
    assert res.status_code == 200
    
    notifications = get_user_notifications(db_path, user['id'])
    read_notif = next((n for n in notifications if n['id'] == notif_id), None)
    assert read_notif is not None
    assert read_notif.get('is_read') == 1


def test_mark_all_notifications_as_read(client):
    """Test marking all notifications as read."""
    db_path = flask_app.config['DATABASE']
    user = get_user_by_username(db_path, 'notifyuser@gmail.com')
    create_notification(db_path, user['id'], 'Unread 1', 'Message 1', 'info')
    create_notification(db_path, user['id'], 'Unread 2', 'Message 2', 'info')
    
    res = client.post('/api/notifications/read-all', follow_redirects=True)
    assert res.status_code == 200
    
    count = get_unread_notification_count(db_path, user['id'])
    assert count == 0


def test_notification_types(client):
    """Test different notification types."""
    db_path = flask_app.config['DATABASE']
    user = get_user_by_username(db_path, 'notifyuser@gmail.com')
    
    create_notification(db_path, user['id'], 'Info', 'Info message', 'info')
    create_notification(db_path, user['id'], 'Warning', 'Warning message', 'warning')
    create_notification(db_path, user['id'], 'Success', 'Success message', 'success')
    create_notification(db_path, user['id'], 'Error', 'Error message', 'error')
    
    notifications = get_user_notifications(db_path, user['id'])
    assert len(notifications) >= 4


def test_check_deadlines_api(client):
    """Test checking deadlines API endpoint."""
    res = client.get('/api/notifications/check-deadlines', follow_redirects=True)
    # Should return JSON or redirect
    assert res.status_code in (200, 302, 401)

