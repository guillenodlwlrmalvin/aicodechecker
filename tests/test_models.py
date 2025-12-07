import os
import tempfile
import pytest
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

from models import (
    initialize_database, create_user, get_user_by_username, get_user_by_id,
    get_user_count, get_user_by_google_id, create_uploaded_file, get_uploaded_files,
    get_uploaded_file, create_analysis, get_recent_analyses, get_analysis_by_id,
    list_all_users, delete_user_and_related, approve_user, update_user_role,
    set_user_verification_token, get_user_by_verification_code, mark_user_verified,
    update_user_password, create_group, get_group_by_id, get_group_members,
    join_group, approve_group_member, create_activity, get_activity_by_id,
    submit_activity, get_activity_submissions, grade_submission,
    create_notification, get_user_notifications, get_unread_notification_count,
    mark_notification_as_read
)


def test_models_crud_flow(tmp_path):
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)

    # user
    uid = create_user(db_path, 'alice', 'hash', is_admin=True, is_approved=True)
    assert uid > 0
    assert get_user_count(db_path) == 1
    user = get_user_by_username(db_path, 'alice')
    assert user and user['username'] == 'alice'

    # file
    fid = create_uploaded_file(db_path, uid, 'code.py', 'code.py', 5, 'py', 'print(1)')
    assert fid > 0
    files = get_uploaded_files(db_path, uid)
    assert len(files) == 1

    # analysis
    aid = create_analysis(db_path, uid, 'print(1)', 'python', 'Human', 20.0, True, [], file_id=fid)
    assert aid > 0
    hist = get_recent_analyses(db_path, uid)
    assert len(hist) == 1
    assert hist[0]['file_id'] == fid


def test_create_user_with_roles(tmp_path):
    """Test creating users with different roles."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    student_id = create_user(db_path, 'student@test.com', 'hash', role='student')
    teacher_id = create_user(db_path, 'teacher@test.com', 'hash', role='teacher')
    admin_id = create_user(db_path, 'admin@test.com', 'hash', is_admin=True, role='admin')
    
    student = get_user_by_id(db_path, student_id)
    teacher = get_user_by_id(db_path, teacher_id)
    admin = get_user_by_id(db_path, admin_id)
    
    assert student['role'] == 'student'
    assert teacher['role'] == 'teacher'
    assert admin['role'] == 'admin' or admin.get('is_admin') == 1


def test_get_user_by_id(tmp_path):
    """Test retrieving user by ID."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'byid@test.com', 'hash', is_approved=True)
    user = get_user_by_id(db_path, user_id)
    
    assert user is not None
    assert user['id'] == user_id
    assert user['username'] == 'byid@test.com'


def test_get_user_by_google_id(tmp_path):
    """Test retrieving user by Google ID."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    from models import upsert_user_from_google
    user_dict, _ = upsert_user_from_google(db_path, 'google123', 'google@test.com', 'Google User')
    
    user = get_user_by_google_id(db_path, 'google123')
    assert user is not None
    assert user['google_id'] == 'google123'
    assert user['username'] == 'google@test.com'


def test_user_verification_token(tmp_path):
    """Test setting and retrieving verification tokens."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'verify@test.com', 'hash', is_approved=False)
    code = '123456'
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    
    set_user_verification_token(db_path, user_id, code, expires_at)
    user = get_user_by_verification_code(db_path, code)
    
    assert user is not None
    assert user['id'] == user_id


def test_mark_user_verified(tmp_path):
    """Test marking user as verified."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'unverified@test.com', 'hash', is_approved=False)
    mark_user_verified(db_path, user_id)
    
    user = get_user_by_id(db_path, user_id)
    assert user.get('is_approved') == 1


def test_update_user_password(tmp_path):
    """Test updating user password."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'passuser@test.com', generate_password_hash('Old123!'))
    new_hash = generate_password_hash('New123!')
    update_user_password(db_path, user_id, new_hash)
    
    user = get_user_by_id(db_path, user_id)
    assert user['password_hash'] == new_hash


def test_create_and_get_group(tmp_path):
    """Test creating and retrieving groups."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    teacher_id = create_user(db_path, 'groupteacher@test.com', 'hash', role='teacher')
    group_id = create_group(db_path, 'Test Group', 'Description', teacher_id)
    
    group = get_group_by_id(db_path, group_id)
    assert group is not None
    assert group['name'] == 'Test Group'
    assert group['teacher_id'] == teacher_id


def test_join_and_approve_group_member(tmp_path):
    """Test joining and approving group members."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    teacher_id = create_user(db_path, 'teacher@test.com', 'hash', role='teacher')
    student_id = create_user(db_path, 'student@test.com', 'hash', role='student')
    group_id = create_group(db_path, 'Join Group', 'Description', teacher_id)
    
    joined = join_group(db_path, group_id, student_id)
    assert joined is True
    
    members = get_group_members(db_path, group_id)
    assert len(members) == 1
    assert members[0]['status'] == 'pending'
    
    approve_group_member(db_path, group_id, student_id)
    members = get_group_members(db_path, group_id)
    assert members[0]['status'] == 'approved'


def test_create_and_get_activity(tmp_path):
    """Test creating and retrieving activities."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    teacher_id = create_user(db_path, 'activityteacher@test.com', 'hash', role='teacher')
    group_id = create_group(db_path, 'Activity Group', 'Description', teacher_id)
    activity_id = create_activity(db_path, group_id, teacher_id, 'Test Activity',
                                 'Description', 'print(1)', 'code')
    
    activity = get_activity_by_id(db_path, activity_id)
    assert activity is not None
    assert activity['title'] == 'Test Activity'
    assert activity['group_id'] == group_id


def test_submit_and_grade_activity(tmp_path):
    """Test submitting and grading activities."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    teacher_id = create_user(db_path, 'gradeteacher@test.com', 'hash', role='teacher')
    student_id = create_user(db_path, 'gradestudent@test.com', 'hash', role='student')
    group_id = create_group(db_path, 'Grade Group', 'Description', teacher_id)
    activity_id = create_activity(db_path, group_id, teacher_id, 'Grade Activity',
                                'Description', 'print(1)', 'code')
    
    submission_id = submit_activity(db_path, activity_id, student_id, content='print("submitted")')
    assert submission_id > 0
    
    submissions = get_activity_submissions(db_path, activity_id)
    assert len(submissions) == 1
    
    grade_submission(db_path, submission_id, 95.0, 'Great work!')
    submissions = get_activity_submissions(db_path, activity_id)
    assert submissions[0]['grade'] == 95.0


def test_create_and_get_notifications(tmp_path):
    """Test creating and retrieving notifications."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'notify@test.com', 'hash')
    notif_id = create_notification(db_path, user_id, 'info', 'Test Title', 'Test Message')
    assert notif_id > 0
    
    notifications = get_user_notifications(db_path, user_id)
    assert len(notifications) > 0
    assert notifications[0]['title'] == 'Test Title'


def test_mark_notification_as_read(tmp_path):
    """Test marking notification as read."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'readnotify@test.com', 'hash')
    notif_id = create_notification(db_path, user_id, 'info', 'Unread', 'Message')
    
    count_before = get_unread_notification_count(db_path, user_id)
    assert count_before >= 1
    
    mark_notification_as_read(db_path, notif_id, user_id)
    count_after = get_unread_notification_count(db_path, user_id)
    assert count_after < count_before


def test_delete_user_and_related(tmp_path):
    """Test deleting user and related data."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'delete@test.com', 'hash')
    create_uploaded_file(db_path, user_id, 'file.py', 'file.py', 100, 'py', 'print(1)')
    create_analysis(db_path, user_id, 'print(1)', 'python', 'Human', 20.0, True, [])
    
    delete_user_and_related(db_path, user_id)
    user = get_user_by_id(db_path, user_id)
    assert user is None


def test_approve_user(tmp_path):
    """Test approving a user."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'approve@test.com', 'hash', is_approved=False)
    approve_user(db_path, user_id)
    
    user = get_user_by_id(db_path, user_id)
    assert user.get('is_approved') == 1


def test_update_user_role(tmp_path):
    """Test updating user role."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'rolechange@test.com', 'hash', role='student')
    update_user_role(db_path, user_id, 'teacher')
    
    user = get_user_by_id(db_path, user_id)
    assert user['role'] == 'teacher'


def test_list_all_users(tmp_path):
    """Test listing all users."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    create_user(db_path, 'user1@test.com', 'hash')
    create_user(db_path, 'user2@test.com', 'hash')
    create_user(db_path, 'user3@test.com', 'hash')
    
    users = list_all_users(db_path)
    assert len(users) >= 3


def test_get_recent_analyses_limit(tmp_path):
    """Test that get_recent_analyses respects limit."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'analyses@test.com', 'hash')
    # Create more than 10 analyses
    for i in range(15):
        create_analysis(db_path, user_id, f'print({i})', 'python', 'Human', 20.0, True, [])
    
    analyses = get_recent_analyses(db_path, user_id, limit=10)
    assert len(analyses) == 10


def test_get_uploaded_files_limit(tmp_path):
    """Test that get_uploaded_files respects limit."""
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)
    
    user_id = create_user(db_path, 'files@test.com', 'hash')
    # Create more than 20 files
    for i in range(25):
        create_uploaded_file(db_path, user_id, f'file{i}.py', f'file{i}.py', 100, 'py', f'print({i})')
    
    files = get_uploaded_files(db_path, user_id, limit=20)
    assert len(files) == 20


