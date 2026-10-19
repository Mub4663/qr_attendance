from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from database import query_db, execute_db
from datetime import datetime

student_bp = Blueprint('student', __name__, url_prefix='/student')

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'student':
            flash('Please login as a student.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────
@student_bp.route('/dashboard')
@login_required
def dashboard():
    student_id = session['user_id']

    # Courses the student is enrolled in
    courses = query_db(
        """SELECT c.*, l.name as lecturer_name
           FROM enrollments e
           JOIN courses c ON e.course_id = c.id
           JOIN lecturers l ON c.lecturer_id = l.id
           WHERE e.student_id=?""",
        (student_id,)
    )

    # Attendance summary per course
    summary = []
    for course in courses:
        total_sessions = query_db(
            "SELECT COUNT(*) as cnt FROM sessions WHERE course_id=?",
            (course['id'],), one=True
        )['cnt']

        attended = query_db(
            """SELECT COUNT(*) as cnt FROM attendance a
               JOIN sessions s ON a.session_id = s.id
               WHERE s.course_id=? AND a.student_id=?""",
            (course['id'], student_id), one=True
        )['cnt']

        percentage = round((attended / total_sessions * 100) if total_sessions > 0 else 0, 1)

        summary.append({
            'course': course,
            'total_sessions': total_sessions,
            'attended': attended,
            'percentage': percentage
        })

    # Recent attendance records
    recent = query_db(
        """SELECT c.code, c.name as course_name, a.timestamp, a.status
           FROM attendance a
           JOIN sessions s ON a.session_id = s.id
           JOIN courses c ON s.course_id = c.id
           WHERE a.student_id=?
           ORDER BY a.timestamp DESC LIMIT 10""",
        (student_id,)
    )

    return render_template('student_dashboard.html',
                           summary=summary,
                           recent=recent,
                           name=session['user_name'])


# ─────────────────────────────────────────────
#  ENROLL IN COURSE
# ─────────────────────────────────────────────
@student_bp.route('/enroll', methods=['GET', 'POST'])
@login_required
def enroll():
    if request.method == 'POST':
        course_code = request.form.get('course_code', '').strip().upper()
        course = query_db("SELECT * FROM courses WHERE code=?", (course_code,), one=True)

        if not course:
            flash(f'Course {course_code} not found.', 'danger')
        else:
            existing = query_db(
                "SELECT id FROM enrollments WHERE student_id=? AND course_id=?",
                (session['user_id'], course['id']), one=True
            )
            if existing:
                flash(f'You are already enrolled in {course_code}.', 'warning')
            else:
                execute_db(
                    "INSERT INTO enrollments (student_id, course_id) VALUES (?,?)",
                    (session['user_id'], course['id'])
                )
                flash(f'Successfully enrolled in {course["name"]}!', 'success')
        return redirect(url_for('student.dashboard'))

    return render_template('enroll.html')


# ─────────────────────────────────────────────
#  SCAN QR CODE (via URL from QR code)
# ─────────────────────────────────────────────
@student_bp.route('/scan/<token>')
@login_required
def scan(token):
    student_id = session['user_id']
    now = datetime.now()

    # Find the session for this token
    sess = query_db(
        """SELECT s.*, c.code, c.name as course_name, c.id as course_id
           FROM sessions s JOIN courses c ON s.course_id = c.id
           WHERE s.qr_token=?""",
        (token,), one=True
    )

    if not sess:
        return render_template('scan_result.html',
                               success=False,
                               message='Invalid QR Code.')

    # Check if QR is active
    if not sess['is_active']:
        return render_template('scan_result.html',
                               success=False,
                               message='This QR Code has been deactivated.')

    # Check if expired
    expires_at = datetime.strptime(sess['expires_at'], '%Y-%m-%d %H:%M:%S')
    if now > expires_at:
        execute_db("UPDATE sessions SET is_active=0 WHERE id=?", (sess['id'],))
        return render_template('scan_result.html',
                               success=False,
                               message='QR Code has expired. Ask your lecturer to generate a new one.')

    # Check if student is enrolled in this course
    enrolled = query_db(
        "SELECT id FROM enrollments WHERE student_id=? AND course_id=?",
        (student_id, sess['course_id']), one=True
    )
    if not enrolled:
        return render_template('scan_result.html',
                               success=False,
                               message=f'You are not enrolled in {sess["code"]}. Please enroll first.')

    # Check if already marked
    already = query_db(
        "SELECT id FROM attendance WHERE student_id=? AND session_id=?",
        (student_id, sess['id']), one=True
    )
    if already:
        return render_template('scan_result.html',
                               success=False,
                               message=f'You have already marked attendance for {sess["code"]} today.')

    # Mark attendance ✅
    execute_db(
        "INSERT INTO attendance (student_id, session_id, status) VALUES (?,?,?)",
        (student_id, sess['id'], 'present')
    )

    return render_template('scan_result.html',
                           success=True,
                           message=f'Attendance marked for {sess["course_name"]} ({sess["code"]})!',
                           time=now.strftime('%H:%M:%S'),
                           date=now.strftime('%A, %d %B %Y'))


# ─────────────────────────────────────────────
#  MANUAL SCAN PAGE (enter token manually)
# ─────────────────────────────────────────────
@student_bp.route('/scan_manual', methods=['GET', 'POST'])
@login_required
def scan_manual():
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        return redirect(url_for('student.scan', token=token))
    return render_template('scan.html')


# ─────────────────────────────────────────────
#  FULL ATTENDANCE HISTORY
# ─────────────────────────────────────────────
@student_bp.route('/history')
@login_required
def history():
    student_id = session['user_id']
    records = query_db(
        """SELECT c.code, c.name as course_name, a.timestamp, a.status,
                  l.name as lecturer_name
           FROM attendance a
           JOIN sessions s ON a.session_id = s.id
           JOIN courses c ON s.course_id = c.id
           JOIN lecturers l ON c.lecturer_id = l.id
           WHERE a.student_id=?
           ORDER BY a.timestamp DESC""",
        (student_id,)
    )
    return render_template('student_history.html',
                           records=records,
                           name=session['user_name'])
