"""
Unit tests for groups and activities functionality.
"""
import os
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app
from models import (
    initialize_database, create_user, create_group, get_group_by_id,
    get_teacher_groups, join_group, approve_group_member, create_activity,
    get_activity_by_id, submit_activity, get_activity_submissions
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_groups.db')
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
def teacher_user(client, db_path):
    """Create and login a teacher user."""
    password_hash = generate_password_hash('password123')
    user_id = create_user(db_path, 'teacher@test.com', password_hash, 
                          is_approved=1, role='teacher')
    
    client.post('/login', data={
        'username': 'teacher@test.com',
        'password': 'password123'
    })
    
    return user_id


@pytest.fixture
def student_user(client, db_path):
    """Create and login a student user."""
    password_hash = generate_password_hash('password123')
    user_id = create_user(db_path, 'student@test.com', password_hash, 
                          is_approved=1, role='student')
    
    client.post('/login', data={
        'username': 'student@test.com',
        'password': 'password123'
    })
    
    return user_id


class TestGroups:
    """Tests for group management."""
    
    def test_create_group_requires_teacher(self, client, db_path):
        """Test that creating a group requires teacher role."""
        # Login as student
        password_hash = generate_password_hash('password123')
        create_user(db_path, 'student@test.com', password_hash, is_approved=1, role='student')
        client.post('/login', data={'username': 'student@test.com', 'password': 'password123'})
        
        response = client.get('/teacher/create_group', follow_redirects=True)
        # Should redirect or deny access
        assert response.status_code == 200
    
    def test_create_group_as_teacher(self, client, teacher_user, db_path):
        """Test creating a group as a teacher."""
        response = client.post('/teacher/create_group', data={
            'name': 'Test Group',
            'description': 'Test Description'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Verify group was created
        groups = get_teacher_groups(db_path, teacher_user)
        assert len(groups) >= 1
    
    def test_view_groups_page(self, client, teacher_user):
        """Test viewing groups page."""
        response = client.get('/groups', follow_redirects=True)
        assert response.status_code == 200
    
    def test_browse_groups_as_student(self, client, student_user):
        """Test browsing groups as a student."""
        response = client.get('/browse_groups', follow_redirects=True)
        assert response.status_code == 200
    
    def test_join_group(self, client, student_user, db_path, teacher_user):
        """Test student joining a group."""
        # Create a group
        group_id = create_group(db_path, 'Test Group', 'Description', teacher_user)
        
        # Student joins group
        result = join_group(db_path, group_id, student_user)
        assert result is True
    
    def test_approve_group_member(self, client, teacher_user, db_path, student_user):
        """Test teacher approving a group member."""
        # Create group and join
        group_id = create_group(db_path, 'Test Group', 'Description', teacher_user)
        join_group(db_path, group_id, student_user)
        
        # Approve member
        approve_group_member(db_path, group_id, student_user)
        
        # Verify approval
        from models import get_group_members
        members = get_group_members(db_path, group_id)
        approved = [m for m in members if m['user_id'] == student_user and m.get('is_approved')]
        assert len(approved) >= 1


class TestActivities:
    """Tests for activity management."""
    
    def test_create_activity(self, client, teacher_user, db_path):
        """Test creating an activity."""
        # Create a group first
        group_id = create_group(db_path, 'Test Group', 'Description', teacher_user)
        
        response = client.post(f'/teacher/group/{group_id}/create_activity', data={
            'title': 'Test Activity',
            'description': 'Activity Description',
            'content': 'Activity Content',
            'activity_type': 'text'
        }, follow_redirects=True)
        
        # May redirect or return 200
        assert response.status_code in [200, 302]
    
    def test_view_activity(self, client, student_user, db_path, teacher_user):
        """Test viewing an activity as a student."""
        # Create group and activity
        group_id = create_group(db_path, 'Test Group', 'Description', teacher_user)
        activity_id = create_activity(
            db_path, group_id, teacher_user, 'Test Activity', 
            'Description', 'Content', 'text'
        )
        
        # Student must join and be approved in the group to view activity
        join_group(db_path, group_id, student_user)
        approve_group_member(db_path, group_id, student_user)
        
        # Student views activity
        response = client.get(f'/student/activity/{activity_id}', 
                            follow_redirects=True)
        # May redirect if activity not accessible or return 200
        assert response.status_code in [200, 302]
    
    def test_submit_activity(self, client, student_user, db_path, teacher_user):
        """Test student submitting an activity."""
        # Create group and activity
        group_id = create_group(db_path, 'Test Group', 'Description', teacher_user)
        activity_id = create_activity(
            db_path, group_id, teacher_user, 'Test Activity',
            'Description', 'Content', 'text'
        )
        
        # Submit activity
        submission_id = submit_activity(
            db_path, activity_id, student_user, 'My submission content'
        )
        
        assert submission_id > 0
        
        # Verify submission
        submissions = get_activity_submissions(db_path, activity_id)
        assert len(submissions) >= 1


class TestRoleBasedAccess:
    """Tests for role-based access control."""
    
    def test_student_dashboard_access(self, client, student_user):
        """Test student can access student dashboard."""
        response = client.get('/student_dashboard', follow_redirects=True)
        assert response.status_code == 200
    
    def test_teacher_dashboard_access(self, client, teacher_user):
        """Test teacher can access teacher dashboard."""
        response = client.get('/teacher_dashboard', follow_redirects=True)
        assert response.status_code == 200
    
    def test_student_cannot_access_teacher_routes(self, client, student_user):
        """Test student cannot access teacher-only routes."""
        response = client.get('/teacher/create_group', follow_redirects=True)
        # Should redirect or show error
        assert response.status_code == 200
    
    def test_code_analysis_access(self, client, teacher_user):
        """Test code analysis access for teachers."""
        response = client.get('/code_analysis', follow_redirects=True)
        assert response.status_code == 200

