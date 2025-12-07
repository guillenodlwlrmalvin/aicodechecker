import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime
import json


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                is_approved INTEGER NOT NULL DEFAULT 0,
                reset_requested INTEGER NOT NULL DEFAULT 0,
                role TEXT NOT NULL DEFAULT 'student'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                language TEXT,
                heuristic_label TEXT,
                heuristic_score REAL,
                check_ok INTEGER,
                check_errors TEXT,
                file_id INTEGER,
                content_type TEXT DEFAULT 'code',
                text_label TEXT,
                text_score REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(file_id) REFERENCES uploaded_files(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                teacher_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(teacher_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                FOREIGN KEY(group_id) REFERENCES groups(id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                UNIQUE(group_id, user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                content TEXT NOT NULL,
                activity_type TEXT NOT NULL DEFAULT 'text',
                created_at TEXT NOT NULL,
                due_date TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(group_id) REFERENCES groups(id),
                FOREIGN KEY(teacher_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                uploaded_by INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY(uploaded_by) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                content TEXT,
                file_id INTEGER,
                submitted_at TEXT NOT NULL,
                grade REAL,
                feedback TEXT,
                status TEXT NOT NULL DEFAULT 'submitted',
                FOREIGN KEY(activity_id) REFERENCES activities(id),
                FOREIGN KEY(student_id) REFERENCES users(id),
                FOREIGN KEY(file_id) REFERENCES uploaded_files(id),
                UNIQUE(activity_id, student_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                related_id INTEGER,
                related_type TEXT,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        # Migration: ensure columns exist
        cols = conn.execute("PRAGMA table_info(users)").fetchall()
        col_names = {c[1] for c in cols}
        if 'is_admin' not in col_names:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        if 'is_approved' not in col_names:
            conn.execute("ALTER TABLE users ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 0")
        if 'reset_requested' not in col_names:
            conn.execute("ALTER TABLE users ADD COLUMN reset_requested INTEGER NOT NULL DEFAULT 0")
        if 'role' not in col_names:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")
            # Migrate existing users: set role based on is_admin
            conn.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
            conn.execute("UPDATE users SET role = 'student' WHERE is_admin = 0")
        # Store email verification token/code for self-service verification
        if 'verification_token' not in col_names:
            conn.execute("ALTER TABLE users ADD COLUMN verification_token TEXT")
        # Store verification code expiration time
        if 'verification_code_expires' not in col_names:
            conn.execute("ALTER TABLE users ADD COLUMN verification_code_expires TEXT")
        # Google OAuth columns
        if 'google_id' not in col_names:
            conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
        if 'avatar' not in col_names:
            conn.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
        
        # Migration: ensure analysis table columns exist
        analysis_cols = conn.execute("PRAGMA table_info(analyses)").fetchall()
        analysis_col_names = {c[1] for c in analysis_cols}
        if 'content_type' not in analysis_col_names:
            conn.execute("ALTER TABLE analyses ADD COLUMN content_type TEXT DEFAULT 'code'")
        if 'text_label' not in analysis_col_names:
            conn.execute("ALTER TABLE analyses ADD COLUMN text_label TEXT")
        if 'text_score' not in analysis_col_names:
            conn.execute("ALTER TABLE analyses ADD COLUMN text_score REAL")
        
        # Migration: ensure uploaded_files table has content_type column
        try:
            uploaded_files_cols = conn.execute("PRAGMA table_info(uploaded_files)").fetchall()
            uploaded_files_col_names = {c[1] for c in uploaded_files_cols}
            if 'content_type' not in uploaded_files_col_names:
                conn.execute("ALTER TABLE uploaded_files ADD COLUMN content_type TEXT NOT NULL DEFAULT 'application/octet-stream'")
        except sqlite3.OperationalError:
            # Table doesn't exist yet, will be created with proper schema
            pass
        
        # Migration: ensure activity_submissions has AI analysis columns
        try:
            submission_cols = conn.execute("PRAGMA table_info(activity_submissions)").fetchall()
            submission_col_names = {c[1] for c in submission_cols}
            if 'ai_label' not in submission_col_names:
                conn.execute("ALTER TABLE activity_submissions ADD COLUMN ai_label TEXT")
            if 'ai_score' not in submission_col_names:
                conn.execute("ALTER TABLE activity_submissions ADD COLUMN ai_score REAL")
            if 'ai_explanation' not in submission_col_names:
                conn.execute("ALTER TABLE activity_submissions ADD COLUMN ai_explanation TEXT")
        except sqlite3.OperationalError:
            # Table might not exist yet; creation above will include these columns next run
            pass
        
        conn.commit()
    finally:
        conn.close()


def get_user_by_username(db_path: str, username: str) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_google_id(db_path: str, google_id: str) -> Optional[Dict[str, Any]]:
    """Lookup user by Google OAuth subject identifier."""
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(db_path: str, user_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_count(db_path: str) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(1) as c FROM users").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def create_user(db_path: str, username: str, password_hash: str, is_admin: bool = False, is_approved: bool = False, role: str = 'student') -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, created_at, is_admin, is_approved, role) VALUES (?, ?, ?, ?, ?, ?)",
            (
                username,
                password_hash,
                datetime.utcnow().isoformat(),
                1 if is_admin else 0,
                1 if is_approved else 0,
                role,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def upsert_user_from_google(
    db_path: str,
    google_id: str,
    email: str,
    name: str,
    avatar: Optional[str] = None,
) -> tuple[Dict[str, Any], bool]:
    """
    Create or update a user based on Google OAuth information.
    Returns: (user_dict, is_new_user)
    - If a user with google_id exists, return it (is_new_user=False).
    - Else if a user with matching email exists, link google_id + avatar and mark verified (is_new_user=False).
    - Else create a new user (auto-approved) with a placeholder password (is_new_user=True).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Connecting to database: {db_path}")
        conn = _connect(db_path)
        
        # 1) Existing Google-linked user
        logger.debug(f"Checking for existing Google user with google_id: {google_id[:20]}...")
        cur = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
        row = cur.fetchone()
        if row:
            logger.info(f"Found existing Google-linked user: {row['username']}")
            return dict(row), False

        # 2) Existing email-based user
        logger.debug(f"Checking for existing user with email: {email}")
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (email,))
        row = cur.fetchone()
        if row:
            logger.info(f"Found existing email-based user: {email}, linking Google account")
            user_id = row['id']
            # Don't auto-approve when linking - keep existing approval status
            try:
                conn.execute(
                    "UPDATE users SET google_id = ?, avatar = ? WHERE id = ?",
                    (google_id, avatar, user_id),
                )
                conn.commit()
                logger.info(f"✓ Successfully linked Google account to user ID {user_id}")
                cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                return dict(cur.fetchone()), False
            except Exception as e:
                logger.error(f"✗ Failed to update user with Google info: {e}", exc_info=True)
                conn.rollback()
                raise

        # 3) New user – requires email verification (NOT auto-approved)
        logger.info(f"Creating new Google user: {email}")
        placeholder_password = ''  # password not used for Google-only accounts
        import random
        from datetime import timedelta
        verification_code = str(random.randint(100000, 999999))  # Generate 6-digit code
        expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()  # 10 minutes expiration
        try:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, created_at, is_admin, is_approved, role, google_id, avatar, verification_token, verification_code_expires)
                VALUES (?, ?, ?, 0, 0, 'student', ?, ?, ?, ?)
                """,
                (
                    email,
                    placeholder_password,
                    datetime.utcnow().isoformat(),
                    google_id,
                    avatar,
                    verification_code,
                    expires_at,
                ),
            )
            user_id = cur.lastrowid
            conn.commit()
            logger.info(f"✓ Successfully created new Google user with ID: {user_id} (requires verification)")
            cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user_dict = dict(cur.fetchone())
            logger.info(f"✓ Retrieved user data for ID {user_id}: username={user_dict.get('username')}")
            return user_dict, True
        except Exception as e:
            logger.error(f"✗ Failed to create new Google user: {e}", exc_info=True)
            conn.rollback()
            raise
    except Exception as e:
        logger.error(f"✗ Database error in upsert_user_from_google: {e}", exc_info=True)
        raise
    finally:
        if 'conn' in locals():
            conn.close()
            logger.debug("Database connection closed")


def set_user_verification_token(db_path: str, user_id: int, token: str, expires_at: str = None) -> None:
    """Set or update the email verification token/code for a user."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE users SET verification_token = ?, verification_code_expires = ? WHERE id = ?",
            (token, expires_at, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_verification_token(db_path: str, token: str) -> Optional[Dict[str, Any]]:
    """Look up a user by their email verification token/code."""
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT * FROM users WHERE verification_token = ?", (token,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_verification_code(db_path: str, code: str) -> Optional[Dict[str, Any]]:
    """Look up a user by their 6-digit verification code and check if it's expired."""
    from datetime import datetime
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT * FROM users WHERE verification_token = ?", (code,))
        row = cur.fetchone()
        if not row:
            return None
        
        user = dict(row)
        expires_at = user.get('verification_code_expires')
        
        # Check if code has expired
        if expires_at:
            try:
                expires = datetime.fromisoformat(expires_at)
                if datetime.utcnow() > expires:
                    return None  # Code expired
            except (ValueError, TypeError):
                pass  # Invalid date format, treat as not expired for backward compatibility
        
        return user
    finally:
        conn.close()


def mark_user_verified(db_path: str, user_id: int) -> None:
    """Mark user as verified (is_approved=1) and clear token/code."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE users SET is_approved = 1, verification_token = NULL, verification_code_expires = NULL WHERE id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def update_user_password(db_path: str, user_id: int, password_hash: str) -> None:
    """Update a user's password hash."""
    import logging
    logger = logging.getLogger(__name__)
    
    conn = _connect(db_path)
    try:
        logger.info(f"Updating password for user_id: {user_id}, hash_length: {len(password_hash) if password_hash else 0}")
        result = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
        logger.info(f"Password update executed, rows affected: {result.rowcount}")
        
        # Verify the update
        cur = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            saved_hash = row['password_hash']
            logger.info(f"Password saved successfully, saved_hash_length: {len(saved_hash) if saved_hash else 0}")
            if saved_hash != password_hash:
                logger.error(f"Password hash mismatch! Expected length: {len(password_hash)}, Saved length: {len(saved_hash) if saved_hash else 0}")
        else:
            logger.error(f"User {user_id} not found after password update")
    except Exception as e:
        logger.error(f"Error updating password: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def create_uploaded_file(db_path: str, user_id: int, filename: str, original_filename: str,
                        file_size: int, file_type: str, content: str) -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO uploaded_files (user_id, filename, original_filename, file_size, file_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                filename,
                original_filename,
                file_size,
                file_type,
                content,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_uploaded_files(db_path: str, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT * FROM uploaded_files
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def create_analysis(db_path: str, user_id: int, code: str, language: str,
                    heuristic_label: str, heuristic_score: float,
                    check_ok: bool, check_errors: List[str], file_id: Optional[int] = None,
                    content_type: str = 'code', text_label: Optional[str] = None, 
                    text_score: Optional[float] = None) -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO analyses (user_id, code, language, heuristic_label, heuristic_score, check_ok, check_errors, file_id, content_type, text_label, text_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                code,
                language,
                heuristic_label,
                float(heuristic_score),
                1 if check_ok else 0,
                json.dumps(check_errors or []),
                file_id,
                content_type,
                text_label,
                text_score,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_recent_analyses(db_path: str, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT a.*, uf.original_filename
            FROM analyses a
            LEFT JOIN uploaded_files uf ON a.file_id = uf.id
            WHERE a.user_id = ?
            ORDER BY a.created_at DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_analysis_by_id(db_path: str, user_id: int, analysis_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT a.*, uf.original_filename
            FROM analyses a
            LEFT JOIN uploaded_files uf ON a.file_id = uf.id
            WHERE a.user_id = ? AND a.id = ?
            """,
            (user_id, analysis_id)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_all_users(db_path: str) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT id, username, created_at, is_admin, is_approved, reset_requested, role FROM users ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def delete_user_and_related(db_path: str, user_id: int) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM analyses WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM uploaded_files WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def approve_user(db_path: str, user_id: int) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("UPDATE users SET is_approved = 1 WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def update_user_role(db_path: str, user_id: int, role: str) -> None:
    """Update user role and sync is_admin field"""
    conn = _connect(db_path)
    try:
        is_admin = 1 if role == 'admin' else 0
        conn.execute("UPDATE users SET role = ?, is_admin = ? WHERE id = ?", (role, is_admin, user_id))
        conn.commit()
    finally:
        conn.close()


# Group Management Functions
def create_group(db_path: str, name: str, description: str, teacher_id: int) -> int:
    """Create a new group/section"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO groups (name, description, teacher_id, created_at) VALUES (?, ?, ?, ?)",
            (name, description, teacher_id, datetime.utcnow().isoformat())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_teacher_groups(db_path: str, teacher_id: int) -> List[Dict[str, Any]]:
    """Get all groups created by a teacher"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT * FROM groups WHERE teacher_id = ? ORDER BY created_at DESC",
            (teacher_id,)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_group_by_id(db_path: str, group_id: int) -> Optional[Dict[str, Any]]:
    """Get group by ID"""
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_group_members(db_path: str, group_id: int) -> List[Dict[str, Any]]:
    """Get all members of a group"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT gm.*, u.username, u.role, u.is_approved
            FROM group_members gm
            JOIN users u ON gm.user_id = u.id
            WHERE gm.group_id = ?
            ORDER BY gm.joined_at DESC
            """,
            (group_id,)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def join_group(db_path: str, group_id: int, user_id: int) -> bool:
    """Student joins a group"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO group_members (group_id, user_id, joined_at) VALUES (?, ?, ?)",
            (group_id, user_id, datetime.utcnow().isoformat())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # User already in group
        return False
    finally:
        conn.close()


def approve_group_member(db_path: str, group_id: int, user_id: int) -> None:
    """Teacher approves a group member"""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE group_members SET status = 'approved' WHERE group_id = ? AND user_id = ?",
            (group_id, user_id)
        )
        conn.commit()
    finally:
        conn.close()


def decline_group_member(db_path: str, group_id: int, user_id: int) -> None:
    """Teacher declines a group member"""
    conn = _connect(db_path)
    try:
        conn.execute(
            "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_group(db_path: str, group_id: int) -> None:
    """Delete a group and all related data (cascade delete)"""
    conn = _connect(db_path)
    try:
        # Get all activity IDs for this group first
        activity_ids = conn.execute(
            "SELECT id FROM activities WHERE group_id = ?",
            (group_id,)
        ).fetchall()
        
        # Delete activity submissions (references activities)
        for activity_id in activity_ids:
            conn.execute(
                "DELETE FROM activity_submissions WHERE activity_id = ?",
                (activity_id[0],)
            )
        
        # Delete activities (references groups)
        conn.execute("DELETE FROM activities WHERE group_id = ?", (group_id,))
        
        # Delete group members (references groups)
        conn.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
        
        # Finally delete the group
        conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        
        conn.commit()
    finally:
        conn.close()


# Activity Management Functions
def create_activity(db_path: str, group_id: int, teacher_id: int, title: str, 
                   description: str, content: str, activity_type: str = 'text', 
                   due_date: Optional[str] = None) -> int:
    """Create a new activity"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO activities (group_id, teacher_id, title, description, content, activity_type, created_at, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (group_id, teacher_id, title, description, content, activity_type, 
             datetime.utcnow().isoformat(), due_date)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_activity_by_id(db_path: str, activity_id: int) -> Optional[Dict[str, Any]]:
    """Get a single activity by ID"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT * FROM activities WHERE id = ?",
            (activity_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_group_activities(db_path: str, group_id: int) -> List[Dict[str, Any]]:
    """Get all activities for a group"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT * FROM activities WHERE group_id = ? ORDER BY created_at DESC",
            (group_id,)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_student_activities(db_path: str, student_id: int) -> List[Dict[str, Any]]:
    """Get all activities for a student (from their groups) with submission flag"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT a.*, g.name as group_name, gm.status as membership_status,
                   CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END AS has_submitted,
                   s.submitted_at
            FROM activities a
            JOIN groups g ON a.group_id = g.id
            JOIN group_members gm ON g.id = gm.group_id
            LEFT JOIN activity_submissions s
                   ON s.activity_id = a.id AND s.student_id = ?
            WHERE gm.user_id = ? AND gm.status = 'approved' AND a.is_active = 1
            ORDER BY a.created_at DESC
            """,
            (student_id, student_id)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def save_uploaded_file(db_path: str, filename: str, original_filename: str, file_path: str, file_size: int, content_type: str, uploaded_by: int) -> int:
    """Save uploaded file information to database"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO uploaded_files (filename, original_filename, file_path, file_size, content_type, uploaded_by, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (filename, original_filename, file_path, file_size, content_type, uploaded_by, datetime.utcnow().isoformat())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_uploaded_file(db_path: str, file_id: int) -> Optional[Dict[str, Any]]:
    """Get uploaded file information by ID"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT * FROM uploaded_files WHERE id = ?",
            (file_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def submit_activity(db_path: str, activity_id: int, student_id: int, content: str = None, file_id: int = None) -> int:
    """Student submits an activity exactly once; raises on duplicates."""
    conn = _connect(db_path)
    try:
        # Check for existing submission
        existing = conn.execute(
            "SELECT id FROM activity_submissions WHERE activity_id = ? AND student_id = ?",
            (activity_id, student_id)
        ).fetchone()
        if existing:
            raise ValueError("Submission already exists for this activity")
        
        # Validate that either content or file_id is provided
        if not content and not file_id:
            raise ValueError("Either content or file must be provided")
        
        cur = conn.execute(
            """
            INSERT INTO activity_submissions (activity_id, student_id, content, file_id, submitted_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (activity_id, student_id, content, file_id, datetime.utcnow().isoformat())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_submission_analysis(db_path: str, submission_id: int, ai_label: str, ai_score: float, ai_explanation: str) -> None:
    """Attach AI/human analysis results to an existing activity submission."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            UPDATE activity_submissions
            SET ai_label = ?, ai_score = ?, ai_explanation = ?
            WHERE id = ?
            """,
            (ai_label, ai_score, ai_explanation, submission_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_activity_submissions(db_path: str, activity_id: int) -> List[Dict[str, Any]]:
    """Get all submissions for an activity"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT s.*, u.username, f.original_filename, f.file_size, f.content_type, f.content as file_content
            FROM activity_submissions s
            JOIN users u ON s.student_id = u.id
            LEFT JOIN uploaded_files f ON s.file_id = f.id
            WHERE s.activity_id = ?
            ORDER BY s.submitted_at DESC
            """,
            (activity_id,)
        )
        rows = cur.fetchall()
        submissions = [dict(row) for row in rows]
        # Combine content: use text content if available, otherwise use file content
        for submission in submissions:
            if submission.get('content'):
                submission['code_content'] = submission['content']
            elif submission.get('file_content'):
                submission['code_content'] = submission['file_content']
            else:
                submission['code_content'] = ''
        return submissions
    finally:
        conn.close()


def get_student_submissions(db_path: str, student_id: int) -> List[Dict[str, Any]]:
    """Get all submissions by a student"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT s.*, a.title as activity_title, g.name as group_name, f.original_filename, f.file_size, f.content_type
            FROM activity_submissions s
            JOIN activities a ON s.activity_id = a.id
            JOIN groups g ON a.group_id = g.id
            LEFT JOIN uploaded_files f ON s.file_id = f.id
            WHERE s.student_id = ?
            ORDER BY s.submitted_at DESC
            """,
            (student_id,)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def grade_submission(db_path: str, submission_id: int, grade: float, feedback: str) -> None:
    """Teacher grades a submission"""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE activity_submissions SET grade = ?, feedback = ? WHERE id = ?",
            (grade, feedback, submission_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_student_activity_participation(db_path: str, group_id: int, student_id: int) -> List[Dict[str, Any]]:
    """Get all activities in a group and check if student has participated"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT a.id, a.title, a.activity_type, a.created_at, a.due_date,
                   CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END as has_submitted,
                   s.submitted_at, s.grade, s.status as submission_status
            FROM activities a
            LEFT JOIN activity_submissions s ON a.id = s.activity_id AND s.student_id = ?
            WHERE a.group_id = ? AND a.is_active = 1
            ORDER BY a.created_at DESC
            """,
            (student_id, group_id)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# Notification functions
def create_notification(db_path: str, user_id: int, notification_type: str, title: str, 
                       message: str, related_id: int = None, related_type: str = None) -> int:
    """Create a new notification for a user"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO notifications (user_id, type, title, message, related_id, related_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, notification_type, title, message, related_id, related_type, datetime.utcnow().isoformat())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_user_notifications(db_path: str, user_id: int, limit: int = 50, unread_only: bool = False) -> List[Dict[str, Any]]:
    """Get notifications for a user"""
    conn = _connect(db_path)
    try:
        query = """
            SELECT * FROM notifications
            WHERE user_id = ?
        """
        params = [user_id]
        
        if unread_only:
            query += " AND is_read = 0"
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_unread_notification_count(db_path: str, user_id: int) -> int:
    """Get count of unread notifications for a user"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,)
        )
        row = cur.fetchone()
        return row['count'] if row else 0
    finally:
        conn.close()


def mark_notification_as_read(db_path: str, notification_id: int, user_id: int) -> None:
    """Mark a notification as read"""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (notification_id, user_id)
        )
        conn.commit()
    finally:
        conn.close()


def mark_all_notifications_as_read(db_path: str, user_id: int) -> None:
    """Mark all notifications as read for a user"""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
    finally:
        conn.close()


def get_all_admin_users(db_path: str) -> List[Dict[str, Any]]:
    """Get all admin users"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT * FROM users WHERE is_admin = 1 OR role = 'admin'",
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_student_submission_for_activity(db_path: str, student_id: int, activity_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific student's submission for a specific activity"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT s.*, u.username
            FROM activity_submissions s
            JOIN users u ON s.student_id = u.id
            WHERE s.student_id = ? AND s.activity_id = ?
            """,
            (student_id, activity_id)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_groups(db_path: str) -> List[Dict[str, Any]]:
    """Get all groups with teacher information"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT g.*, u.username as teacher_username
            FROM groups g
            JOIN users u ON g.teacher_id = u.id
            ORDER BY g.created_at DESC
            """
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_available_groups_for_student(db_path: str, student_id: int) -> List[Dict[str, Any]]:
    """Get all groups available for a student to join (not already a member)"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT g.*, u.username as teacher_username,
                   EXISTS(SELECT 1 FROM group_members gm WHERE gm.group_id = g.id AND gm.user_id = ?) as is_member,
                   CASE 
                       WHEN EXISTS(SELECT 1 FROM group_members gm WHERE gm.group_id = g.id AND gm.user_id = ? AND gm.status = 'approved') 
                       THEN 'approved'
                       WHEN EXISTS(SELECT 1 FROM group_members gm WHERE gm.group_id = g.id AND gm.user_id = ? AND gm.status = 'pending') 
                       THEN 'pending'
                       ELSE NULL
                   END as membership_status
            FROM groups g
            JOIN users u ON g.teacher_id = u.id
            WHERE g.is_active = 1
            ORDER BY g.created_at DESC
            """,
            (student_id, student_id, student_id)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
