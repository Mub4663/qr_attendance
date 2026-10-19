from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from database import query_db, execute_db
from config import Config
import qrcode
import uuid
import os
from datetime import datetime, timedelta

lecturer_bp = Blueprint('lecturer', __name__, url_prefix='/lecturer')

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'lecturer':
            flash('Please login as a lecturer.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────
@lecturer_bp.route('/dashboard')
@login_required
def dashboard():
    lecturer_id = session['user_id']

    courses = query_db(
        "SELECT * FROM courses WHERE lecturer_id=? ORDER BY code",
        (lecturer_id,)
    )

    # Count total sessions and attendance per course
    stats = []
    for course in courses:
        total_sessions = query_db(
            "SELECT COUNT(*) as cnt FROM sessions WHERE course_id=?",
            (course['id'],), one=True
        )['cnt']

        total_attendance = query_db(
            """SELECT COUNT(*) as cnt FROM attendance a
               JOIN sessions s ON a.session_id = s.id
               WHERE s.course_id=?""",
            (course['id'],), one=True
        )['cnt']

        stats.append({
            'course': course,
            'total_sessions': total_sessions,
            'total_attendance': total_attendance
        })

    return render_template('lecturer_dashboard.html',
                           stats=stats,
                           name=session['user_name'])


# ─────────────────────────────────────────────
#  ADD COURSE
# ─────────────────────────────────────────────
@lecturer_bp.route('/add_course', methods=['POST'])
@login_required
def add_course():
    code       = request.form.get('code', '').strip().upper()
    name       = request.form.get('name', '').strip()
    department = request.form.get('department', '').strip()
    level      = request.form.get('level', '').strip()

    existing = query_db("SELECT id FROM courses WHERE code=?", (code,), one=True)
    if existing:
        flash(f'Course {code} already exists.', 'danger')
    else:
        execute_db(
            "INSERT INTO courses (code, name, lecturer_id, department, level) VALUES (?,?,?,?,?)",
            (code, name, session['user_id'], department, level)
        )
        flash(f'Course {code} added successfully.', 'success')

    return redirect(url_for('lecturer.dashboard'))


# ─────────────────────────────────────────────
#  GENERATE QR CODE
# ─────────────────────────────────────────────
@lecturer_bp.route('/generate_qr/<int:course_id>', methods=['POST'])
@login_required
def generate_qr(course_id):
    # Verify this course belongs to this lecturer
    course = query_db(
        "SELECT * FROM courses WHERE id=? AND lecturer_id=?",
        (course_id, session['user_id']), one=True
    )
    if not course:
        flash('Course not found.', 'danger')
        return redirect(url_for('lecturer.dashboard'))

    # Deactivate old active sessions for this course
    execute_db(
        "UPDATE sessions SET is_active=0 WHERE course_id=? AND is_active=1",
        (course_id,)
    )

    # Generate unique token
    token      = str(uuid.uuid4())
    now        = datetime.now()
    expires_at = now + timedelta(minutes=Config.QR_EXPIRY_MINUTES)

    # Build the scan URL
    scan_url = f"{request.host_url}student/scan/{token}"

    # Generate QR image
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    qr_filename = f"qr_{token}.png"
    qr_path = os.path.join(Config.QR_FOLDER, qr_filename)
    img.save(qr_path)

    # Save session to DB
    session_id = execute_db(
        "INSERT INTO sessions (course_id, qr_token, qr_image, expires_at) VALUES (?,?,?,?)",
        (course_id, token, qr_filename, expires_at.strftime('%Y-%m-%d %H:%M:%S'))
    )

    flash(f'QR Code generated for {course["code"]}! Valid for {Config.QR_EXPIRY_MINUTES} minutes.', 'success')
    return redirect(url_for('lecturer.view_session', session_id=session_id))


# ─────────────────────────────────────────────
#  VIEW SESSION (QR + live attendance)
# ─────────────────────────────────────────────
@lecturer_bp.route('/session/<int:session_id>')
@login_required
def view_session(session_id):
    sess = query_db(
        """SELECT s.*, c.code, c.name as course_name
           FROM sessions s JOIN courses c ON s.course_id = c.id
           WHERE s.id=?""",
        (session_id,), one=True
    )
    if not sess:
        flash('Session not found.', 'danger')
        return redirect(url_for('lecturer.dashboard'))

    attendance = query_db(
        """SELECT st.name, st.reg_no, a.timestamp, a.status
           FROM attendance a
           JOIN students st ON a.student_id = st.id
           WHERE a.session_id=?
           ORDER BY a.timestamp""",
        (session_id,)
    )

    # Check if QR is still valid
    expires_at = datetime.strptime(sess['expires_at'], '%Y-%m-%d %H:%M:%S')
    is_expired = datetime.now() > expires_at

    return render_template('session.html',
                           sess=sess,
                           attendance=attendance,
                           is_expired=is_expired,
                           qr_image=sess['qr_image'])


# ─────────────────────────────────────────────
#  AJAX: Live attendance count
# ─────────────────────────────────────────────
@lecturer_bp.route('/session/<int:session_id>/live')
@login_required
def live_count(session_id):
    count = query_db(
        "SELECT COUNT(*) as cnt FROM attendance WHERE session_id=?",
        (session_id,), one=True
    )['cnt']

    rows = query_db(
        """SELECT st.name, st.reg_no, a.timestamp
           FROM attendance a JOIN students st ON a.student_id = st.id
           WHERE a.session_id=? ORDER BY a.timestamp DESC""",
        (session_id,)
    )
    students = [dict(r) for r in rows]
    return jsonify({'count': count, 'students': students})


# ─────────────────────────────────────────────
#  COURSE ATTENDANCE HISTORY
# ─────────────────────────────────────────────
@lecturer_bp.route('/course/<int:course_id>/history')
@login_required
def course_history(course_id):
    course = query_db("SELECT * FROM courses WHERE id=?", (course_id,), one=True)

    sessions = query_db(
        """SELECT s.*, COUNT(a.id) as count
           FROM sessions s
           LEFT JOIN attendance a ON s.id = a.session_id
           WHERE s.course_id=?
           GROUP BY s.id
           ORDER BY s.created_at DESC""",
        (course_id,)
    )

    return render_template('course_history.html', course=course, sessions=sessions)
