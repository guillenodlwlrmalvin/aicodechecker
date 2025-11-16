import subprocess
import tempfile
import os
import sys
import threading
import time
import queue
from typing import Dict, Any, Optional


class InteractiveExecutor:
    """Interactive code execution with real-time I/O"""
    
    MAX_EXECUTION_TIME = 300  # 5 minutes for interactive sessions
    MAX_OUTPUT_SIZE = 100000  # 100KB for interactive output
    
    def __init__(self, code: str, language: str, session_id: str):
        self.code = code
        self.language = language.lower().strip()
        self.session_id = session_id
        self.process = None
        self.temp_file = None
        self.temp_dir = None
        self.output_queue = queue.Queue()
        self.error_queue = queue.Queue()
        self.is_running = False
        self.start_time = None
        self.output_thread = None
        self.error_thread = None
        
    def start(self) -> Dict[str, Any]:
        """Start the interactive execution"""
        try:
            if self.language == 'python' or self.language == 'py':
                return self._start_python()
            elif self.language == 'java':
                return self._start_java()
            else:
                return {
                    'success': False,
                    'error': f'Language "{self.language}" is not supported for interactive execution.'
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to start execution: {str(e)}'
            }
    
    def _start_python(self) -> Dict[str, Any]:
        """Start Python execution"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(self.code)
                self.temp_file = f.name
            
            # Start process with pipes for interactive I/O
            # Use -u flag for unbuffered stdout/stderr, and PYTHONUNBUFFERED env var
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            
            self.process = subprocess.Popen(
                [sys.executable, '-u', self.temp_file],  # -u for unbuffered output
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,  # Unbuffered for immediate output
                cwd=tempfile.gettempdir(),
                universal_newlines=True,
                env=env  # Set PYTHONUNBUFFERED environment variable
            )
            
            self.is_running = True
            self.start_time = time.time()
            
            # Start threads to read output and error
            self.output_thread = threading.Thread(target=self._read_output, daemon=True)
            self.error_thread = threading.Thread(target=self._read_error, daemon=True)
            self.output_thread.start()
            self.error_thread.start()
            
            return {
                'success': True,
                'message': 'Execution started',
                'session_id': self.session_id
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to start Python execution: {str(e)}'
            }
    
    def _start_java(self) -> Dict[str, Any]:
        """Start Java execution"""
        try:
            import re
            # Extract class name
            class_match = re.search(r'public\s+class\s+(\w+)', self.code)
            if not class_match:
                return {
                    'success': False,
                    'error': 'Java code must contain a public class declaration'
                }
            
            class_name = class_match.group(1)
            
            # Create temporary directory
            self.temp_dir = tempfile.mkdtemp()
            java_file = os.path.join(self.temp_dir, f'{class_name}.java')
            
            # Write Java code
            with open(java_file, 'w', encoding='utf-8') as f:
                f.write(self.code)
            
            # Compile Java code
            compile_result = subprocess.run(
                ['javac', java_file],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.temp_dir
            )
            
            if compile_result.returncode != 0:
                return {
                    'success': False,
                    'error': f'Compilation error:\n{compile_result.stderr}'
                }
            
            # Start Java process with proper buffering for Windows
            self.process = subprocess.Popen(
                ['java', '-cp', self.temp_dir, class_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered for better input handling with Scanner
                cwd=self.temp_dir,
                universal_newlines=True
            )
            
            self.is_running = True
            self.start_time = time.time()
            
            # Start threads to read output and error
            self.output_thread = threading.Thread(target=self._read_output, daemon=True)
            self.error_thread = threading.Thread(target=self._read_error, daemon=True)
            self.output_thread.start()
            self.error_thread.start()
            
            return {
                'success': True,
                'message': 'Execution started',
                'session_id': self.session_id
            }
            
        except FileNotFoundError:
            return {
                'success': False,
                'error': 'Java compiler (javac) or runtime (java) not found. Please ensure Java is installed.'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to start Java execution: {str(e)}'
            }
    
    def _read_output(self):
        """Read stdout in a separate thread"""
        if not self.process:
            return
        
        try:
            import sys as sys_module
            
            while self.is_running and self.process:
                if self.process.stdout:
                    try:
                        # For Windows, read character by character for immediate output
                        if sys_module.platform == 'win32':
                            # Read character by character for immediate display of prompts
                            char = self.process.stdout.read(1)
                            if char:
                                self.output_queue.put(('output', char))
                            elif self.process.poll() is not None:
                                # Process ended, read any remaining output
                                remaining = self.process.stdout.read()
                                if remaining:
                                    self.output_queue.put(('output', remaining))
                                break
                            else:
                                # No data available, small sleep to avoid busy waiting
                                time.sleep(0.01)
                        else:
                            # On Unix, use select for non-blocking read
                            import select
                            if select.select([self.process.stdout], [], [], 0.1)[0]:
                                chunk = self.process.stdout.read(1)  # Read 1 char at a time for responsiveness
                                if chunk:
                                    self.output_queue.put(('output', chunk))
                            elif self.process.poll() is not None:
                                # Process ended, read any remaining output
                                remaining = self.process.stdout.read()
                                if remaining:
                                    self.output_queue.put(('output', remaining))
                                break
                    except ImportError:
                        # Fallback: read character by character
                        try:
                            char = self.process.stdout.read(1)
                            if char:
                                self.output_queue.put(('output', char))
                            elif self.process.poll() is not None:
                                remaining = self.process.stdout.read()
                                if remaining:
                                    self.output_queue.put(('output', remaining))
                                break
                            else:
                                time.sleep(0.01)
                        except Exception:
                            if self.process.poll() is not None:
                                break
                    except Exception:
                        if self.process.poll() is not None:
                            break
                else:
                    break
        except Exception as e:
            self.error_queue.put(('error', f'Error reading output: {str(e)}'))
        finally:
            self.output_queue.put(('done', None))
    
    def _read_error(self):
        """Read stderr in a separate thread"""
        if not self.process:
            return
        
        try:
            import sys as sys_module
            
            while self.is_running and self.process:
                if self.process.stderr:
                    try:
                        chunk = self.process.stderr.read(1024)
                        if chunk:
                            self.error_queue.put(('error', chunk))
                        elif self.process.poll() is not None:
                            break
                    except Exception:
                        if self.process.poll() is not None:
                            break
                else:
                    break
        except Exception:
            pass
    
    def send_input(self, input_data: str) -> Dict[str, Any]:
        """Send input to the running process"""
        if not self.is_running or not self.process:
            return {
                'success': False,
                'error': 'Process is not running'
            }
        
        try:
            if self.process.stdin:
                # Ensure input_data ends with newline if it doesn't already
                if not input_data.endswith('\n'):
                    input_data = input_data + '\n'
                
                # Write and flush immediately
                self.process.stdin.write(input_data)
                self.process.stdin.flush()
                
                return {
                    'success': True,
                    'message': 'Input sent'
                }
            else:
                return {
                    'success': False,
                    'error': 'Process stdin is not available'
                }
        except BrokenPipeError:
            return {
                'success': False,
                'error': 'Process has terminated'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to send input: {str(e)}'
            }
    
    def get_output(self) -> Dict[str, Any]:
        """Get available output from the process"""
        output_chunks = []
        error_chunks = []
        done = False
        
        # Collect all available output
        while True:
            try:
                msg_type, data = self.output_queue.get_nowait()
                if msg_type == 'output':
                    output_chunks.append(data)
                elif msg_type == 'done':
                    done = True
                    break
            except queue.Empty:
                break
        
        # Collect all available errors
        while True:
            try:
                msg_type, data = self.error_queue.get_nowait()
                if msg_type == 'error':
                    error_chunks.append(data)
            except queue.Empty:
                break
        
        # Check if process is still running
        if self.process and self.process.poll() is not None:
            # Process has ended
            if not done:
                # Read any remaining output
                try:
                    if self.process.stdout:
                        remaining = self.process.stdout.read()
                        if remaining:
                            output_chunks.append(remaining)
                except Exception:
                    pass
                
                try:
                    if self.process.stderr:
                        remaining = self.process.stderr.read()
                        if remaining:
                            error_chunks.append(remaining)
                except Exception:
                    pass
            
            self.is_running = False
            done = True
        
        output = ''.join(output_chunks)
        error = ''.join(error_chunks)
        
        return {
            'output': output,
            'error': error,
            'is_running': self.is_running,
            'done': done,
            'return_code': self.process.poll() if self.process else None
        }
    
    def stop(self):
        """Stop the execution"""
        self.is_running = False
        
        if self.process:
            try:
                self.process.terminate()
                # Wait a bit, then kill if still running
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            except Exception:
                pass
        
        # Cleanup
        self._cleanup()
    
    def _cleanup(self):
        """Clean up temporary files"""
        try:
            if self.temp_file and os.path.exists(self.temp_file):
                os.unlink(self.temp_file)
        except Exception:
            pass
        
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass

