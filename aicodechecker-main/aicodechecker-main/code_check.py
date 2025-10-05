import ast
import re
from typing import Dict, Any, List, Tuple


def _guess_language(code: str, hint: str) -> str:
    h = (hint or '').strip().lower()
    if h in ('py', 'python'): return 'python'
    if h in ('js', 'javascript', 'node', 'ts', 'typescript'): return 'javascript'
    # Heuristics
    if 'def ' in code or 'import ' in code or 'class ' in code:
        return 'python'
    if 'function ' in code or ';' in code or '=>' in code:
        return 'javascript'
    return 'unknown'


def _check_python(code: str) -> Tuple[bool, List[str]]:
    try:
        ast.parse(code)
        return True, []
    except SyntaxError as e:
        msg = f"SyntaxError: {e.msg} at line {e.lineno}, column {e.offset}"
        line = ''
        if e.text:
            line = e.text.strip('\n')
        details = f"Line: {line}" if line else ''
        return False, [msg, details] if details else [msg]
    except Exception as e:
        return False, [f"Error: {type(e).__name__}: {e}"]


def _check_balanced(code: str) -> Tuple[bool, List[str]]:
    stack: List[str] = []
    pairs = {')': '(', ']': '[', '}': '{'}
    opening = set(pairs.values())
    closing = set(pairs.keys())

    in_single = False
    in_double = False
    escape = False

    for ch in code:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if not in_double and ch == "'":
            in_single = not in_single
        elif not in_single and ch == '"':
            in_double = not in_double
        elif not in_single and not in_double:
            if ch in opening:
                stack.append(ch)
            elif ch in closing:
                if not stack or stack[-1] != pairs[ch]:
                    return False, [f"Unbalanced delimiter near '{ch}'"]
                stack.pop()
    if in_single or in_double:
        return False, ["Unterminated string literal"]
    if stack:
        return False, ["Unbalanced delimiters: " + ''.join(stack)]
    return True, []


def validate_language_match(code: str, selected_language: str) -> Tuple[bool, str]:
    """
    Validate that the input code matches the selected programming language.
    Returns (is_valid, error_message).
    """
    if not selected_language or selected_language.lower() == 'auto':
        return True, ""
    
    code = code.strip()
    if not code:
        return True, ""
    
    selected_language = selected_language.lower()
    
    # Language-specific validation rules
    if selected_language == 'python':
        # Prefer strong Python-only indicators (exclude ambiguous ones like 'class')
        strong_python_indicators = [
            r'def\s+\w+\s*\(',  # function definitions
            r'import\s+',       # import statements
            r'from\s+\w+\s+import',  # from imports
            r'if\s+__name__\s*==\s*[\'"]__main__[\'"]',  # main guard
            r'print\s*\(',      # print statements
            r'for\s+\w+\s+in',  # for loops
            r'while\s+',        # while loops
            r'elif\s+',         # elif statements
            r'else\s*:',        # else statements
            r'try\s*:',         # try blocks
            r'except\s+',       # except blocks
            r'finally\s*:',     # finally blocks
            r'with\s+',         # with statements
            r'async\s+def',     # async functions
            r'await\s+',        # await statements
        ]
        
        # Check for Python-specific syntax (strong)
        has_strong_python = any(re.search(pattern, code, re.IGNORECASE) for pattern in strong_python_indicators)
        
        # Check for non-Python indicators
        non_python_indicators = [
            r'public\s+class',   # Java
            r'private\s+',       # Java/C#
            r'protected\s+',     # Java/C#
            r'namespace\s+',     # C#
            r'using\s+',         # C#
            r'#include\s+<',     # C++
            r'std::',            # C++
            r'int\s+main\s*\(',  # C/C++
            r'cout\s*<<',        # C++
            r'cin\s*>>',         # C++
            r'printf\s*\(',      # C
            r'scanf\s*\(',       # C
            r'function\s+\w+\s*\(',  # JavaScript
            r'var\s+',           # JavaScript
            r'let\s+',           # JavaScript
            r'const\s+',         # JavaScript
            r'console\.log',     # JavaScript
        ]
        
        has_non_python = any(re.search(pattern, code, re.IGNORECASE) for pattern in non_python_indicators)
        has_braces_or_semicolons = bool(re.search(r'[{};]', code))
        
        if (has_non_python or has_braces_or_semicolons) and not has_strong_python:
            return False, "This code appears to be written in a different programming language, not Python."
        
    elif selected_language == 'java':
        # Java indicators
        java_indicators = [
            r'public\s+class',   # public class
            r'private\s+',       # private members
            r'protected\s+',     # protected members
            r'public\s+static\s+void\s+main',  # main method
            r'System\.out\.println',  # print statements
            r'import\s+java\.',  # Java imports
            r'package\s+',       # package declaration
            r'extends\s+',       # inheritance
            r'implements\s+',    # interface implementation
            r'new\s+\w+\s*\(',   # object creation
            r'ArrayList<',       # generics
            r'HashMap<',         # generics
            r'String\s+',        # String type
            r'int\s+',           # int type
            r'boolean\s+',       # boolean type
        ]
        
        # Check for Java-specific syntax
        has_java_syntax = any(re.search(pattern, code, re.IGNORECASE) for pattern in java_indicators)
        
        # Check for non-Java indicators
        non_java_indicators = [
            r'def\s+\w+\s*\(',   # Python
            r'import\s+',        # Python
            r'print\s*\(',       # Python
            r'#include\s+<',     # C++
            r'std::',            # C++
            r'namespace\s+',     # C#
            r'using\s+',         # C#
            r'function\s+\w+\s*\(',  # JavaScript
            r'var\s+',           # JavaScript
            r'console\.log',     # JavaScript
        ]
        
        has_non_java = any(re.search(pattern, code, re.IGNORECASE) for pattern in non_java_indicators)
        
        if has_non_java and not has_java_syntax:
            return False, "This code appears to be written in a different programming language, not Java."
        
    elif selected_language == 'csharp':
        # C# indicators
        csharp_indicators = [
            r'namespace\s+',     # namespace
            r'using\s+',         # using statements
            r'public\s+class',   # public class
            r'private\s+',       # private members
            r'protected\s+',     # protected members
            r'static\s+void\s+Main',  # main method
            r'Console\.WriteLine',  # print statements
            r'Console\.ReadLine',   # input statements
            r'var\s+',           # var keyword
            r'string\s+',        # string type
            r'int\s+',           # int type
            r'bool\s+',          # bool type
            r'List<',            # generics
            r'Dictionary<',      # generics
            r'get;\s*set;',      # properties
            r'[^\w\s]get\s*{',  # getter
            r'[^\w\s]set\s*{',  # setter
        ]
        
        # Check for C#-specific syntax
        has_csharp_syntax = any(re.search(pattern, code, re.IGNORECASE) for pattern in csharp_indicators)
        
        # Check for non-C# indicators
        non_csharp_indicators = [
            r'def\s+\w+\s*\(',   # Python
            r'import\s+',        # Python
            r'print\s*\(',       # Python
            r'public\s+static\s+void\s+main',  # Java
            r'System\.out\.println',  # Java
            r'#include\s+<',     # C++
            r'std::',            # C++
            r'function\s+\w+\s*\(',  # JavaScript
            r'var\s+',           # JavaScript
            r'console\.log',     # JavaScript
        ]
        
        has_non_csharp = any(re.search(pattern, code, re.IGNORECASE) for pattern in non_csharp_indicators)
        
        if has_non_csharp and not has_csharp_syntax:
            return False, "This code appears to be written in a different programming language, not C#."
        
    elif selected_language == 'cpp':
        # C++ indicators
        cpp_indicators = [
            r'#include\s+<',     # include statements
            r'#include\s+"',     # include statements
            r'std::',            # std namespace
            r'using\s+namespace\s+std',  # using namespace
            r'int\s+main\s*\(',  # main function
            r'void\s+main\s*\(', # void main
            r'cout\s*<<',        # cout
            r'cin\s*>>',         # cin
            r'printf\s*\(',      # printf
            r'scanf\s*\(',       # scanf
            r'class\s+\w+',      # class definition
            r'template\s*<',     # templates
            r'vector\s*<',       # STL containers
            r'string\s+',        # string type
            r'auto\s+',          # auto keyword
            r'nullptr',          # nullptr
            r'delete\s+',        # delete operator
            r'new\s+\w+\s*\(',   # new operator
        ]
        
        # Check for C++-specific syntax
        has_cpp_syntax = any(re.search(pattern, code, re.IGNORECASE) for pattern in cpp_indicators)
        
        # Check for non-C++ indicators
        non_cpp_indicators = [
            r'def\s+\w+\s*\(',   # Python
            r'import\s+',        # Python
            r'print\s*\(',       # Python
            r'public\s+static\s+void\s+main',  # Java
            r'System\.out\.println',  # Java
            r'namespace\s+',     # C#
            r'using\s+',         # C#
            r'Console\.WriteLine',  # C#
            r'function\s+\w+\s*\(',  # JavaScript
            r'var\s+',           # JavaScript
            r'console\.log',     # JavaScript
        ]
        
        has_non_cpp = any(re.search(pattern, code, re.IGNORECASE) for pattern in non_cpp_indicators)
        
        if has_non_cpp and not has_cpp_syntax:
            return False, "This code appears to be written in a different programming language, not C++."
    
    return True, ""


def check_code(code: str, language_hint: str = 'auto') -> Dict[str, Any]:
    lang = _guess_language(code, language_hint)
    errors: List[str] = []
    ok = True

    if lang == 'python':
        ok, errors = _check_python(code)
        if ok:
            ok2, errs2 = _check_balanced(code)
            ok = ok and ok2
            errors.extend(errs2)
    else:
        ok, errors = _check_balanced(code)

    return {
        'language': lang,
        'ok': bool(ok and not errors),
        'errors': errors,
    }
