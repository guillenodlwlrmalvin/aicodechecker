"""
Unit tests for database models and operations.
"""
import os
import pytest
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

from models import (
    initialize_database,
    create_user,
    get_user_by_username,
    get_user_by_id,
    get_user_count,
    approve_user,
    update_user_password,
    update_user_role,
    create_analysis,
    get_recent_analyses,
    create_group,
    get_group_by_id,
    get_teacher_groups,
    create_activity,
    get_activity_by_id,
    submit_activity,
    get_activity_submissions,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_models.db')
    initialize_database(db)
    return db


class TestUserOperations:
    """Tests for user-related database operations."""
    
    def test_initialize_database(self, tmp_path):
        """Test database initialization."""
        db = os.path.join(tmp_path, 'test_init.db')
        initialize_database(db)
        
        # Database should be created
        assert os.path.exists(db)
    
    def test_create_user(self, db_path):
        """Test creating a user."""
        user_id = create_user(db_path, 'test@test.com', 'hash123')
        assert user_id > 0
        
        user = get_user_by_username(db_path, 'test@test.com')
        assert user is not None
        assert user['username'] == 'test@test.com'
        assert user['role'] == 'student'
        assert user['is_admin'] == 0
        assert user['is_approved'] == 0
    
    def test_create_admin_user(self, db_path):
        """Test creating an admin user."""
        user_id = create_user(db_path, 'admin@test.com', 'hash123', is_admin=True, is_approved=True)
        
        user = get_user_by_id(db_path, user_id)
        assert user['is_admin'] == 1
        assert user['is_approved'] == 1
    
    def test_get_user_by_username(self, db_path):
        """Test retrieving user by username."""
        create_user(db_path, 'test@test.com', 'hash123')
        
        user = get_user_by_username(db_path, 'test@test.com')
        assert user is not None
        assert user['username'] == 'test@test.com'
        
        # Non-existent user
        user = get_user_by_username(db_path, 'nonexistent@test.com')
        assert user is None
    
    def test_get_user_by_id(self, db_path):
        """Test retrieving user by ID."""
        user_id = create_user(db_path, 'test@test.com', 'hash123')
        
        user = get_user_by_id(db_path, user_id)
        assert user is not None
        assert user['id'] == user_id
    
    def test_approve_user(self, db_path):
        """Test approving a user."""
        user_id = create_user(db_path, 'test@test.com', 'hash123', is_approved=0)
        
        approve_user(db_path, user_id)
        
        user = get_user_by_id(db_path, user_id)
        assert user['is_approved'] == 1
    
    def test_update_user_password(self, db_path):
        """Test updating user password."""
        user_id = create_user(db_path, 'test@test.com', 'old_hash')
        
        new_hash = generate_password_hash('newpassword')
        update_user_password(db_path, user_id, new_hash)
        
        user = get_user_by_id(db_path, user_id)
        assert user['password_hash'] == new_hash
    
    def test_update_user_role(self, db_path):
        """Test updating user role."""
        user_id = create_user(db_path, 'test@test.com', 'hash123', role='student')
        
        update_user_role(db_path, user_id, 'teacher')
        
        user = get_user_by_id(db_path, user_id)
        assert user['role'] == 'teacher'
    
    def test_get_user_count(self, db_path):
        """Test getting user count."""
        assert get_user_count(db_path) == 0
        
        create_user(db_path, 'user1@test.com', 'hash1')
        assert get_user_count(db_path) == 1
        
        create_user(db_path, 'user2@test.com', 'hash2')
        assert get_user_count(db_path) == 2


class TestAnalysisOperations:
    """Tests for code analysis database operations."""
    
    def test_create_analysis(self, db_path):
        """Test creating an analysis record."""
        user_id = create_user(db_path, 'test@test.com', 'hash123')
        
        analysis_id = create_analysis(
            db_path, user_id, 'print("hello")', 'python', 'human', 0.85,
            check_ok=True, check_errors=[]
        )
        
        assert analysis_id > 0
    
    def test_get_recent_analyses(self, db_path):
        """Test retrieving recent analyses."""
        user_id = create_user(db_path, 'test@test.com', 'hash123')
        
        # Create multiple analyses
        create_analysis(db_path, user_id, 'code1', 'python', 'human', 0.8, check_ok=True, check_errors=[])
        create_analysis(db_path, user_id, 'code2', 'python', 'ai', 0.9, check_ok=True, check_errors=[])
        create_analysis(db_path, user_id, 'code3', 'python', 'human', 0.7, check_ok=True, check_errors=[])
        
        analyses = get_recent_analyses(db_path, user_id, limit=2)
        assert len(analyses) == 2
        # Should be ordered by most recent first
        assert analyses[0]['code'] == 'code3'


class TestGroupOperations:
    """Tests for group-related database operations."""
    
    def test_create_group(self, db_path):
        """Test creating a group."""
        teacher_id = create_user(db_path, 'teacher@test.com', 'hash123', role='teacher')
        
        group_id = create_group(db_path, 'Test Group', 'Test Description', teacher_id)
        
        assert group_id > 0
        
        group = get_group_by_id(db_path, group_id)
        assert group is not None
        assert group['name'] == 'Test Group'
        assert group['teacher_id'] == teacher_id
    
    def test_get_teacher_groups(self, db_path):
        """Test retrieving groups for a teacher."""
        teacher_id = create_user(db_path, 'teacher@test.com', 'hash123', role='teacher')
        
        create_group(db_path, 'Group 1', 'Desc 1', teacher_id)
        create_group(db_path, 'Group 2', 'Desc 2', teacher_id)
        
        groups = get_teacher_groups(db_path, teacher_id)
        assert len(groups) == 2


class TestActivityOperations:
    """Tests for activity-related database operations."""
    
    def test_create_activity(self, db_path):
        """Test creating an activity."""
        teacher_id = create_user(db_path, 'teacher@test.com', 'hash123', role='teacher')
        group_id = create_group(db_path, 'Test Group', 'Desc', teacher_id)
        
        activity_id = create_activity(
            db_path, group_id, teacher_id, 'Test Activity', 'Activity Description',
            'Activity content here', 'text', '2024-12-31T23:59:59'
        )
        
        assert activity_id > 0
        
        activity = get_activity_by_id(db_path, activity_id)
        assert activity is not None
        assert activity['title'] == 'Test Activity'
    
    def test_submit_activity(self, db_path):
        """Test submitting an activity."""
        teacher_id = create_user(db_path, 'teacher@test.com', 'hash123', role='teacher')
        student_id = create_user(db_path, 'student@test.com', 'hash123', role='student')
        group_id = create_group(db_path, 'Test Group', 'Desc', teacher_id)
        activity_id = create_activity(
            db_path, group_id, teacher_id, 'Test Activity', 'Desc', 'Content', 'text'
        )
        
        submission_id = submit_activity(
            db_path, activity_id, student_id, 'submission_code'
        )
        
        assert submission_id > 0
        
        submissions = get_activity_submissions(db_path, activity_id)
        assert len(submissions) >= 1
        # Check that submission exists
        assert any(sub['content'] == 'submission_code' for sub in submissions)
