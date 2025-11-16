import subprocess
import tempfile
import os
import sys
from typing import Dict, Any, Optional
import time


class CodeExecutor:
    """Safe code execution for Python and Java code"""
    
    MAX_EXECUTION_TIME = 10  # seconds
    MAX_OUTPUT_SIZE = 10000  # characters
    MAX_MEMORY_MB = 128  # MB
    
    @staticmethod
    def execute_python(code: str, timeout: int = None, input_data: str = None) -> Dict[str, Any]:
        """
        Execute Python code safely with timeout and output limits.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds (default: MAX_EXECUTION_TIME)
            input_data: Optional input string to provide to stdin (each line separated by newline)
            
        Returns:
            Dictionary with 'success', 'output', 'error', and 'execution_time'
        """
        if timeout is None:
            timeout = CodeExecutor.MAX_EXECUTION_TIME
        
        start_time = time.time()
        
        try:
            # Create a temporary file for the code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # Execute the code with timeout
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=tempfile.gettempdir(),
                    input=input_data  # Provide input to stdin
                )
                
                execution_time = time.time() - start_time
                
                # Limit output size
                stdout = result.stdout[:CodeExecutor.MAX_OUTPUT_SIZE] if result.stdout else ''
                stderr = result.stderr[:CodeExecutor.MAX_OUTPUT_SIZE] if result.stderr else ''
                
                # If output was truncated, add a note
                if result.stdout and len(result.stdout) > CodeExecutor.MAX_OUTPUT_SIZE:
                    stdout += f"\n... (output truncated, showing first {CodeExecutor.MAX_OUTPUT_SIZE} characters)"
                if result.stderr and len(result.stderr) > CodeExecutor.MAX_OUTPUT_SIZE:
                    stderr += f"\n... (error output truncated, showing first {CodeExecutor.MAX_OUTPUT_SIZE} characters)"
                
                # For Python, if returncode is non-zero, stderr usually contains the error
                # If there's stderr, it's likely an error even if stdout has content
                if result.returncode != 0 or stderr:
                    # Python errors go to stderr, combine with stdout if present
                    error_msg = stderr if stderr else 'Unknown error occurred'
                    if stdout and stderr:
                        # Both have content - show both
                        return {
                            'success': False,
                            'output': stdout,
                            'error': error_msg,
                            'execution_time': round(execution_time, 3),
                            'return_code': result.returncode
                        }
                    else:
                        # Only error, no output
                        return {
                            'success': False,
                            'output': '',
                            'error': error_msg,
                            'execution_time': round(execution_time, 3),
                            'return_code': result.returncode
                        }
                else:
                    # Success - only stdout
                    return {
                        'success': True,
                        'output': stdout,
                        'error': '',
                        'execution_time': round(execution_time, 3),
                        'return_code': result.returncode
                    }
                
            except subprocess.TimeoutExpired:
                execution_time = time.time() - start_time
                return {
                    'success': False,
                    'output': '',
                    'error': f'Execution timed out after {timeout} seconds',
                    'execution_time': round(execution_time, 3),
                    'return_code': -1
                }
            except FileNotFoundError:
                execution_time = time.time() - start_time
                return {
                    'success': False,
                    'output': '',
                    'error': f'Python interpreter not found. Please ensure Python is installed and in PATH. Tried: {sys.executable}',
                    'execution_time': round(execution_time, 3),
                    'return_code': -1
                }
            except Exception as e:
                execution_time = time.time() - start_time
                import traceback
                error_details = traceback.format_exc()
                return {
                    'success': False,
                    'output': '',
                    'error': f'Execution error: {str(e)}\n\nDetails:\n{error_details}',
                    'execution_time': round(execution_time, 3),
                    'return_code': -1
                }
            finally:
                # Clean up temporary file
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception:
                    pass
                    
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                'success': False,
                'output': '',
                'error': f'Failed to create temporary file: {str(e)}',
                'execution_time': round(execution_time, 3),
                'return_code': -1
            }
    
    @staticmethod
    def execute_java(code: str, timeout: int = None, input_data: str = None) -> Dict[str, Any]:
        """
        Execute Java code safely with timeout and output limits.
        
        Args:
            code: Java code to execute
            timeout: Execution timeout in seconds (default: MAX_EXECUTION_TIME)
            input_data: Optional input string to provide to stdin (each line separated by newline)
            
        Returns:
            Dictionary with 'success', 'output', 'error', and 'execution_time'
        """
        if timeout is None:
            timeout = CodeExecutor.MAX_EXECUTION_TIME
        
        start_time = time.time()
        temp_dir = None
        class_name = None
        
        try:
            # Extract class name from code
            import re
            class_match = re.search(r'public\s+class\s+(\w+)', code)
            if not class_match:
                return {
                    'success': False,
                    'output': '',
                    'error': 'Java code must contain a public class declaration',
                    'execution_time': 0,
                    'return_code': -1
                }
            
            class_name = class_match.group(1)
            
            # Create a temporary directory for Java files
            temp_dir = tempfile.mkdtemp()
            java_file = os.path.join(temp_dir, f'{class_name}.java')
            
            # Write Java code to file
            with open(java_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            try:
                # Compile Java code
                compile_result = subprocess.run(
                    ['javac', java_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=temp_dir
                )
                
                if compile_result.returncode != 0:
                    execution_time = time.time() - start_time
                    error_msg = compile_result.stderr[:CodeExecutor.MAX_OUTPUT_SIZE]
                    if len(compile_result.stderr) > CodeExecutor.MAX_OUTPUT_SIZE:
                        error_msg += f"\n... (error output truncated)"
                    return {
                        'success': False,
                        'output': '',
                        'error': f'Compilation error:\n{error_msg}',
                        'execution_time': round(execution_time, 3),
                        'return_code': compile_result.returncode
                    }
                
                # Execute compiled Java code
                run_result = subprocess.run(
                    ['java', '-cp', temp_dir, class_name],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=temp_dir,
                    input=input_data  # Provide input to stdin
                )
                
                execution_time = time.time() - start_time
                
                # Limit output size
                stdout = run_result.stdout[:CodeExecutor.MAX_OUTPUT_SIZE]
                stderr = run_result.stderr[:CodeExecutor.MAX_OUTPUT_SIZE]
                
                # If output was truncated, add a note
                if len(run_result.stdout) > CodeExecutor.MAX_OUTPUT_SIZE:
                    stdout += f"\n... (output truncated, showing first {CodeExecutor.MAX_OUTPUT_SIZE} characters)"
                if len(run_result.stderr) > CodeExecutor.MAX_OUTPUT_SIZE:
                    stderr += f"\n... (error output truncated, showing first {CodeExecutor.MAX_OUTPUT_SIZE} characters)"
                
                return {
                    'success': run_result.returncode == 0,
                    'output': stdout,
                    'error': stderr,
                    'execution_time': round(execution_time, 3),
                    'return_code': run_result.returncode
                }
                
            except subprocess.TimeoutExpired:
                execution_time = time.time() - start_time
                return {
                    'success': False,
                    'output': '',
                    'error': f'Execution timed out after {timeout} seconds',
                    'execution_time': round(execution_time, 3),
                    'return_code': -1
                }
            except FileNotFoundError:
                execution_time = time.time() - start_time
                return {
                    'success': False,
                    'output': '',
                    'error': 'Java compiler (javac) or runtime (java) not found. Please ensure Java is installed and in PATH.',
                    'execution_time': round(execution_time, 3),
                    'return_code': -1
                }
            except Exception as e:
                execution_time = time.time() - start_time
                return {
                    'success': False,
                    'output': '',
                    'error': f'Execution error: {str(e)}',
                    'execution_time': round(execution_time, 3),
                    'return_code': -1
                }
            finally:
                # Clean up temporary directory
                if temp_dir and os.path.exists(temp_dir):
                    try:
                        import shutil
                        shutil.rmtree(temp_dir)
                    except Exception:
                        pass
                        
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                'success': False,
                'output': '',
                'error': f'Failed to execute Java code: {str(e)}',
                'execution_time': round(execution_time, 3),
                'return_code': -1
            }
    
    @staticmethod
    def execute_code(code: str, language: str, timeout: int = None, input_data: str = None) -> Dict[str, Any]:
        """
        Execute code in the specified language.
        
        Args:
            code: Code to execute
            language: Programming language ('python' or 'java')
            timeout: Execution timeout in seconds (default: MAX_EXECUTION_TIME)
            input_data: Optional input string to provide to stdin (each line separated by newline)
            
        Returns:
            Dictionary with execution results
        """
        language = language.lower().strip()
        
        if language == 'python' or language == 'py':
            return CodeExecutor.execute_python(code, timeout, input_data)
        elif language == 'java':
            return CodeExecutor.execute_java(code, timeout, input_data)
        else:
            return {
                'success': False,
                'output': '',
                'error': f'Language "{language}" is not supported for code execution. Supported languages: Python, Java',
                'execution_time': 0,
                'return_code': -1
            }

