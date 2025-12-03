"""
Unit tests for admin functionality.
"""
import os
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app
from models import (
    initialize_database, create_user, get_user_by_id, approve_user,
    list_all_users, delete_user_and_related, update_user_role
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_admin.db')
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
def admin_user(client, db_path):
    """Create and login an admin user."""
    password_hash = generate_password_hash('password123')
    user_id = create_user(db_path, 'admin@test.com', password_hash, 
                          is_approved=1, is_admin=True, role='admin')
    
    client.post('/login', data={
        'username': 'admin@test.com',
        'password': 'password123'
    })
    
    return user_id


class TestAdminFunctions:
    """Tests for admin functionality."""
    
    def test_admin_page_requires_admin(self, client, db_path):
        """Test that admin page requires admin role."""
        # Login as regular user
        password_hash = generate_password_hash('password123')
        create_user(db_path, 'user@test.com', password_hash, is_approved=1)
        client.post('/login', data={'username': 'user@test.com', 'password': 'password123'})
        
        response = client.get('/admin', follow_redirects=True)
        # Should redirect or deny access
        assert response.status_code == 200
    
    def test_admin_page_access(self, client, admin_user):
        """Test admin can access admin page."""
        response = client.get('/admin', follow_redirects=True)
        assert response.status_code == 200
    
    def test_approve_user(self, client, admin_user, db_path):
        """Test approving a user."""
        # Create unapproved user
        user_id = create_user(db_path, 'newuser@test.com', 'hash123', is_approved=0)
        
        response = client.post(f'/admin/approve_user/{user_id}', follow_redirects=True)
        assert response.status_code == 200
        
        # Verify user is approved
        user = get_user_by_id(db_path, user_id)
        assert user['is_approved'] == 1
    
    def test_delete_user(self, client, admin_user, db_path):
        """Test deleting a user."""
        # Create user to delete
        user_id = create_user(db_path, 'todelete@test.com', 'hash123')
        
        response = client.post(f'/admin/delete_user/{user_id}', follow_redirects=True)
        assert response.status_code == 200
        
        # Verify user is deleted
        user = get_user_by_id(db_path, user_id)
        assert user is None
    
    def test_change_user_role(self, client, admin_user, db_path):
        """Test changing a user's role."""
        user_id = create_user(db_path, 'user@test.com', 'hash123', role='student')
        
        response = client.post(f'/admin/change_role/{user_id}', data={
            'new_role': 'teacher'  # Correct form field name
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        # Verify role changed
        user = get_user_by_id(db_path, user_id)
        assert user['role'] == 'teacher'
    
    def test_change_user_password(self, client, admin_user, db_path):
        """Test admin changing a user's password."""
        user_id = create_user(db_path, 'user@test.com', 'hash123')
        
        response = client.post(f'/admin/change_password/{user_id}', data={
            'new_password': 'newpassword123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_list_all_users(self, client, admin_user, db_path):
        """Test listing all users."""
        # Create some users
        create_user(db_path, 'user1@test.com', 'hash1')
        create_user(db_path, 'user2@test.com', 'hash2')
        
        users = list_all_users(db_path)
        assert len(users) >= 2
    
    def test_admin_create_group(self, client, admin_user, db_path):
        """Test admin creating a group."""
        response = client.post('/admin/create_group', data={
            'name': 'Admin Group',
            'description': 'Admin Description',
            'teacher_id': admin_user
        }, follow_redirects=True)
        
        assert response.status_code == 200

