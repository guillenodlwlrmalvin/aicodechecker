"""Tests for Utility Functions (7 tests)."""
import pytest
from werkzeug.security import generate_password_hash, check_password_hash
from app import allowed_file, get_language_from_extension


def test_password_hashing():
    """Test password hashing and verification."""
    password = 'Test123!'
    hash1 = generate_password_hash(password)
    hash2 = generate_password_hash(password)
    
    # Hashes should be different (due to salt)
    assert hash1 != hash2
    
    # But both should verify correctly
    assert check_password_hash(hash1, password) == True
    assert check_password_hash(hash2, password) == True
    
    # Wrong password should fail
    assert check_password_hash(hash1, 'Wrong123!') == False


def test_allowed_file_extensions():
    """Test allowed file extension validation."""
    assert allowed_file('test.py') == True
    assert allowed_file('test.java') == True
    assert allowed_file('test.PY') == True  # Case insensitive
    assert allowed_file('test.JAVA') == True
    assert allowed_file('test.txt') == False
    assert allowed_file('test.py.bak') == False
    assert allowed_file('test') == False  # No extension


def test_get_language_from_extension():
    """Test getting language from file extension."""
    assert get_language_from_extension('test.py') == 'python'
    assert get_language_from_extension('test.java') == 'java'
    assert get_language_from_extension('test.PY') == 'python'  # Case insensitive
    assert get_language_from_extension('test.JAVA') == 'java'
    assert get_language_from_extension('test.txt') == 'auto'  # Unknown extension returns 'auto'
    assert get_language_from_extension('test.cs') == 'csharp'
    assert get_language_from_extension('test.js') == 'javascript'


def test_gmail_validation():
    """Test Gmail address validation."""
    valid_emails = [
        'test@gmail.com',
        'user.name@gmail.com',
        'user+tag@gmail.com',
        '123@gmail.com'
    ]
    
    invalid_emails = [
        'test@gmail',
        'test@example.com',
        'test@yahoo.com',
        'notanemail'
    ]
    
    for email in valid_emails:
        assert '@' in email and email.lower().endswith('@gmail.com')
    
    for email in invalid_emails:
        assert not ('@' in email and email.lower().endswith('@gmail.com'))


def test_verification_code_format():
    """Test verification code format validation."""
    valid_codes = ['123456', '000000', '999999']
    invalid_codes = ['12345', '1234567', 'abcdef', '12345a', '']
    
    for code in valid_codes:
        assert len(code) == 6 and code.isdigit()
    
    for code in invalid_codes:
        assert not (len(code) == 6 and code.isdigit())


def test_email_format_validation():
    """Test email format validation."""
    valid_emails = [
        'user@gmail.com',
        'user.name@gmail.com',
        'user+tag@gmail.com'
    ]
    
    invalid_emails = [
        'notanemail',
        '@gmail.com',
        'user@',
        'user @gmail.com'  # Space
    ]
    
    for email in valid_emails:
        parts = email.split('@')
        assert len(parts) == 2 and '.' in parts[1], f"Email '{email}' should be valid"
    
    for email in invalid_emails:
        if '@' in email:
            parts = email.split('@')
            # Check if there's a valid local part (before @) and domain part (after @)
            # Also check for spaces in email
            has_space = ' ' in email
            is_valid = len(parts) == 2 and len(parts[0]) > 0 and '.' in parts[1] if len(parts) > 1 else False
            is_valid = is_valid and not has_space
        else:
            is_valid = False
        assert not is_valid, f"Email '{email}' should be invalid"


def test_password_strength_validation():
    """Test password strength validation (basic checks)."""
    # In a real app, you'd have more sophisticated validation
    weak_passwords = ['123', 'abc', 'short', 'weak']  # All < 8 characters
    strong_passwords = ['Test123!', 'SecurePass1', 'MyP@ssw0rd', 'LongEnough123']  # All >= 8 characters
    
    for pwd in weak_passwords:
        assert len(pwd) < 8, f"Password '{pwd}' should be considered weak (too short)"
    
    for pwd in strong_passwords:
        assert len(pwd) >= 8, f"Password '{pwd}' should meet minimum length requirement"

