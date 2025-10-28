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


def get_activity_submissions(db_path: str, activity_id: int) -> List[Dict[str, Any]]:
    """Get all submissions for an activity"""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT s.*, u.username, f.original_filename, f.file_size, f.content_type
            FROM activity_submissions s
            JOIN users u ON s.student_id = u.id
            LEFT JOIN uploaded_files f ON s.file_id = f.id
            WHERE s.activity_id = ?
            ORDER BY s.submitted_at DESC
            """,
            (activity_id,)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
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
