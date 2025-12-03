#!/usr/bin/env python
"""
Test runner script for CodeCraft application.
Run this script to execute all unit tests.
"""
import sys
import subprocess

def main():
    """Run pytest with appropriate options."""
    # Run pytest with verbose output and coverage
    cmd = [
        sys.executable, '-m', 'pytest',
        'tests/',
        '-v',  # Verbose output
        '--tb=short',  # Short traceback format
        '--color=yes',  # Colored output
    ]
    
    # Add coverage if pytest-cov is available
    try:
        import pytest_cov
        cmd.extend(['--cov=.', '--cov-report=term-missing'])
    except ImportError:
        print("pytest-cov not installed. Run 'pip install pytest-cov' for coverage reports.")
    
    result = subprocess.run(cmd)
    return result.returncode

if __name__ == '__main__':
    sys.exit(main())

