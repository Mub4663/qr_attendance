from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response
from database import query_db, execute_db
from io import StringIO
import csv

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')
admin_bp   = Blueprint('admin',   __name__, url_prefix='/admin')


def lecturer_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') not in ('lecturer', 'admin'):
            flash('Access denied.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
#  EXPORT ATTENDANCE AS CSV
# ─────────────────────────────────────────────
@reports_bp.route('/export/csv/<int:course_id>')
@lecturer_required
def export_csv(course_id):
    course = query_db("SELECT * FROM courses WHERE id=?", (course_id,), one=True)
    if not course:
        flash('Course not found.', 'danger')
        return redirect(url_for('lecturer.dashboard'))

    records = query_db(
        """SELECT st.name, st.reg_no, st.department,
                  a.timestamp, a.status, s.created_at as session_date
           FROM attendance a
           JOIN students st  ON a.student_id  = st.id
           JOIN sessions s   ON a.session_id  = s.id
           WHERE s.course_id=?
           ORDER BY s.created_at, st.name""",
        (course_id,)
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Reg No', 'Department', 'Session Date', 'Time', 'Status'])
    for r in records:
        writer.writerow([r['name'], r['reg_no'], r['department'],
                         r['session_date'][:10], r['timestamp'][11:19], r['status']])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={course["code"]}_attendance.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response


# ─────────────────────────────────────────────
#  ATTENDANCE SUMMARY REPORT
# ─────────────────────────────────────────────
@reports_bp.route('/summary/<int:course_id>')
@lecturer_required
def summary(course_id):
    course = query_db("SELECT * FROM courses WHERE id=?", (course_id,), one=True)

    enrolled_students = query_db(
        """SELECT st.name, st.reg_no, st.department
           FROM enrollments e JOIN students st ON e.student_id = st.id
           WHERE e.course_id=?
           ORDER BY st.name""",
        (course_id,)
    )

    total_sessions = query_db(
        "SELECT COUNT(*) as cnt FROM sessions WHERE course_id=?",
        (course_id,), one=True
    )['cnt']

    student_stats = []
    for st in enrolled_students:
        attended = query_db(
            """SELECT COUNT(*) as cnt FROM attendance a
               JOIN sessions s ON a.session_id = s.id
               WHERE s.course_id=? AND a.student_id=(
                   SELECT id FROM students WHERE reg_no=?
               )""",
            (course_id, st['reg_no']), one=True
        )['cnt']

        pct = round((attended / total_sessions * 100) if total_sessions > 0 else 0, 1)
        student_stats.append({
            'name':           st['name'],
            'reg_no':         st['reg_no'],
            'department':     st['department'],
            'attended':       attended,
            'total_sessions': total_sessions,
            'percentage':     pct,
            'status':         'OK' if pct >= 75 else 'LOW'
        })

    return render_template('reports.html',
                           course=course,
                           student_stats=student_stats,
                           total_sessions=total_sessions)


# ─────────────────────────────────────────────
#  ADMIN DASHBOARD
# ─────────────────────────────────────────────
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    total_students  = query_db("SELECT COUNT(*) as cnt FROM students",  one=True)['cnt']
    total_lecturers = query_db("SELECT COUNT(*) as cnt FROM lecturers", one=True)['cnt']
    total_courses   = query_db("SELECT COUNT(*) as cnt FROM courses",   one=True)['cnt']
    total_sessions  = query_db("SELECT COUNT(*) as cnt FROM sessions",  one=True)['cnt']
    total_attendance= query_db("SELECT COUNT(*) as cnt FROM attendance",one=True)['cnt']

    recent_sessions = query_db(
        """SELECT s.created_at, s.expires_at, s.is_active,
                  c.code, c.name as course_name, l.name as lecturer_name,
                  COUNT(a.id) as count
           FROM sessions s
           JOIN courses c ON s.course_id = c.id
           JOIN lecturers l ON c.lecturer_id = l.id
           LEFT JOIN attendance a ON s.id = a.session_id
           GROUP BY s.id
           ORDER BY s.created_at DESC LIMIT 10"""
    )

    return render_template('admin_dashboard.html',
                           total_students=total_students,
                           total_lecturers=total_lecturers,
                           total_courses=total_courses,
                           total_sessions=total_sessions,
                           total_attendance=total_attendance,
                           recent_sessions=recent_sessions,
                           name=session['user_name'])


# ─────────────────────────────────────────────
#  ADMIN — REGISTER LECTURER
# ─────────────────────────────────────────────
@admin_bp.route('/add_lecturer', methods=['POST'])
@admin_required
def add_lecturer():
    import hashlib
    name       = request.form.get('name', '').strip()
    staff_id   = request.form.get('staff_id', '').strip().upper()
    email      = request.form.get('email', '').strip().lower()
    department = request.form.get('department', '').strip()
    password   = hashlib.sha256(request.form.get('password', '').encode()).hexdigest()

    existing = query_db(
        "SELECT id FROM lecturers WHERE staff_id=? OR email=?",
        (staff_id, email), one=True
    )
    if existing:
        flash('Staff ID or email already exists.', 'danger')
    else:
        execute_db(
            "INSERT INTO lecturers (name, staff_id, email, password, department) VALUES (?,?,?,?,?)",
            (name, staff_id, email, password, department)
        )
        flash(f'Lecturer {name} added successfully.', 'success')

    return redirect(url_for('admin.dashboard'))
