import os
import tempfile

from models import (
    initialize_database,
    create_user,
    get_user_by_username,
    get_user_count,
    create_uploaded_file,
    get_uploaded_files,
    create_analysis,
    get_recent_analyses,
)


def test_models_crud_flow(tmp_path):
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    initialize_database(db_path)

    # user
    uid = create_user(db_path, 'alice', 'hash', is_admin=True, is_approved=True)
    assert uid > 0
    assert get_user_count(db_path) == 1
    user = get_user_by_username(db_path, 'alice')
    assert user and user['username'] == 'alice'

    # file
    fid = create_uploaded_file(db_path, uid, 'code.py', 'code.py', 5, 'py', 'print(1)')
    assert fid > 0
    files = get_uploaded_files(db_path, uid)
    assert len(files) == 1

    # analysis
    aid = create_analysis(db_path, uid, 'print(1)', 'python', 'Human', 20.0, True, [], file_id=fid)
    assert aid > 0
    hist = get_recent_analyses(db_path, uid)
    assert len(hist) == 1
    assert hist[0]['file_id'] == fid


