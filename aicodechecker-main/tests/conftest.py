import os
import sys

# Ensure the correct project root (this directory's parent) is on sys.path
this_dir = os.path.dirname(__file__)
project_root = os.path.dirname(this_dir)
if os.path.isfile(os.path.join(project_root, 'app.py')) and project_root not in sys.path:
    sys.path.insert(0, project_root)


