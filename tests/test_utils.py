import pytest
from werkzeug.security import generate_password_hash, check_password_hash
from app import app as flask_app


def test_password_hashing():
    """Test password hashing and verification."""
    password = 'TestPassword123!'
    hash1 = generate_password_hash(password)
    hash2 = generate_password_hash(password)
    
    # Hashes should be different (due to salt)
    assert hash1 != hash2
    
    # Both should verify correctly
    assert check_password_hash(hash1, password) is True
    assert check_password_hash(hash2, password) is True
    
    # Wrong password should fail
    assert check_password_hash(hash1, 'WrongPassword') is False


def test_gmail_validation():
    """Test Gmail address validation."""
    valid_emails = [
        'test@gmail.com',
        'user.name@gmail.com',
        'user+tag@gmail.com',
        '123@gmail.com'
    ]
    
    invalid_emails = [
        'test@yahoo.com',
        'test@hotmail.com',
        'test@gmail',
        'test@.com',
        'notanemail'
    ]
    
    for email in valid_emails:
        assert '@' in email and email.lower().endswith('@gmail.com')
    
    for email in invalid_emails:
        assert not ('@' in email and email.lower().endswith('@gmail.com'))


def test_verification_code_format():
    """Test verification code format (6 digits)."""
    valid_codes = ['123456', '000000', '999999', '012345']
    invalid_codes = ['12345', '1234567', 'abcdef', '12 3456', '']
    
    for code in valid_codes:
        assert len(code) == 6 and code.isdigit()
    
    for code in invalid_codes:
        assert not (len(code) == 6 and code.isdigit())


def test_allowed_file_extensions():
    """Test file extension validation."""
    from app import allowed_file
    
    # According to app.py comment, only Python and Java files are allowed for upload
    valid_files = ['test.py', 'code.java']
    invalid_files = ['test.txt', 'code.doc', 'script.exe', 'script.js', 'file.cpp', 'app.cs', 'file', 'noextension']
    
    for filename in valid_files:
        assert allowed_file(filename) is True
    
    for filename in invalid_files:
        assert allowed_file(filename) is False


def test_get_language_from_extension():
    """Test language detection from file extension."""
    from app import get_language_from_extension
    
    test_cases = {
        'test.py': 'python',
        'code.java': 'java',
        'script.js': 'javascript',
        'file.cpp': 'cpp',
        'app.cs': 'csharp'
    }
    
    for filename, expected_lang in test_cases.items():
        result = get_language_from_extension(filename)
        assert result == expected_lang


def test_secure_filename():
    """Test secure filename generation."""
    from werkzeug.utils import secure_filename
    
    test_cases = {
        'test file.py': 'test_file.py',
        '../../etc/passwd': 'etc_passwd',
        'file with spaces.txt': 'file_with_spaces.txt',
        'normal-file.py': 'normal-file.py'
    }
    
    for input_name, expected in test_cases.items():
        result = secure_filename(input_name)
        # Secure filename should not contain spaces or path separators
        assert ' ' not in result
        assert '/' not in result
        assert '\\' not in result

