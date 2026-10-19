from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import hashlib
from database import query_db, execute_db

auth_bp = Blueprint('auth', __name__)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ─────────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────────
@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = hash_password(request.form.get('password', ''))
        role     = request.form.get('role', '')

        if role == 'admin':
            user = query_db(
                "SELECT * FROM admins WHERE email=? AND password=?",
                (email, password), one=True
            )
        elif role == 'lecturer':
            user = query_db(
                "SELECT * FROM lecturers WHERE email=? AND password=?",
                (email, password), one=True
            )
        elif role == 'student':
            user = query_db(
                "SELECT * FROM students WHERE email=? AND password=?",
                (email, password), one=True
            )
        else:
            user = None

        if user:
            session['user_id']   = user['id']
            session['user_name'] = user['name']
            session['role']      = role
            return redirect(url_for('auth.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')


# ─────────────────────────────────────────────
#  REGISTER STUDENT
# ─────────────────────────────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name       = request.form.get('name', '').strip()
        reg_no     = request.form.get('reg_no', '').strip().upper()
        email      = request.form.get('email', '').strip().lower()
        password   = hash_password(request.form.get('password', ''))
        department = request.form.get('department', '').strip()
        level      = request.form.get('level', '').strip()

        # Check if reg_no or email already exists
        existing = query_db(
            "SELECT id FROM students WHERE reg_no=? OR email=?",
            (reg_no, email), one=True
        )
        if existing:
            flash('Registration number or email already exists.', 'danger')
        else:
            execute_db(
                "INSERT INTO students (name, reg_no, email, password, department, level) VALUES (?,?,?,?,?,?)",
                (name, reg_no, email, password, department, level)
            )
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('register.html')


# ─────────────────────────────────────────────
#  DASHBOARD REDIRECT
# ─────────────────────────────────────────────
@auth_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif role == 'lecturer':
        return redirect(url_for('lecturer.dashboard'))
    elif role == 'student':
        return redirect(url_for('student.dashboard'))
    return redirect(url_for('auth.login'))


# ─────────────────────────────────────────────
#  LOGOUT
# ─────────────────────────────────────────────
@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
