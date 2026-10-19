import sqlite3
import os
from config import Config

def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row  # allows dict-like access: row['name']
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    cursor = conn.cursor()

    # ── ADMINS ──────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            email       TEXT    UNIQUE NOT NULL,
            password    TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    ''')

    # ── LECTURERS ───────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lecturers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            staff_id    TEXT    UNIQUE NOT NULL,
            email       TEXT    UNIQUE NOT NULL,
            password    TEXT    NOT NULL,
            department  TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    ''')

    # ── STUDENTS ────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            reg_no      TEXT    UNIQUE NOT NULL,
            email       TEXT    UNIQUE NOT NULL,
            password    TEXT    NOT NULL,
            department  TEXT    NOT NULL,
            level       TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    ''')

    # ── COURSES ─────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT    UNIQUE NOT NULL,
            name        TEXT    NOT NULL,
            lecturer_id INTEGER NOT NULL,
            department  TEXT    NOT NULL,
            level       TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (lecturer_id) REFERENCES lecturers(id)
        )
    ''')

    # ── SESSIONS (each class = one session with unique QR) ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id   INTEGER NOT NULL,
            qr_token    TEXT    UNIQUE NOT NULL,
            qr_image    TEXT,
            created_at  TEXT    DEFAULT (datetime('now')),
            expires_at  TEXT    NOT NULL,
            is_active   INTEGER DEFAULT 1,
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    ''')

    # ── ATTENDANCE ──────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  INTEGER NOT NULL,
            session_id  INTEGER NOT NULL,
            timestamp   TEXT    DEFAULT (datetime('now')),
            status      TEXT    DEFAULT 'present',
            UNIQUE(student_id, session_id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    ''')

    # ── COURSE ENROLLMENTS ──────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS enrollments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  INTEGER NOT NULL,
            course_id   INTEGER NOT NULL,
            enrolled_at TEXT    DEFAULT (datetime('now')),
            UNIQUE(student_id, course_id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id)  REFERENCES courses(id)
        )
    ''')

    conn.commit()

    # ── Seed default admin ──────────────────────────────────
    import hashlib
    admin_pass = hashlib.sha256('admin123'.encode()).hexdigest()
    try:
        cursor.execute(
            "INSERT INTO admins (name, email, password) VALUES (?, ?, ?)",
            ('Administrator', 'admin@adustech.edu.ng', admin_pass)
        )
        conn.commit()
        print("✅ Default admin created → email: admin@adustech.edu.ng | password: admin123")
    except sqlite3.IntegrityError:
        pass   # admin already exists

    conn.close()
    print("✅ Database initialised successfully.")


def query_db(sql, args=(), one=False):
    """Run a SELECT query and return results."""
    conn = get_db()
    cur = conn.execute(sql, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(sql, args=()):
    """Run INSERT / UPDATE / DELETE and return lastrowid."""
    conn = get_db()
    cur = conn.execute(sql, args)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id
