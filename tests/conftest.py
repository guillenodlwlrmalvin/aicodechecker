import os
import sys

# Ensure the project root (where app.py resides) is on sys.path for tests
PROJECT_ROOT_CANDIDATES = [
    os.path.dirname(os.path.dirname(__file__)),  # one level up from tests/
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # two up (in case of nested copies)
]

for candidate in PROJECT_ROOT_CANDIDATES:
    if candidate and os.path.isfile(os.path.join(candidate, 'app.py')):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
        break


