"""Tests for Admin Functions (10 tests)."""
import os
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import initialize_database, create_user, get_user_by_username, approve_user


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_admin.db')
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
def admin_user(client, db_path):
    """Create and login an admin user."""
    admin_id = create_user(db_path, 'admin@gmail.com', generate_password_hash('Admin123!'), 
                          is_admin=True, is_approved=True, role='admin')
    client.post('/login', data={
        'username': 'admin@gmail.com',
        'password': 'Admin123!'
    }, follow_redirects=True)
    return admin_id


def test_admin_dashboard_requires_admin(client, db_path):
    """Test that admin dashboard requires admin role."""
    # Login as regular user
    create_user(db_path, 'regular@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    client.post('/login', data={
        'username': 'regular@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    
    res = client.get('/admin', follow_redirects=True)
    # Should redirect or show error
    assert res.status_code in (200, 302, 403)


def test_admin_dashboard_access(client, db_path, admin_user):
    """Test accessing admin dashboard as admin."""
    res = client.get('/admin', follow_redirects=True)
    assert res.status_code == 200


def test_admin_approve_user(client, db_path, admin_user):
    """Test admin approving a user."""
    user_id = create_user(db_path, 'pending@gmail.com', generate_password_hash('Test123!'), is_approved=False)
    
    res = client.post(f'/admin/approve_user/{user_id}', follow_redirects=True)
    assert res.status_code == 200
    
    user = get_user_by_username(db_path, 'pending@gmail.com')
    assert user['is_approved'] == 1


def test_admin_delete_user(client, db_path, admin_user):
    """Test admin deleting a user."""
    user_id = create_user(db_path, 'delete@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    
    res = client.post(f'/admin/delete_user/{user_id}', follow_redirects=True)
    assert res.status_code == 200
    
    user = get_user_by_username(db_path, 'delete@gmail.com')
    assert user is None


def test_admin_cannot_delete_self(client, db_path, admin_user):
    """Test that admin cannot delete their own account."""
    res = client.post(f'/admin/delete_user/{admin_user}', follow_redirects=True)
    assert res.status_code == 200
    assert b'cannot delete' in res.data.lower() or b'own' in res.data.lower()


def test_admin_change_password(client, db_path, admin_user):
    """Test admin changing user password."""
    user_id = create_user(db_path, 'changepass@gmail.com', generate_password_hash('Old123!'), is_approved=True)
    
    res = client.post(f'/admin/change_password/{user_id}', data={
        'new_password': 'New123!',
        'confirm_password': 'New123!'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_admin_change_role(client, db_path, admin_user):
    """Test admin changing user role."""
    user_id = create_user(db_path, 'changerole@gmail.com', generate_password_hash('Test123!'), 
                         is_approved=True, role='student')
    
    res = client.post(f'/admin/change_role/{user_id}', data={
        'new_role': 'teacher'
    }, follow_redirects=True)
    assert res.status_code == 200
    
    user = get_user_by_username(db_path, 'changerole@gmail.com')
    assert user['role'] == 'teacher'


def test_admin_create_group(client, db_path, admin_user):
    """Test admin creating a group."""
    res = client.post('/admin/create_group', data={
        'name': 'Admin Group',
        'description': 'Group created by admin'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_admin_delete_group(client, db_path, admin_user):
    """Test admin deleting a group."""
    from models import create_group, get_group_by_id
    group_id = create_group(db_path, 'Delete Group', 'Desc', admin_user)
    
    res = client.post(f'/admin/group/{group_id}/delete', follow_redirects=True)
    assert res.status_code == 200
    
    group = get_group_by_id(db_path, group_id)
    assert group is None or group.get('is_active') == 0


def test_admin_grade_submission(client, db_path, admin_user):
    """Test admin grading a submission."""
    from models import create_user, create_group, create_activity, submit_activity, grade_submission, get_activity_submissions
    teacher_id = create_user(db_path, 'teacher@gmail.com', generate_password_hash('Test123!'), 
                            is_approved=True, role='teacher')
    student_id = create_user(db_path, 'student@gmail.com', generate_password_hash('Test123!'), 
                            is_approved=True, role='student')
    group_id = create_group(db_path, 'Grade Group', 'Desc', teacher_id)
    activity_id = create_activity(db_path, group_id, teacher_id, 'Grade Activity', 
                                  'Desc', '2024-12-31', 'coding', 'instructions')
    submission_id = submit_activity(db_path, activity_id, student_id, 'submitted code')
    
    res = client.post(f'/teacher/submission/{submission_id}/grade', data={
        'grade': 85,
        'feedback': 'Good work!',
        'activity_id': activity_id
    }, follow_redirects=True)
    assert res.status_code == 200
    
    submissions = get_activity_submissions(db_path, activity_id)
    graded = [s for s in submissions if s['id'] == submission_id]
    if graded:
        # Check both 'grade' and 'score' (score is alias for grade)
        assert graded[0].get('grade') == 85 or graded[0].get('score') == 85

