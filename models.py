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
                created_at TEXT NOT NULL
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


def create_user(db_path: str, username: str, password_hash: str) -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, datetime.utcnow().isoformat()),
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
                    check_ok: bool, check_errors: List[str], file_id: Optional[int] = None) -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO analyses (user_id, code, language, heuristic_label, heuristic_score, check_ok, check_errors, file_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
