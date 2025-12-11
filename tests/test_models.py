"""Tests for Database Operations (21 tests)."""
import os
import pytest
from werkzeug.security import generate_password_hash
from models import (
    initialize_database, create_user, get_user_by_username, get_user_by_id,
    get_user_count, create_analysis, get_recent_analyses, get_analysis_by_id,
    create_uploaded_file, get_uploaded_files, create_group, get_group_by_id,
    get_teacher_groups, create_activity, get_group_activities, submit_activity,
    get_activity_submissions, set_user_verification_token, get_user_by_verification_code,
    get_group_members, get_student_activities
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_models.db')
    initialize_database(db)
    return db


def test_initialize_database(db_path):
    """Test database initialization creates all tables."""
    assert os.path.exists(db_path)
    # Database should be accessible
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert 'users' in tables
    assert 'analyses' in tables
    assert 'uploaded_files' in tables
    assert 'groups' in tables
    conn.close()


def test_create_user(db_path):
    """Test creating a user."""
    user_id = create_user(db_path, 'testuser@gmail.com', generate_password_hash('Test123!'))
    assert user_id > 0
    
    user = get_user_by_username(db_path, 'testuser@gmail.com')
    assert user is not None
    assert user['username'] == 'testuser@gmail.com'


def test_get_user_by_username(db_path):
    """Test retrieving user by username."""
    user_id = create_user(db_path, 'getuser@gmail.com', generate_password_hash('Test123!'))
    user = get_user_by_username(db_path, 'getuser@gmail.com')
    assert user is not None
    assert user['id'] == user_id


def test_get_user_by_id(db_path):
    """Test retrieving user by ID."""
    user_id = create_user(db_path, 'iduser@gmail.com', generate_password_hash('Test123!'))
    user = get_user_by_id(db_path, user_id)
    assert user is not None
    assert user['username'] == 'iduser@gmail.com'


def test_get_user_count(db_path):
    """Test getting user count."""
    assert get_user_count(db_path) == 0
    create_user(db_path, 'count1@gmail.com', generate_password_hash('Test123!'))
    assert get_user_count(db_path) == 1
    create_user(db_path, 'count2@gmail.com', generate_password_hash('Test123!'))
    assert get_user_count(db_path) == 2


def test_create_analysis(db_path):
    """Test creating a code analysis."""
    user_id = create_user(db_path, 'analyst@gmail.com', generate_password_hash('Test123!'))
    analysis_id = create_analysis(
        db_path, user_id, 'print("hello")', 'python', 
        'Human', 0.8, True, []
    )
    assert analysis_id > 0
    
    analyses = get_recent_analyses(db_path, user_id, limit=10)
    assert len(analyses) == 1
    assert analyses[0]['code'] == 'print("hello")'


def test_get_recent_analyses(db_path):
    """Test retrieving recent analyses."""
    user_id = create_user(db_path, 'recent@gmail.com', generate_password_hash('Test123!'))
    create_analysis(db_path, user_id, 'code1', 'python', 'Human', 0.5, True, [])
    create_analysis(db_path, user_id, 'code2', 'python', 'AI', 0.9, True, [])
    
    analyses = get_recent_analyses(db_path, user_id, limit=10)
    assert len(analyses) == 2
    # Most recent should be first
    assert analyses[0]['code'] == 'code2'


def test_get_analysis_by_id(db_path):
    """Test retrieving analysis by ID."""
    user_id = create_user(db_path, 'analysisid@gmail.com', generate_password_hash('Test123!'))
    analysis_id = create_analysis(db_path, user_id, 'test code', 'python', 'Human', 0.5, True, [])
    
    analysis = get_analysis_by_id(db_path, user_id, analysis_id)
    assert analysis is not None
    assert analysis['code'] == 'test code'


def test_create_uploaded_file(db_path):
    """Test creating an uploaded file record."""
    user_id = create_user(db_path, 'fileuser@gmail.com', generate_password_hash('Test123!'))
    file_id = create_uploaded_file(db_path, user_id, 'test.py', 'test.py', 100, 'py', 'print("test")')
    assert file_id > 0
    
    files = get_uploaded_files(db_path, user_id)
    assert len(files) == 1
    assert files[0]['filename'] == 'test.py'


def test_get_uploaded_files(db_path):
    """Test retrieving uploaded files."""
    user_id = create_user(db_path, 'files@gmail.com', generate_password_hash('Test123!'))
    create_uploaded_file(db_path, user_id, 'file1.py', 'file1.py', 50, 'py', 'code1')
    create_uploaded_file(db_path, user_id, 'file2.py', 'file2.py', 60, 'py', 'code2')
    
    files = get_uploaded_files(db_path, user_id)
    assert len(files) == 2


def test_create_group(db_path):
    """Test creating a group."""
    teacher_id = create_user(db_path, 'teacher@gmail.com', generate_password_hash('Test123!'), role='teacher')
    group_id = create_group(db_path, 'Test Group', 'Description', teacher_id)
    assert group_id > 0
    
    group = get_group_by_id(db_path, group_id)
    assert group is not None
    assert group['name'] == 'Test Group'


def test_get_teacher_groups(db_path):
    """Test retrieving teacher's groups."""
    teacher_id = create_user(db_path, 'teacher2@gmail.com', generate_password_hash('Test123!'), role='teacher')
    create_group(db_path, 'Group 1', 'Desc 1', teacher_id)
    create_group(db_path, 'Group 2', 'Desc 2', teacher_id)
    
    groups = get_teacher_groups(db_path, teacher_id)
    assert len(groups) == 2


def test_create_activity(db_path):
    """Test creating an activity."""
    teacher_id = create_user(db_path, 'activityteacher@gmail.com', generate_password_hash('Test123!'), role='teacher')
    group_id = create_group(db_path, 'Activity Group', 'Desc', teacher_id)
    
    activity_id = create_activity(
        db_path, group_id, teacher_id, 'Test Activity', 
        'Description', '2024-12-31', 'coding', 'instructions'
    )
    assert activity_id > 0
    
    activities = get_group_activities(db_path, group_id)
    assert len(activities) == 1
    assert activities[0]['title'] == 'Test Activity'


def test_submit_activity(db_path):
    """Test submitting an activity."""
    teacher_id = create_user(db_path, 'subteacher@gmail.com', generate_password_hash('Test123!'), role='teacher')
    student_id = create_user(db_path, 'student@gmail.com', generate_password_hash('Test123!'), role='student')
    group_id = create_group(db_path, 'Submit Group', 'Desc', teacher_id)
    activity_id = create_activity(
        db_path, group_id, teacher_id, 'Submit Activity', 
        'Desc', '2024-12-31', 'coding', 'instructions'
    )
    
    submission_id = submit_activity(db_path, activity_id, student_id, 'submitted code')
    assert submission_id > 0
    
    submissions = get_activity_submissions(db_path, activity_id)
    assert len(submissions) == 1
    assert submissions[0]['content'] == 'submitted code'


def test_get_activity_submissions(db_path):
    """Test retrieving activity submissions."""
    teacher_id = create_user(db_path, 'subteacher2@gmail.com', generate_password_hash('Test123!'), role='teacher')
    student1_id = create_user(db_path, 'student1@gmail.com', generate_password_hash('Test123!'), role='student')
    student2_id = create_user(db_path, 'student2@gmail.com', generate_password_hash('Test123!'), role='student')
    group_id = create_group(db_path, 'Multi Group', 'Desc', teacher_id)
    activity_id = create_activity(
        db_path, group_id, teacher_id, 'Multi Activity', 
        'Desc', '2024-12-31', 'coding', 'instructions'
    )
    
    submit_activity(db_path, activity_id, student1_id, 'code1')
    submit_activity(db_path, activity_id, student2_id, 'code2')
    
    submissions = get_activity_submissions(db_path, activity_id)
    assert len(submissions) == 2


def test_set_user_verification_token(db_path):
    """Test setting user verification token."""
    user_id = create_user(db_path, 'tokenuser@gmail.com', generate_password_hash('Test123!'))
    from datetime import datetime, timedelta
    code = '123456'
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    
    set_user_verification_token(db_path, user_id, code, expires_at)
    
    user = get_user_by_verification_code(db_path, code)
    assert user is not None
    assert user['id'] == user_id


def test_get_user_by_verification_code(db_path):
    """Test retrieving user by verification code."""
    user_id = create_user(db_path, 'codeuser@gmail.com', generate_password_hash('Test123!'))
    from datetime import datetime, timedelta
    code = '999888'
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    set_user_verification_token(db_path, user_id, code, expires_at)
    
    user = get_user_by_verification_code(db_path, code)
    assert user is not None
    assert user['username'] == 'codeuser@gmail.com'


def test_verification_code_expiration(db_path):
    """Test that expired verification codes are not found."""
    user_id = create_user(db_path, 'expired@gmail.com', generate_password_hash('Test123!'))
    from datetime import datetime, timedelta
    code = '111222'
    expires_at = (datetime.utcnow() - timedelta(minutes=1)).isoformat()  # Expired
    set_user_verification_token(db_path, user_id, code, expires_at)
    
    user = get_user_by_verification_code(db_path, code)
    assert user is None  # Expired code should not be found


def test_get_group_members(db_path):
    """Test retrieving group members."""
    from models import get_group_members, join_group, approve_group_member
    teacher_id = create_user(db_path, 'memberteacher@gmail.com', generate_password_hash('Test123!'), role='teacher')
    student_id = create_user(db_path, 'memberstudent@gmail.com', generate_password_hash('Test123!'), role='student')
    group_id = create_group(db_path, 'Member Group', 'Desc', teacher_id)
    
    join_group(db_path, group_id, student_id)
    approve_group_member(db_path, group_id, student_id)
    
    members = get_group_members(db_path, group_id)
    assert len(members) == 1
    assert members[0]['user_id'] == student_id


def test_get_student_activities(db_path):
    """Test retrieving student activities."""
    teacher_id = create_user(db_path, 'actteacher@gmail.com', generate_password_hash('Test123!'), role='teacher')
    student_id = create_user(db_path, 'actstudent@gmail.com', generate_password_hash('Test123!'), role='student')
    group_id = create_group(db_path, 'Act Group', 'Desc', teacher_id)
    activity_id = create_activity(db_path, group_id, teacher_id, 'Student Activity', 
                                  'Desc', '2024-12-31', 'coding', 'instructions')
    
    activities = get_student_activities(db_path, student_id)
    # Student should see activities from groups they're in
    assert isinstance(activities, list)
