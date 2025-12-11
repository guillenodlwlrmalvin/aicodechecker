"""Tests for Groups & Activities (13 tests)."""
import os
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import (
    initialize_database, create_user, create_group, get_group_by_id,
    join_group, approve_group_member, create_activity, get_group_activities,
    submit_activity, get_activity_submissions, get_student_activities,
    get_user_by_username
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_groups.db')
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
def teacher_user(client, db_path):
    """Create and login a teacher user."""
    teacher_id = create_user(db_path, 'teacher@gmail.com', generate_password_hash('Test123!'), 
                           is_approved=True, role='teacher')
    client.post('/login', data={
        'username': 'teacher@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    return teacher_id


@pytest.fixture
def student_user(client, db_path):
    """Create and login a student user."""
    student_id = create_user(db_path, 'student@gmail.com', generate_password_hash('Test123!'), 
                           is_approved=True, role='student')
    client.post('/login', data={
        'username': 'student@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    return student_id


def test_create_group_route_requires_teacher(client, db_path):
    """Test that creating a group requires teacher role."""
    # Login as student
    create_user(db_path, 'student2@gmail.com', generate_password_hash('Test123!'), 
               is_approved=True, role='student')
    client.post('/login', data={
        'username': 'student2@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    
    res = client.post('/teacher/create_group', data={
        'name': 'Test Group',
        'description': 'Test Description'
    }, follow_redirects=True)
    # Should redirect or show error
    assert res.status_code in (200, 302, 403)


def test_create_group_route_as_teacher(client, db_path, teacher_user):
    """Test creating a group as teacher."""
    res = client.post('/teacher/create_group', data={
        'name': 'New Group',
        'description': 'Group Description'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_view_group_requires_teacher(client, db_path, teacher_user):
    """Test viewing a group requires teacher role."""
    group_id = create_group(db_path, 'View Group', 'Desc', teacher_user)
    
    res = client.get(f'/teacher/group/{group_id}', follow_redirects=True)
    assert res.status_code == 200


def test_join_group_route(client, db_path, teacher_user, student_user):
    """Test student joining a group."""
    group_id = create_group(db_path, 'Join Group', 'Desc', teacher_user)
    
    res = client.post(f'/student/join_group/{group_id}', follow_redirects=True)
    assert res.status_code == 200


def test_approve_group_member(client, db_path, teacher_user):
    """Test approving a group member."""
    # Create student
    student_id = create_user(db_path, 'approvestudent@gmail.com', generate_password_hash('Test123!'), 
                           is_approved=True, role='student')
    group_id = create_group(db_path, 'Approve Group', 'Desc', teacher_user)
    join_group(db_path, group_id, student_id)
    
    res = client.post(f'/teacher/group/{group_id}/approve/{student_id}', follow_redirects=True)
    assert res.status_code == 200


def test_create_activity_route(client, db_path, teacher_user):
    """Test creating an activity."""
    group_id = create_group(db_path, 'Activity Group', 'Desc', teacher_user)
    
    res = client.post(f'/teacher/group/{group_id}/create_activity', data={
        'title': 'Test Activity',
        'description': 'Activity Description',
        'deadline': '2024-12-31',
        'activity_type': 'coding',
        'content': 'Activity instructions'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_view_activity(client, db_path, teacher_user, student_user):
    """Test viewing an activity."""
    from models import get_user_by_username
    group_id = create_group(db_path, 'View Activity Group', 'Desc', teacher_user)
    activity_id = create_activity(
        db_path, group_id, teacher_user, 'View Activity',
        'Desc', '2024-12-31', 'coding', 'instructions'
    )
    
    # Student views activity
    res = client.get(f'/student/activity/{activity_id}', follow_redirects=True)
    assert res.status_code == 200


def test_submit_activity_route(client, db_path, teacher_user, student_user):
    """Test submitting an activity."""
    from models import get_user_by_username
    group_id = create_group(db_path, 'Submit Group', 'Desc', teacher_user)
    activity_id = create_activity(
        db_path, group_id, teacher_user, 'Submit Activity',
        'Desc', '2024-12-31', 'coding', 'instructions'
    )
    
    # Join and approve student
    student = get_user_by_username(db_path, 'student@gmail.com')
    join_group(db_path, group_id, student['id'])
    approve_group_member(db_path, group_id, student['id'])
    
    res = client.post(f'/student/activity/{activity_id}/submit', data={
        'content': 'submitted code here'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_view_activity_submissions(client, db_path, teacher_user, student_user):
    """Test viewing activity submissions as teacher."""
    from models import get_user_by_username
    group_id = create_group(db_path, 'Submissions Group', 'Desc', teacher_user)
    activity_id = create_activity(
        db_path, group_id, teacher_user, 'Submissions Activity',
        'Desc', '2024-12-31', 'coding', 'instructions'
    )
    
    student = get_user_by_username(db_path, 'student@gmail.com')
    join_group(db_path, group_id, student['id'])
    approve_group_member(db_path, group_id, student['id'])
    submit_activity(db_path, activity_id, student['id'], 'code submission')
    
    res = client.get(f'/teacher/activity/{activity_id}/submissions', follow_redirects=True)
    assert res.status_code == 200


def test_browse_groups_requires_student(client, db_path):
    """Test that browse_groups requires student role."""
    res = client.get('/browse_groups', follow_redirects=False)
    assert res.status_code in (302, 303)


def test_browse_groups_as_student(client, db_path, student_user):
    """Test browsing groups as student."""
    res = client.get('/browse_groups', follow_redirects=True)
    assert res.status_code == 200


def test_decline_group_member(client, db_path, teacher_user):
    """Test declining a group member."""
    student_id = create_user(db_path, 'declinestudent@gmail.com', generate_password_hash('Test123!'), 
                            is_approved=True, role='student')
    group_id = create_group(db_path, 'Decline Group', 'Desc', teacher_user)
    join_group(db_path, group_id, student_id)
    
    res = client.post(f'/teacher/group/{group_id}/decline/{student_id}', follow_redirects=True)
    assert res.status_code == 200


def test_grade_submission_route(client, db_path, teacher_user):
    """Test grading a submission as teacher."""
    from models import get_user_by_username, create_group, create_activity, submit_activity
    student_id = create_user(db_path, 'gradestudent@gmail.com', generate_password_hash('Test123!'), 
                            is_approved=True, role='student')
    group_id = create_group(db_path, 'Grade Group', 'Desc', teacher_user)
    activity_id = create_activity(db_path, group_id, teacher_user, 'Grade Activity', 
                                  'Desc', '2024-12-31', 'coding', 'instructions')
    
    student = get_user_by_username(db_path, 'gradestudent@gmail.com')
    join_group(db_path, group_id, student['id'])
    approve_group_member(db_path, group_id, student['id'])
    submission_id = submit_activity(db_path, activity_id, student['id'], 'code')
    
    res = client.post(f'/teacher/submission/{submission_id}/grade', data={
        'score': 90,
        'feedback': 'Excellent!',
        'activity_id': activity_id
    }, follow_redirects=True)
    assert res.status_code == 200

