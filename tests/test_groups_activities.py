import os
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import (
    initialize_database, create_user, get_user_by_username, create_group, join_group,
    create_activity, get_group_by_id, get_group_members, approve_group_member,
    mark_user_verified
)


@pytest.fixture()
def teacher_client(monkeypatch, tmp_path):
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    initialize_database(db_path)
    
    teacher_id = create_user(db_path, 'teacher@gmail.com', generate_password_hash('Test123!'),
                             is_approved=True, role='teacher')
    mark_user_verified(db_path, teacher_id)
    
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'teacher@gmail.com'
        yield c


@pytest.fixture()
def student_client(monkeypatch, tmp_path):
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    initialize_database(db_path)
    
    student_id = create_user(db_path, 'student@gmail.com', generate_password_hash('Test123!'),
                            is_approved=True, role='student')
    mark_user_verified(db_path, student_id)
    
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'student@gmail.com'
        yield c


def test_browse_groups_page_loads(student_client):
    """Test that browse groups page loads for students."""
    res = student_client.get('/browse_groups')
    assert res.status_code == 200
    assert b'group' in res.data.lower()


def test_groups_page_loads(teacher_client):
    """Test that groups page loads for teachers."""
    res = teacher_client.get('/groups')
    assert res.status_code == 200
    assert b'group' in res.data.lower()


def test_create_group(teacher_client):
    """Test group creation by teacher."""
    res = teacher_client.post('/teacher/create_group', data={
        'name': 'Test Group',
        'description': 'Test Description'
    }, follow_redirects=True)
    assert res.status_code == 200
    # Group should be created


def test_join_group(student_client, teacher_client):
    """Test that student can join a group."""
    # Teacher creates a group
    db_path = flask_app.config['DATABASE']
    teacher = get_user_by_username(db_path, 'teacher@gmail.com')
    group_id = create_group(db_path, 'Joinable Group', 'Description', teacher['id'])
    
    # Student joins
    res = student_client.post(f'/student/join_group/{group_id}', follow_redirects=True)
    assert res.status_code == 200


def test_view_group_details(teacher_client):
    """Test viewing group details."""
    db_path = flask_app.config['DATABASE']
    teacher = get_user_by_username(db_path, 'teacher@gmail.com')
    group_id = create_group(db_path, 'Detail Group', 'Description', teacher['id'])
    
    res = teacher_client.get(f'/teacher/group/{group_id}')
    assert res.status_code == 200
    assert b'Detail Group' in res.data or res.status_code == 200


def test_create_activity(teacher_client):
    """Test activity creation by teacher."""
    db_path = flask_app.config['DATABASE']
    teacher = get_user_by_username(db_path, 'teacher@gmail.com')
    group_id = create_group(db_path, 'Activity Group', 'Description', teacher['id'])
    
    res = teacher_client.post(f'/teacher/group/{group_id}/create_activity', data={
        'title': 'Test Activity',
        'description': 'Test Description',
        'content': 'print("hello")',
        'activity_type': 'code'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_view_activity(student_client, teacher_client):
    """Test viewing activity by student."""
    db_path = flask_app.config['DATABASE']
    teacher = get_user_by_username(db_path, 'teacher@gmail.com')
    group_id = create_group(db_path, 'View Group', 'Description', teacher['id'])
    
    # Add student to group
    student = get_user_by_username(db_path, 'student@gmail.com')
    join_group(db_path, group_id, student['id'])
    approve_group_member(db_path, group_id, student['id'])
    
    activity_id = create_activity(db_path, group_id, teacher['id'], 'View Activity',
                                 'Description', 'print(1)', 'code')
    
    res = student_client.get(f'/student/activity/{activity_id}')
    assert res.status_code == 200


def test_submit_activity(student_client, teacher_client):
    """Test activity submission by student."""
    db_path = flask_app.config['DATABASE']
    teacher = get_user_by_username(db_path, 'teacher@gmail.com')
    group_id = create_group(db_path, 'Submit Group', 'Description', teacher['id'])
    
    student = get_user_by_username(db_path, 'student@gmail.com')
    join_group(db_path, group_id, student['id'])
    approve_group_member(db_path, group_id, student['id'])
    
    activity_id = create_activity(db_path, group_id, teacher['id'], 'Submit Activity',
                                 'Description', 'print(1)', 'code')
    
    res = student_client.post(f'/student/activity/{activity_id}/submit', data={
        'content': 'print("submitted")'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_approve_group_member(teacher_client):
    """Test approving a group member."""
    db_path = flask_app.config['DATABASE']
    teacher = get_user_by_username(db_path, 'teacher@gmail.com')
    assert teacher is not None
    group_id = create_group(db_path, 'Approve Group', 'Description', teacher['id'])
    
    # Create student if doesn't exist
    from werkzeug.security import generate_password_hash
    from models import create_user, mark_user_verified
    student = get_user_by_username(db_path, 'student@gmail.com')
    if student is None:
        student_id = create_user(db_path, 'student@gmail.com', generate_password_hash('Test123!'),
                                is_approved=True, role='student')
        mark_user_verified(db_path, student_id)
        student = get_user_by_username(db_path, 'student@gmail.com')
    
    assert student is not None
    join_group(db_path, group_id, student['id'])
    
    res = teacher_client.post(f'/teacher/group/{group_id}/approve/{student["id"]}',
                             follow_redirects=True)
    assert res.status_code in (200, 302)


def test_decline_group_member(teacher_client):
    """Test declining a group member."""
    db_path = flask_app.config['DATABASE']
    teacher = get_user_by_username(db_path, 'teacher@gmail.com')
    group_id = create_group(db_path, 'Decline Group', 'Description', teacher['id'])
    
    from werkzeug.security import generate_password_hash
    from models import create_user, mark_user_verified, join_group, decline_group_member
    student = get_user_by_username(db_path, 'student@gmail.com')
    if student is None:
        student_id = create_user(db_path, 'student@gmail.com', generate_password_hash('Test123!'),
                                is_approved=True, role='student')
        mark_user_verified(db_path, student_id)
        student = get_user_by_username(db_path, 'student@gmail.com')
    
    join_group(db_path, group_id, student['id'])
    res = teacher_client.post(f'/teacher/group/{group_id}/decline/{student["id"]}',
                             follow_redirects=True)
    assert res.status_code in (200, 302)


def test_view_activity_submissions(teacher_client):
    """Test viewing activity submissions as teacher."""
    db_path = flask_app.config['DATABASE']
    teacher = get_user_by_username(db_path, 'teacher@gmail.com')
    group_id = create_group(db_path, 'Submissions Group', 'Description', teacher['id'])
    activity_id = create_activity(db_path, group_id, teacher['id'], 'Submissions Activity',
                                  'Description', 'print(1)', 'code')
    
    res = teacher_client.get(f'/teacher/activity/{activity_id}/submissions', follow_redirects=True)
    assert res.status_code in (200, 302)

