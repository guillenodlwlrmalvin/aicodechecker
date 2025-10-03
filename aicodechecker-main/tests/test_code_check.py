import pytest

from code_check import check_code, validate_language_match


def test_check_code_python_valid():
    code = """
def add(a, b):
    return a + b
""".strip()
    result = check_code(code, 'python')
    assert result['language'] == 'python'
    assert result['ok'] is True
    assert result['errors'] == []


def test_check_code_python_syntax_error():
    code = """
def add(a, b):
    return a +
""".strip()
    result = check_code(code, 'python')
    assert result['language'] == 'python'
    assert result['ok'] is False
    assert any('SyntaxError' in e for e in result['errors'])


def test_check_code_balanced_non_python():
    js = "function x(){ return (1 + 2); }"
    result = check_code(js, 'javascript')
    assert result['language'] == 'javascript'
    assert result['ok'] is True


@pytest.mark.parametrize(
    'lang,code,expected',
    [
        ('python', 'def x():\n    pass', True),
        ('python', 'public class X { }', False),
        ('java', 'public class X { }', True),
        ('java', 'def x(): pass', False),
        ('cpp', '#include <iostream>\nint main() { return 0; }', True),
        ('cpp', 'def x(): pass', False),
    ],
)
def test_validate_language_match(lang, code, expected):
    ok, _ = validate_language_match(code, lang)
    assert ok is expected


