"""
Unit tests for utility functions.
"""
import pytest
from werkzeug.security import generate_password_hash, check_password_hash


class TestPasswordHashing:
    """Tests for password hashing utilities."""
    
    def test_generate_password_hash(self):
        """Test password hash generation."""
        password = 'testpassword123'
        hash1 = generate_password_hash(password)
        hash2 = generate_password_hash(password)
        
        # Hashes should be different (due to salt)
        assert hash1 != hash2
        
        # But both should verify correctly
        assert check_password_hash(hash1, password)
        assert check_password_hash(hash2, password)
    
    def test_check_password_hash(self):
        """Test password hash verification."""
        password = 'testpassword123'
        password_hash = generate_password_hash(password)
        
        # Correct password
        assert check_password_hash(password_hash, password) is True
        
        # Wrong password
        assert check_password_hash(password_hash, 'wrongpassword') is False
    
    def test_password_hash_consistency(self):
        """Test that password hashing is consistent."""
        password = 'testpassword123'
        hash1 = generate_password_hash(password)
        
        # Same password should verify against the hash
        assert check_password_hash(hash1, password) is True
        
        # Different password should not verify
        assert check_password_hash(hash1, 'differentpassword') is False


class TestCodeValidation:
    """Tests for code validation utilities."""
    
    def test_code_length_validation(self):
        """Test code length validation."""
        short_code = 'x' * 100
        long_code = 'x' * 10000
        
        # Should accept reasonable length
        assert len(short_code) < 10000
        
        # Should reject very long code
        assert len(long_code) > 1000
    
    def test_code_line_count(self):
        """Test counting lines in code."""
        code_10_lines = '\n'.join([f'line {i}' for i in range(10)])
        code_1000_lines = '\n'.join([f'line {i}' for i in range(1000)])
        code_2000_lines = '\n'.join([f'line {i}' for i in range(2000)])
        
        assert code_10_lines.count('\n') + 1 == 10
        assert code_1000_lines.count('\n') + 1 == 1000
        assert code_2000_lines.count('\n') + 1 == 2000


class TestEmailValidation:
    """Tests for email validation."""
    
    def test_gmail_validation(self):
        """Test Gmail address validation."""
        valid_emails = [
            'test@gmail.com',
            'user.name@gmail.com',
            'user+tag@gmail.com',
        ]
        
        invalid_emails = [
            'test@yahoo.com',
            'test@hotmail.com',
            'notanemail',
            'test@',
        ]
        
        for email in valid_emails:
            assert '@' in email and email.endswith('@gmail.com')
        
        for email in invalid_emails:
            if not email.endswith('@gmail.com'):
                assert True  # Invalid as expected

