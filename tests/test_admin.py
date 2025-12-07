import os
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import (
    initialize_database, create_user, get_user_by_username, list_all_users, approve_user,
    delete_user_and_related, get_user_by_id, update_user_role, mark_user_verified
)


@pytest.fixture()
def admin_client(monkeypatch, tmp_path):
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    initialize_database(db_path)
    
    admin_id = create_user(db_path, 'admin@gmail.com', generate_password_hash('Admin123!'),
                          is_admin=True, is_approved=True)
    mark_user_verified(db_path, admin_id)
    
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'admin@gmail.com'
        yield c


def test_admin_dashboard_loads(admin_client):
    """Test that admin dashboard loads."""
    res = admin_client.get('/admin')
    assert res.status_code == 200
    assert b'admin' in res.data.lower() or b'user' in res.data.lower()


def test_admin_approve_user(admin_client):
    """Test approving a user."""
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'pending@gmail.com', generate_password_hash('Test123!'),
                          is_approved=False)
    
    res = admin_client.post(f'/admin/approve_user/{user_id}', follow_redirects=True)
    assert res.status_code == 200
    
    user = get_user_by_id(db_path, user_id)
    assert user.get('is_approved') == 1


def test_admin_delete_user(admin_client):
    """Test deleting a user."""
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'delete@gmail.com', generate_password_hash('Test123!'),
                          is_approved=True)
    
    res = admin_client.post(f'/admin/delete_user/{user_id}', follow_redirects=True)
    assert res.status_code == 200
    
    user = get_user_by_id(db_path, user_id)
    assert user is None


def test_admin_change_password(admin_client):
    """Test admin changing user password."""
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'changepass@gmail.com', generate_password_hash('Old123!'),
                          is_approved=True)
    
    res = admin_client.post(f'/admin/change_password/{user_id}', data={
        'new_password': 'NewPass123!',
        'confirm_password': 'NewPass123!'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_admin_change_role(admin_client):
    """Test admin changing user role."""
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'changerole@gmail.com', generate_password_hash('Test123!'),
                          is_approved=True, role='student')
    
    res = admin_client.post(f'/admin/change_role/{user_id}', data={
        'new_role': 'teacher'
    }, follow_redirects=True)
    assert res.status_code == 200
    
    user = get_user_by_id(db_path, user_id)
    assert user.get('role') == 'teacher'


def test_admin_create_group(admin_client):
    """Test admin creating a group."""
    res = admin_client.post('/admin/create_group', data={
        'name': 'Admin Group',
        'description': 'Admin Description'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_admin_delete_group(admin_client):
    """Test admin deleting a group."""
    from models import create_group, get_user_by_username
    db_path = flask_app.config['DATABASE']
    admin = get_user_by_username(db_path, 'admin@gmail.com')
    group_id = create_group(db_path, 'Delete Group', 'Description', admin['id'])
    
    res = admin_client.post(f'/admin/group/{group_id}/delete', follow_redirects=True)
    assert res.status_code == 200


def test_admin_list_users(admin_client):
    """Test that admin can view all users."""
    db_path = flask_app.config['DATABASE']
    create_user(db_path, 'user1@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    create_user(db_path, 'user2@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    
    users = list_all_users(db_path)
    assert len(users) >= 3  # admin + 2 new users


def test_admin_grade_submission(admin_client):
    """Test admin grading a submission."""
    from models import (create_user, create_group, create_activity, submit_activity,
                       grade_submission, get_activity_submissions, mark_user_verified)
    db_path = flask_app.config['DATABASE']
    admin = get_user_by_username(db_path, 'admin@gmail.com')
    student_id = create_user(db_path, 'gradestudent@gmail.com', generate_password_hash('Test123!'),
                            is_approved=True, role='student')
    mark_user_verified(db_path, student_id)
    group_id = create_group(db_path, 'Grade Group', 'Description', admin['id'])
    activity_id = create_activity(db_path, group_id, admin['id'], 'Grade Activity',
                                  'Description', 'print(1)', 'code')
    submission_id = submit_activity(db_path, activity_id, student_id, content='print("done")')
    
    grade_submission(db_path, submission_id, 85.0, 'Good work!')
    # Verify grade was set
    submissions = get_activity_submissions(db_path, activity_id)
    graded = next((s for s in submissions if s['id'] == submission_id), None)
    assert graded is not None
    assert graded['grade'] == 85.0

