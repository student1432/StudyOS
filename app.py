from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort, send_from_directory
from firebase_config import auth, db
from firebase_admin import auth as admin_auth, storage
from datetime import datetime, date, timedelta
from templates.academic_data import get_syllabus, get_available_subjects, ACADEMIC_SYLLABI
from careers_data import CAREERS_DATA, COURSES_DATA, INTERNSHIPS_DATA, get_career_by_id, get_course_by_id, get_internship_by_id
from utils import (
    PasswordManager, login_rate_limiter, logger, validate_schema,
    user_registration_schema, user_login_schema, CacheManager
)
from utils.timezone import get_current_time_for_user
from config import config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_mail import Mail, Message
import os
from werkzeug.utils import secure_filename
import time
import uuid
from functools import wraps
from firebase_admin import firestore
from collections import defaultdict
import random
import string
from marshmallow import ValidationError
import traceback
# AI Assistant import
from ai_assistant import get_ai_assistant
# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()
# Initialize Flask app with configuration
env = os.environ.get('FLASK_ENV', 'production')
app = Flask(__name__)
config[env].init_app(app)
# Dedicated CSS endpoint with explicit MIME type

@app.route('/styles.css')
def serve_css():
    from flask import send_from_directory
    return send_from_directory('static', 'styles.css')
# Initialize rate limiter
disable_rate_limits = (
    env == 'development' or
    os.environ.get('DISABLE_RATE_LIMITS', 'False').lower() == 'true'
)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[config[env].RATE_LIMIT_DEFAULT],
    enabled=(not disable_rate_limits),
    storage_uri="memory://"
)
# Initialize security headers with Talisman
Talisman(app,
    force_https=config[env].SESSION_COOKIE_SECURE,
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,
    strict_transport_security_include_subdomains=True,
    content_security_policy={
        'default-src': "'self'",
        'script-src': ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://fonts.googleapis.com", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com", "https://cdn.jsdelivr.net"],
        'style-src': ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://fonts.googleapis.com", "https://fonts.gstatic.com"],
        'font-src': ["https://fonts.googleapis.com", "https://fonts.gstatic.com"],
        'img-src': ["'self'", "data:", "https:"],
        'connect-src': ["'self'", "https://cdn.jsdelivr.net"],
        'frame-ancestors': "'none'",
        'base-uri': "'self'",
        'form-action': "'self'"
    },
    referrer_policy='strict-origin-when-cross-origin'
)
user_ref = None
# Initialize Flask-Mail
mail = Mail(app)

# ============================================================================
# INSTITUTION V2 CONSTANTS / HELPERS

# ============================================================================
INSTITUTION_ADMINS_COL = 'institution_admins'
INSTITUTION_TEACHERS_COL = 'institution_teachers'
INSTITUTIONS_COL = 'institutions'
TEACHER_INVITES_COL = 'teacher_invites'
CLASSES_COL = 'classes'
CLASS_INVITES_COL = 'class_invites'

def _generate_code(length: int = 6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def _set_session_identity(uid: str, account_type: str, institution_id: str | None = None):
    session['uid'] = uid
    session['account_type'] = account_type  # 'student' | 'teacher' | 'admin'
    if institution_id:
        session['institution_id'] = institution_id
    else:
        session.pop('institution_id', None)

def _get_account_type() -> str:
    return session.get('account_type', 'student')

def require_institution_role(allowed_roles: list[str]):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'uid' not in session:
                return redirect(url_for('login'))
            account_type = _get_account_type()
            if account_type not in allowed_roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator
require_admin_v2 = require_institution_role(['admin'])
require_teacher_v2 = require_institution_role(['teacher'])

def _get_admin_profile(uid: str) -> dict | None:
    profile = _get_any_profile(uid)
    return profile if profile and profile.get('account_type') == 'admin' else None

def _get_teacher_profile(uid: str) -> dict | None:
    profile = _get_any_profile(uid)
    return profile if profile and profile.get('account_type') == 'teacher' else None

def _get_any_profile(uid: str) -> dict | None:
    """Check all identity collections and return profile + account_type."""
    # Check collections in order of specificity
    doc = db.collection(INSTITUTION_ADMINS_COL).document(uid).get()
    if doc.exists: return {**doc.to_dict(), 'account_type': 'admin'}
    doc = db.collection(INSTITUTION_TEACHERS_COL).document(uid).get()
    if doc.exists: return {**doc.to_dict(), 'account_type': 'teacher'}
    doc = db.collection('users').document(uid).get()
    if doc.exists: return {**doc.to_dict(), 'account_type': 'student'}
    return None

def _get_institution_analytics(institution_id, class_ids=None):
    """
    Common logic for real-time heatmap and at-risk predictive analytics.
    If class_ids is provided, filter students by those classes.
    """
    heatmap_data = defaultdict(int)
    at_risk_students = []
    
    if not institution_id:
        return {'heatmap': {}, 'at_risk': []}

    # 1. Fetch relevant classes
    classes_ref = db.collection(CLASSES_COL).where('institution_id', '==', institution_id)
    classes_docs = list(classes_ref.stream())
    
    if class_ids:
        classes_docs = [d for d in classes_docs if d.id in class_ids]
    
    classes_map = {d.id: d.to_dict() for d in classes_docs}
    all_student_ids = set()
    for _, c_data in classes_map.items():
        all_student_ids.update(c_data.get('student_uids', []))

    # 2. Aggregations (Heatmap)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    for sid in all_student_ids:
        sessions = db.collection('users').document(sid).collection('study_sessions')\
                     .where('start_time', '>=', thirty_days_ago.isoformat()).stream()
        for s in sessions:
            s_data = s.to_dict()
            h = s_data.get('local_hour')
            w = s_data.get('local_weekday')
            if h is not None and w is not None:
                heatmap_data[f"{w}-{h}"] += 1

    # 3. Risk Analytics
    for sid in all_student_ids:
        s_doc = db.collection('users').document(sid).get()
        if not s_doc.exists: continue
        s_data = s_doc.to_dict()
        
        # Simple Risk model
        last_str = s_data.get('last_login_date')
        status = 'healthy'
        if not last_str: status = 'stagnating'
        else:
            days = (datetime.utcnow() - datetime.fromisoformat(last_str)).days
            if days > 7: status = 'stagnating'
        
        # Velocity Momentum
        results = s_data.get('exam_results', [])
        momentum = 0
        if len(results) >= 2:
            try:
                sorted_res = sorted(results, key=lambda x: x.get('date', ''), reverse=True)
                series = [float(r.get('percentage', r.get('score', 0))) for r in sorted_res[:3]][::-1]
                momentum = series[-1] - series[0]
                if momentum < -5: status = 'critical' if status == 'stagnating' else 'declining'
            except: pass

        if status != 'healthy':
            student_class = "Unknown"
            for cid, cdata in classes_map.items():
                if sid in cdata.get('student_uids', []):
                    student_class = cdata.get('name', cid)
                    break
            at_risk_students.append({
                'uid': sid,
                'name': s_data.get('name', 'Student'),
                'class': student_class,
                'status': status,
                'momentum': round(momentum, 2)
            })

    return {
        'heatmap': dict(heatmap_data),
        'at_risk': at_risk_students
    }

def _institution_login_guard():
    """Prevent admin/teacher accounts from entering student app routes."""
    if 'uid' not in session:
        return None
    path = request.path or ''
    if path in ['/logout', '/styles.css', '/login'] or path.startswith('/static/'):
        return None
    account_type = _get_account_type()
    # Block students from V2 institution portals
    if account_type == 'student' and (path.startswith('/institution/admin') or path.startswith('/institution/teacher')):
        abort(403)
    # Allow institution routes for admin/teacher
    if path.startswith('/institution'):
        return None
    # Block admin/teacher from student app
    if account_type == 'admin':
        return redirect(url_for('institution_admin_dashboard'))
    if account_type == 'teacher':
        return redirect(url_for('institution_teacher_dashboard'))
    return None

# ============================================================================
# UTILITY FUNCTIONS - 
# ============================================================================

# ============================================================================
# STATISTICS
# ============================================================================
TEST_TYPES = [
    "Unit Test 1", "Unit Test 2", "Unit Test 3", "Unit Test 4",
    "Unit Test 5", "Unit Test 6",
    "Quarterly", "Half Yearly",
    "Pre Midterms", "Midterms", "Post Midterms",
    "1st Midterm", "2nd Midterm",
    "Pre Finals", "Finals",
    "Pre Annual", "Annual"
]

def require_login(f):
    def wrapper(*args, **kwargs):
        if 'uid' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def get_user_data(uid):
    user_doc = db.collection('users').document(uid).get()
    if user_doc.exists:
        return user_doc.to_dict()
    return None

def calculate_academic_progress(user_data, uid=None):
    """
    Calculate academic progress with 3-tier exclusion system:
    Level 1: Institution exclusions (admin)
    Level 2: Class exclusions (teacher)
    Level 3: Personal exclusions (student)
    """
    purpose = user_data.get('purpose')
    chapters_completed = user_data.get('chapters_completed', {})
    personal_exclusions = user_data.get('academic_exclusions', {})
    # Fetch institution and class exclusions
    institution_exclusions = {}
    class_exclusions = {}
    inst_id = user_data.get('institution_id')
    class_ids = user_data.get('class_ids', [])
    # Level 1: Institution Exclusions
    if inst_id:
        try:
            inst_excl_doc = db.collection('institutions').document(inst_id).collection('syllabus_exclusions').document('current').get()
            if inst_excl_doc.exists:
                institution_exclusions = inst_excl_doc.to_dict().get('chapters', {})
        except:
            pass
    # Level 2: Class Exclusions (union of all classes student is in)
    if class_ids:
        for class_id in class_ids:
            try:
                class_excl_doc = db.collection('classes').document(class_id).collection('excluded_chapters').document('current').get()
                if class_excl_doc.exists:
                    class_exclusions.update(class_excl_doc.to_dict().get('chapters', {}))
            except:
                pass
    # Merge all exclusions (union)
    all_exclusions = {}
    all_exclusions.update(institution_exclusions)
    all_exclusions.update(class_exclusions)
    all_exclusions.update(personal_exclusions)
    syllabus = {}
    syllabus_purpose = {
        'high_school': 'highschool',
        'exam_prep': 'exam',
        'after_tenth': 'after_tenth'
    }.get(purpose, purpose)
    if purpose == 'high_school' and user_data.get('highschool'):
        hs = user_data['highschool']
        syllabus = get_syllabus(syllabus_purpose, hs.get('board'), hs.get('grade'))
    elif purpose == 'exam_prep' and user_data.get('exam'):
        syllabus = get_syllabus(syllabus_purpose, user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        syllabus = get_syllabus(syllabus_purpose, 'CBSE', at.get('grade'), at.get('subjects', []))
    if not syllabus:
        return {
            'overall': 0,
            'by_subject': {},
            'total_chapters': 0,
            'total_completed': 0,
            'momentum': 0,
            'consistency': 0,
            'readiness': 0
        }
    by_subject = {}
    chapters_by_subject = {}
    total_chapters = 0
    total_completed = 0
    for subject_name, subject_data in syllabus.items():
        chapters = subject_data.get('chapters', {})
        subject_completed_data = chapters_completed.get(subject_name, {})
        subject_valid_count = 0
        subject_completed_count = 0
        for chapter_name in chapters.keys():
            exclusion_key = f"{subject_name}::{chapter_name}"
            # If chapter is excluded at ANY level, skip it
            if all_exclusions.get(exclusion_key):
                continue
            subject_valid_count += 1
            if subject_completed_data.get(chapter_name, False):
                subject_completed_count += 1
        if subject_valid_count > 0:
            by_subject[subject_name] = round((subject_completed_count / subject_valid_count) * 100, 1)
        else:
            by_subject[subject_name] = 0
        
        # Store chapter counts per subject
        chapters_by_subject[subject_name] = {
            'total': subject_valid_count,
            'completed': subject_completed_count
        }
        
        total_chapters += subject_valid_count
        total_completed += subject_completed_count
    # --- AI Analytics Engine ---
    momentum = 0
    consistency = 0
    readiness = 0
    # 1. Momentum: Last 4 exams gradient
    results = user_data.get('exam_results', [])
    if len(results) >= 2:
        sorted_res = sorted(results, key=lambda x: x.get('date', ''), reverse=True)
        try:
            series = [float(r.get('percentage', r.get('score', 0))) for r in sorted_res[:4]][::-1]
            momentum = round(series[-1] - series[0], 1)
        except: pass
    # 2. Consistency: Time pattern stability
    # In a full app, we analyze study_sessions. Here we use session data if available.
    # Logic: More sessions per week = higher consistency.
    sessions_count = len(user_data.get('recent_sessions', [])) # Mocking session density
    consistency = min(100, sessions_count * 15) # Example calculation
    # 3. Readiness: Weighted Academic Health
    avg_score = 0
    if results:
        avg_score = sum([float(r.get('percentage', r.get('score', 0))) for r in results]) / len(results)
    overall = round((total_completed / total_chapters) * 100, 1) if total_chapters > 0 else 0
    readiness = round((overall * 0.4) + (avg_score * 0.6), 1)
    return {
        'overall': overall,
        'by_subject': by_subject,
        'chapters_by_subject': chapters_by_subject,
        'total_chapters': total_chapters,
        'total_completed': total_completed,
        'momentum': momentum,
        'consistency': consistency,
        'readiness': readiness
    }

def calculate_average_percentage(results):
    valid_percentages = []
    for r in results:
        try:
            score = float(r.get('score', 0))
            max_score = float(r.get('max_score', 0))
            if max_score > 0:
                pct = (score / max_score) * 100
                valid_percentages.append(pct)
        except (TypeError, ValueError):
            continue
    if not valid_percentages:
        return 0
    return round(sum(valid_percentages) / len(valid_percentages), 1)

def initialize_profile_fields(uid):
    user_doc = db.collection('users').document(uid).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    updates = {}
    defaults = {
        'about': '', 'skills': [], 'hobbies': [], 'certificates': [],
        'achievements': [], 'chapters_completed': {}, 'time_studied': 0,
        'goals': [], 'tasks': [], 'todos': [], 'milestones': [], 'exam_results': [],
        'connections': {
            'accepted': [],
            'pending_sent': [],
            'pending_received': []
        },
        'bubbles': [],
        'academic_sharing_consents': {},
        'profile_visibility': {
            'name': True,
            'grade': True,
            'school': True,
            'academic_progress': False,
            'subjects': True
        }
    }
    # interests is a structured object now
    if 'interests' not in user_data:
        updates['interests'] = {'careers': [], 'courses': [], 'internships': []}
    elif isinstance(user_data.get('interests'), list):
        # migrate old list format to new structured format
        updates['interests'] = {'careers': [], 'courses': [], 'internships': []}
    for key, default in defaults.items():
        if key not in user_data:
            updates[key] = default
    if updates:
        db.collection('users').document(uid).update(updates)
    uid = session['uid']
    user_data = get_user_data(uid)
    name_top_statistics = user_data.get('name')

# ============================================================================
# AUTH ROUTES

# ============================================================================

@app.route('/')
def index():
    if 'uid' in session:
        return redirect(url_for('profile_dashboard'))
    return redirect(url_for('landing'))

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit(config[env].RATE_LIMIT_SIGNUP)
def signup():
    if request.method == 'POST':
        # Validate input using schema
        data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'purpose': request.form.get('purpose')
        }
        is_valid, result = validate_schema(user_registration_schema, data)
        if not is_valid:
            flash(f'Validation error: {result}', 'error')
            return redirect(url_for('signup'))
        name = result['name']
        age = request.form.get('age')
        email = result['email']
        password = result['password']
        purpose = result['purpose']
        # Check password strength
        is_strong, msg = PasswordManager.is_strong_password(password)
        if not is_strong:
            flash(f'Password not strong enough: {msg}', 'error')
            return redirect(url_for('signup'))
        try:
            try:
                admin_auth.get_user_by_email(email)
                flash('Email already exists. Please login.', 'error')
                return redirect(url_for('login'))
            except admin_auth.UserNotFoundError:
                pass
            user = admin_auth.create_user(email=email, password=password)
            uid = user.uid
            password_hash = PasswordManager.hash_password(password)
            user_data = {
                'uid': uid, 'name': name, 'age': age, 'email': email,
                'password_hash': password_hash, 'purpose': purpose,
                'about': '', 'skills': [], 'hobbies': [], 'certificates': [],
                'achievements': [],
                'interests': {'careers': [], 'courses': [], 'internships': []},
                'highschool': None, 'exam': None, 'after_tenth': None,
                'chapters_completed': {}, 'time_studied': 0,
                'goals': [], 'tasks': [], 'todos': [], 'milestones': [],
                'exam_results': [],
                'timezone': 'Asia/Kolkata',  # Default timezone (IST)
                'connections': {
                    'accepted': [],
                    'pending_sent': [],
                    'pending_received': []
                },
                'bubbles': [],
                'academic_sharing_consents': {},
                'profile_visibility': {
                    'name': True,
                    'grade': True,
                    'school': True,
                    'academic_progress': False,
                    'subjects': True
                },
                'created_at': datetime.utcnow().isoformat()
            }
            db.collection('users').document(uid).set(user_data)
            session['uid'] = uid
            logger.security_event("user_registered", user_id=uid, ip_address=request.remote_addr)
            if purpose == 'high_school':
                return redirect(url_for('setup_highschool'))
            elif purpose == 'exam_prep':
                return redirect(url_for('setup_exam'))
            elif purpose == 'after_tenth':
                return redirect(url_for('setup_after_tenth'))
            else:
                flash('Invalid purpose selected', 'error')
                return redirect(url_for('signup'))
        except Exception as e:
            logger.error("signup_error", error=str(e), email=email)
            flash(f'Error creating account: An error occurred during registration', 'error')
            return redirect(url_for('signup'))
    return render_template('signup.html')

@app.route('/setup/highschool', methods=['GET', 'POST'])
@require_login
def setup_highschool():
    if request.method == 'POST':
        uid = session['uid']
        db.collection('users').document(uid).update({
            'highschool': {'board': request.form.get('board'), 'grade': request.form.get('grade')}
        })
        flash('Setup complete!', 'success')
        return redirect(url_for('profile_dashboard'))
    return render_template('setup_highschool.html')

@app.route('/setup/exam', methods=['GET', 'POST'])
@require_login
def setup_exam():
    if request.method == 'POST':
        uid = session['uid']
        db.collection('users').document(uid).update({'exam': {'type': request.form.get('exam_type')}})
        flash('Setup complete!', 'success')
        return redirect(url_for('profile_dashboard'))
    return render_template('setup_exam.html')

@app.route('/setup/after_tenth', methods=['GET', 'POST'])
@require_login
def setup_after_tenth():
    if request.method == 'POST':
        uid = session['uid']
        db.collection('users').document(uid).update({
            'after_tenth': {
                'stream': request.form.get('stream'),
                'grade': request.form.get('grade'),
                'subjects': request.form.getlist('subjects')
            }
        })
        flash('Setup complete!', 'success')
        return redirect(url_for('profile_dashboard'))
    return render_template('setup_after_tenth.html')

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit(config[env].RATE_LIMIT_LOGIN)
def login():
    if request.method == 'POST':
        # Get client IP for rate limiting
        client_ip = request.remote_addr
        # Check rate limiting
        if not login_rate_limiter.is_allowed(client_ip):
            flash('Too many login attempts. Please try again later.', 'error')
            logger.security_event("login_rate_limited", ip_address=client_ip)
            return redirect(url_for('login'))
        # Validate input
        data = {
            'email': request.form.get('email'),
            'password': request.form.get('password')
        }
        is_valid, result = validate_schema(user_login_schema, data)
        if not is_valid:
            flash('Invalid email or password format', 'error')
            return redirect(url_for('login'))
        email = result['email']
        password = result['password']
        try:
            user = admin_auth.get_user_by_email(email)
            uid = user.uid
            user_doc = db.collection('users').document(uid).get()
            if not user_doc.exists:
                login_rate_limiter.record_attempt(client_ip)
                flash('Invalid email or password', 'error')
                return redirect(url_for('login'))
            user_data = user_doc.to_dict()
            stored_hash = user_data.get('password_hash')
            if not stored_hash:
                flash('Please contact support to reset your password', 'error')
                return redirect(url_for('login'))
            if not PasswordManager.verify_password(password, stored_hash):
                login_rate_limiter.record_attempt(client_ip)
                logger.security_event("failed_login", user_id=uid, ip_address=client_ip)
                flash('Invalid email or password', 'error')
                return redirect(url_for('login'))
            # Check if this is a legacy SHA-256 hash and upgrade to bcrypt
            if PasswordManager._is_legacy_hash(stored_hash):
                new_hash = PasswordManager.hash_password(password)
                db.collection('users').document(uid).update({'password_hash': new_hash})
                logger.security_event("password_hash_upgraded", user_id=uid, ip_address=client_ip)
            # Successful login - reset rate limiter
            login_rate_limiter.reset_attempts(client_ip)
            _set_session_identity(uid, 'student')
            session.permanent = True
            logger.security_event("successful_login", user_id=uid, ip_address=client_ip)
            user_ref = db.collection('users').document(uid)
            snapshot = user_ref.get()
            user_data = snapshot.to_dict() if snapshot.exists else {}
            today = date.today().isoformat()
            last_login = user_data.get('last_login_date')
            streak = user_data.get('login_streak', 0)
            if last_login:
                last_date = datetime.fromisoformat(last_login).date()
                if last_date == date.today():
                    pass
                elif last_date == date.today() - timedelta(days=1):
                    streak +=1
                else:
                    streak=1
            else:
                streak = 1
            user_ref.update({
                'last_login_date': today,
                'login_streak': streak
            })
            initialize_profile_fields(uid)
            flash('Login successful!', 'success')
            return redirect(url_for('profile_dashboard'))
        except admin_auth.UserNotFoundError:
            login_rate_limiter.record_attempt(client_ip)
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
        except Exception as e:
            logger.error("login_error", error=str(e), email=email, ip=client_ip)
            flash('Login error: An error occurred during login', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/login/student', methods=['GET', 'POST'])
def login_student():
    """Explicit student login (mirrors /login for clarity)"""
    return login()

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('landing'))

@app.route('/student/join/class', methods=['GET', 'POST'])
@require_login
def student_join_class():
    """Student joins a class via multi-use invite code (overlay only)"""
    if request.method == 'POST':
        invite_code = request.form.get('invite_code', '').strip().upper()
        if not invite_code:
            flash('Invite code is required', 'error')
            return render_template('student_join_class.html')
        try:
            # Find class invite
            invite_ref = db.collection('class_invites').document(invite_code).get()
            if not invite_ref.exists:
                flash('Invalid invite code', 'error')
                return render_template('student_join_class.html')
            invite = invite_ref.to_dict()
            if not invite.get('active', False):
                flash('Invite code is no longer active', 'error')
                return render_template('student_join_class.html')
            class_id = invite.get('class_id')
            teacher_id = invite.get('teacher_id')
            institution_id = invite.get('institution_id')
            if not (class_id and teacher_id and institution_id):
                flash('Malformed invite', 'error')
                return render_template('student_join_class.html')
            # Overlay student with institution/class info (no academic data changes)
            uid = session.get('uid')
            user_ref = db.collection('users').document(uid)
            user_ref.update({
                'institution_id': institution_id,
                'class_ids': firestore.ArrayUnion([class_id]),
                'teacher_id': teacher_id
            })
            # Add student to class roster
            class_ref = db.collection('classes').document(class_id)
            class_ref.update({
                'student_uids': firestore.ArrayUnion([uid])
            })
            flash('Successfully joined the class!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            logger.error("student_join_class_error", error=str(e), invite_code=invite_code)
            flash('An error occurred while joining the class', 'error')
    return render_template('student_join_class.html')

@app.route('/institution/teacher/classes/create', methods=['GET', 'POST'])
@require_teacher_v2
def institution_teacher_create_class():
    """Teacher creates a class and generates multi-use invite code"""
    uid = session.get('uid')
    teacher_profile = _get_any_profile(uid) or {}
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        board = request.form.get('board', '').strip()
        grade = request.form.get('grade', '').strip()
        purpose = request.form.get('purpose', '').strip()
        if not name:
            flash('Class name is required', 'error')
            return render_template('institution_teacher_create_class.html', profile=teacher_profile)
        try:
            institution_id = teacher_profile.get('institution_id')
            class_id = str(uuid.uuid4())
            # Create class
            db.collection('classes').document(class_id).set({
                'id': class_id,
                'name': name,
                'board': board,
                'grade': grade,
                'purpose': purpose,
                'teacher_id': uid,
                'institution_id': institution_id,
                'student_uids': [],
                'created_at': firestore.SERVER_TIMESTAMP
            })
            # Generate multi-use invite code
            invite_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
            db.collection('class_invites').document(invite_code).set({
                'code': invite_code,
                'class_id': class_id,
                'teacher_id': uid,
                'institution_id': institution_id,
                'active': True,
                'created_at': firestore.SERVER_TIMESTAMP
            })
            flash(f'Class created! Invite code: {invite_code}', 'success')
            return redirect(url_for('institution_teacher_dashboard'))
        except Exception as e:
            logger.error("teacher_create_class_error", error=str(e))
            flash('Failed to create class', 'error')
    return render_template('institution_teacher_create_class.html', profile=teacher_profile)

@app.route('/institution/teacher/classes')
@require_teacher_v2
def institution_teacher_classes():
    """List teacher's classes with invite codes and actions"""
    try:
        uid = session.get('uid')
        profile = _get_teacher_profile(uid) or {}
        institution_id = profile.get('institution_id')
        classes = []
        class_docs = db.collection('classes').where('teacher_id', '==', uid).stream()
        for doc in class_docs:
            cls = doc.to_dict()
            cls['uid'] = doc.id
            # Find invite code for this class
            invite = db.collection('class_invites').where('class_id', '==', doc.id).where('active', '==', True).limit(1).get()
            if invite:
                invite = next(iter(invite))
                cls['invite_code'] = invite.get('code')
            classes.append(cls)
        return render_template('institution_teacher_classes.html', profile=profile, classes=classes, institution_id=institution_id)
    except Exception as e:
        logger.error("teacher_list_classes_error", error=str(e))
        flash('Failed to load classes', 'error')
        return redirect(url_for('institution_teacher_dashboard'))

# ============================================================================
# INSTITUTION V2 AUTH (ADMIN / TEACHER)

# ============================================================================

@app.route('/signup/admin', methods=['GET', 'POST'])
def signup_admin():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        institution_name = request.form.get('institution_name', '').strip()
        password = request.form.get('password', '')
        if not name or not email or not institution_name or not password:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('signup_admin'))
        is_strong, msg = PasswordManager.is_strong_password(password)
        if not is_strong:
            flash(f'Password not strong enough: {msg}', 'error')
            return redirect(url_for('signup_admin'))
        try:
            try:
                admin_auth.get_user_by_email(email)
                flash('Email already exists. Please login.', 'error')
                return redirect(url_for('login_admin'))
            except admin_auth.UserNotFoundError:
                pass
            user = admin_auth.create_user(email=email, password=password)
            uid = user.uid
            institution_id = uuid.uuid4().hex
            now = datetime.utcnow().isoformat()
            db.collection(INSTITUTIONS_COL).document(institution_id).set({
                'name': institution_name,
                'created_at': now,
                'created_by': uid,
                'status': 'active',
                'plan': 'Free'
            })
            db.collection(INSTITUTION_ADMINS_COL).document(uid).set({
                'uid': uid,
                'name': name,
                'email': email,
                'phone': phone,
                'institution_id': institution_id,
                'role': 'admin',
                'status': 'active',
                'created_at': now,
                'last_login_at': None,
                'password_hash': PasswordManager.hash_password(password),
            })
            _set_session_identity(uid, 'admin', institution_id=institution_id)
            flash('Admin account created successfully!', 'success')
            return redirect(url_for('institution_admin_dashboard'))
        except Exception as e:
            logger.error("admin_signup_error", error=str(e), email=email)
            flash('Error creating admin account.', 'error')
            return redirect(url_for('signup_admin'))
    return render_template('signup_admin.html')

@app.route('/login/admin', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('login_admin'))
        try:
            user = admin_auth.get_user_by_email(email)
            uid = user.uid
            profile = _get_admin_profile(uid)
            if not profile:
                flash('Invalid admin credentials.', 'error')
                return redirect(url_for('login_admin'))
            if profile.get('status') != 'active':
                flash('Your admin account is disabled.', 'error')
                return redirect(url_for('login_admin'))
            stored_hash = profile.get('password_hash')
            if not stored_hash or not PasswordManager.verify_password(password, stored_hash):
                flash('Invalid admin credentials.', 'error')
                return redirect(url_for('login_admin'))
            institution_id = profile.get('institution_id')
            db.collection(INSTITUTION_ADMINS_COL).document(uid).update({
                'last_login_at': datetime.utcnow().isoformat()
            })
            _set_session_identity(uid, 'admin', institution_id=institution_id)
            flash('Login successful!', 'success')
            return redirect(url_for('institution_admin_dashboard'))
        except admin_auth.UserNotFoundError:
            flash('Invalid admin credentials.', 'error')
            return redirect(url_for('login_admin'))
        except Exception as e:
            logger.error("admin_login_error", error=str(e), email=email)
            flash('Login error.', 'error')
            return redirect(url_for('login_admin'))
    return render_template('login_admin.html')

@app.route('/signup/teacher', methods=['GET', 'POST'])
def signup_teacher():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        if not name or not email or not password:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('signup_teacher'))
        is_strong, msg = PasswordManager.is_strong_password(password)
        if not is_strong:
            flash(f'Password not strong enough: {msg}', 'error')
            return redirect(url_for('signup_teacher'))
        try:
            try:
                admin_auth.get_user_by_email(email)
                flash('Email already exists. Please login.', 'error')
                return redirect(url_for('login_teacher'))
            except admin_auth.UserNotFoundError:
                pass
            user = admin_auth.create_user(email=email, password=password)
            uid = user.uid
            now = datetime.utcnow().isoformat()
            db.collection(INSTITUTION_TEACHERS_COL).document(uid).set({
                'uid': uid,
                'name': name,
                'email': email,
                'phone': phone,
                'institution_id': None,
                'role': 'teacher',
                'status': 'pending',
                'created_at': now,
                'last_login_at': None,
                'password_hash': PasswordManager.hash_password(password),
                'class_ids': [],
            })
            _set_session_identity(uid, 'teacher')
            flash('Teacher account created. Join an institution to activate.', 'success')
            return redirect(url_for('institution_teacher_join'))
        except Exception as e:
            logger.error("teacher_signup_error", error=str(e), email=email)
            flash('Error creating teacher account.', 'error')
            return redirect(url_for('signup_teacher'))
    return render_template('signup_teacher.html')

@app.route('/login/teacher', methods=['GET', 'POST'])
def login_teacher():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('login_teacher'))
        try:
            user = admin_auth.get_user_by_email(email)
            uid = user.uid
            profile = _get_teacher_profile(uid)
            if not profile:
                flash('Invalid teacher credentials.', 'error')
                return redirect(url_for('login_teacher'))
            if profile.get('status') == 'disabled':
                flash('Your teacher account is disabled.', 'error')
                return redirect(url_for('login_teacher'))
            stored_hash = profile.get('password_hash')
            if not stored_hash or not PasswordManager.verify_password(password, stored_hash):
                flash('Invalid teacher credentials.', 'error')
                return redirect(url_for('login_teacher'))
            institution_id = profile.get('institution_id')
            db.collection(INSTITUTION_TEACHERS_COL).document(uid).update({
                'last_login_at': datetime.utcnow().isoformat()
            })
            _set_session_identity(uid, 'teacher', institution_id=institution_id)
            if not institution_id or profile.get('status') != 'active':
                flash('Join an institution to activate your account.', 'info')
                return redirect(url_for('institution_teacher_join'))
            flash('Login successful!', 'success')
            return redirect(url_for('institution_teacher_dashboard'))
        except admin_auth.UserNotFoundError:
            flash('Invalid teacher credentials.', 'error')
            return redirect(url_for('login_teacher'))
        except Exception as e:
            logger.error("teacher_login_error", error=str(e), email=email)
            flash('Login error.', 'error')
            return redirect(url_for('login_teacher'))
    return render_template('login_teacher.html')

@app.route('/institution/teacher/join', methods=['GET', 'POST'])
@require_teacher_v2
def institution_teacher_join():
    uid = session['uid']
    profile = _get_teacher_profile(uid) or {}
    if request.method == 'POST':
        code = request.form.get('invite_code', '').strip().upper()
        if not code:
            flash('Invite code is required.', 'error')
            return redirect(url_for('institution_teacher_join'))
        invite_q = db.collection(TEACHER_INVITES_COL).where('code', '==', code).where('used', '==', False).limit(1)
        invites = list(invite_q.stream())
        if not invites:
            flash('Invalid or expired invite code.', 'error')
            return redirect(url_for('institution_teacher_join'))
        invite_doc = invites[0]
        invite_data = invite_doc.to_dict()
        institution_id = invite_data.get('institution_id')
        batch = db.batch()
        batch.update(invite_doc.reference, {
            'used': True,
            'used_by': uid,
            'used_at': datetime.utcnow().isoformat()
        })
        batch.update(db.collection(INSTITUTION_TEACHERS_COL).document(uid), {
            'institution_id': institution_id,
            'status': 'active'
        })
        batch.commit()
        _set_session_identity(uid, 'teacher', institution_id=institution_id)
        flash('Successfully joined institution!', 'success')
        return redirect(url_for('institution_teacher_dashboard'))
    return render_template('institution_teacher_join.html', profile=profile)

@app.route('/institution/admin/dashboard')
@require_admin_v2
def institution_admin_dashboard():
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id') or session.get('institution_id')
    inst_doc = db.collection(INSTITUTIONS_COL).document(institution_id).get() if institution_id else None
    institution = inst_doc.to_dict() if inst_doc and inst_doc.exists else {}
    teachers_ref = db.collection(INSTITUTION_TEACHERS_COL).where('institution_id', '==', institution_id)
    teachers = []
    for t in teachers_ref.stream():
        d = t.to_dict()
        d['uid'] = t.id
        teachers.append(d)
    students_ref = db.collection('users').where('institution_id', '==', institution_id)
    students = []
    for s in students_ref.stream():
        d = s.to_dict()
        d['uid'] = s.id
        students.append(d)
    # Analytics (Heatmap + Predictive Risk)
    analytics = _get_institution_analytics(institution_id)
    
    context = {
        'profile': admin_profile,
        'institution': institution,
        'institution_id': institution_id,
        'teachers': teachers,
        'students': students,
        'heatmap_data': analytics['heatmap'],
        'at_risk_students': analytics['at_risk']
    }
    return render_template('institution_admin_dashboard.html', **context)

@app.route('/institution/admin/teacher_invite', methods=['POST'])
@require_admin_v2
def institution_admin_create_teacher_invite():
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')
    code = _generate_code(8)
    db.collection(TEACHER_INVITES_COL).add({
        'code': code,
        'institution_id': institution_id,
        'created_by': uid,
        'created_at': datetime.utcnow().isoformat(),
        'used': False,
        'used_by': None,
        'used_at': None,
        'one_time': True
    })
    flash(f'Teacher invite code generated: {code}', 'success')
    return redirect(url_for('institution_admin_dashboard'))

@app.route('/institution/admin/teachers/<teacher_uid>/disable', methods=['POST'])
@require_admin_v2
def institution_admin_disable_teacher(teacher_uid):
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')
    t_doc = db.collection(INSTITUTION_TEACHERS_COL).document(teacher_uid).get()
    if not t_doc.exists:
        abort(404)
    t = t_doc.to_dict()
    if t.get('institution_id') != institution_id:
        abort(403)
    db.collection(INSTITUTION_TEACHERS_COL).document(teacher_uid).update({'status': 'disabled'})
    try:
        admin_auth.update_user(teacher_uid, disabled=True)
    except Exception:
        pass
    flash('Teacher disabled.', 'success')
    return redirect(url_for('institution_admin_dashboard'))

@app.route('/institution/admin/teachers/<teacher_uid>/delete', methods=['POST'])
@require_admin_v2
def institution_admin_delete_teacher(teacher_uid):
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')
    t_doc = db.collection(INSTITUTION_TEACHERS_COL).document(teacher_uid).get()
    if not t_doc.exists:
        abort(404)
    t = t_doc.to_dict()
    if t.get('institution_id') != institution_id:
        abort(403)
    # Soft-delete by default (keep auth but disable); profile removed.
    try:
        admin_auth.update_user(teacher_uid, disabled=True)
    except Exception:
        pass
    db.collection(INSTITUTION_TEACHERS_COL).document(teacher_uid).delete()
    flash('Teacher deleted.', 'success')
    return redirect(url_for('institution_admin_dashboard'))

@app.route('/institution/admin/students/<student_uid>/remove', methods=['POST'])
@require_admin_v2
def institution_admin_remove_student(student_uid):
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')
    s_doc = db.collection('users').document(student_uid).get()
    if not s_doc.exists:
        abort(404)
    s = s_doc.to_dict()
    if s.get('institution_id') != institution_id:
        abort(403)
    # Remove overlay links; do NOT touch academic progress
    class_ids = s.get('class_ids', []) or []
    batch = db.batch()
    batch.update(db.collection('users').document(student_uid), {
        'institution_id': None,
        'class_ids': [],
        'role': 'student'
    })
    for cid in class_ids:
        batch.update(db.collection(CLASSES_COL).document(cid), {
            'students': firestore.ArrayRemove([student_uid])
        })
    batch.commit()
    flash('Student removed from institution (personal dashboard preserved).', 'success')
    return redirect(url_for('institution_admin_dashboard'))

@app.route('/institution/admin/students/<student_uid>/delete', methods=['POST'])
@require_admin_v2
def institution_admin_delete_student(student_uid):
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')
    s_doc = db.collection('users').document(student_uid).get()
    if not s_doc.exists:
        abort(404)
    s = s_doc.to_dict()
    if s.get('institution_id') != institution_id:
        abort(403)
    # Hard delete = disable auth + remove user doc (this WILL delete academic data)
    try:
        admin_auth.update_user(student_uid, disabled=True)
    except Exception:
        pass
    db.collection('users').document(student_uid).delete()
    flash('Student deleted (account disabled).', 'success')
    return redirect(url_for('institution_admin_dashboard'))

@app.route('/institution/teacher/dashboard')
@require_teacher_v2
def institution_teacher_dashboard():
    uid = session['uid']
    profile = _get_teacher_profile(uid) or {}
    institution_id = profile.get('institution_id')
    if not institution_id or profile.get('status') != 'active':
        return redirect(url_for('institution_teacher_join'))
    classes_ref = db.collection(CLASSES_COL).where('institution_id', '==', institution_id).where('teacher_id', '==', uid)
    classes = []
    # Fetch invite codes for the dashboard view as well
    for c in classes_ref.stream():
        cls_data = c.to_dict()
        cls_data['id'] = c.id
        # Find invite code for this class
        invite = db.collection('class_invites').where('class_id', '==', c.id).where('active', '==', True).limit(1).get()
        if invite:
            invite_doc = next(iter(invite))
            cls_data['invite_code'] = invite_doc.get('code')
        classes.append(cls_data)
    # Analytics (Heatmap + Predictive Risk) for the teacher's classes
    class_ids = [c['id'] for c in classes]
    analytics = _get_institution_analytics(institution_id, class_ids=class_ids)
    
    return render_template('institution_teacher_dashboard.html', 
                           profile=profile, 
                           classes=classes, 
                           institution_id=institution_id,
                           heatmap_data=analytics['heatmap'],
                           at_risk_students=analytics['at_risk'])

@app.route('/institution/teacher/class/<class_id>/upload', methods=['GET', 'POST'])
@require_teacher_v2
def institution_teacher_upload_file(class_id):
    uid = session['uid']
    profile = _get_teacher_profile(uid) or {}
    # Check if teacher owns the class
    class_doc = db.collection('classes').document(class_id).get()
    if not class_doc.exists or class_doc.to_dict().get('teacher_id') != uid:
        flash('Unauthorized', 'error')
        return redirect(url_for('institution_teacher_dashboard'))
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        # Save to local storage
        upload_folder = os.path.join(app.root_path, 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        file_path = os.path.join(upload_folder, f'{file_id}_{filename}')
        file.save(file_path)
        file_url = url_for('serve_upload', filename=f'{file_id}_{filename}')
        # Save to Firestore
        db.collection('class_files').document(file_id).set({
            'id': file_id,
            'class_id': class_id,
            'file_name': filename,
            'file_url': file_url,
            'uploaded_by': uid,
            'upload_date': datetime.utcnow().isoformat(),
            'file_type': 'notes',
            'file_size': file.content_length or 0
        })
        flash('File uploaded successfully', 'success')
        return redirect(url_for('institution_teacher_dashboard'))
    # GET: render upload form
    class_data = class_doc.to_dict()
    return render_template('institution_teacher_upload.html', class_id=class_id, class_name=class_data.get('name'), profile=profile)

@app.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded files from local storage"""
    try:
        return send_from_directory(
            os.path.join(app.root_path, 'uploads'),
            filename
        )
    except FileNotFoundError:
        abort(404)

@app.route('/profile_banners/<filename>')
def serve_profile_banner(filename):
    """Serve profile banners from local storage"""
    try:
        return send_from_directory(
            os.path.join(app.root_path, 'static', 'profile_banners'),
            filename
        )
    except FileNotFoundError:
        # Return default banner or 404
        return '', 404

# ============================================================================
# MAIN DASHBOARD

# ============================================================================

@app.route('/dashboard')
@app.route('/profile')
@require_login
def profile_dashboard():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    purpose = user_data.get('purpose')
    academic_summary = ''
    if purpose == 'highschool' and user_data.get('highschool'):
        hs = user_data['highschool']
        academic_summary = f"{hs.get('board', '')} – Grade {hs.get('grade', '')}"
    elif purpose == 'exam' and user_data.get('exam'):
        academic_summary = f"{user_data['exam'].get('type', '')} Preparation"
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        academic_summary = f"{at.get('stream', '')} – Grade {at.get('grade', '')}"
    progress_data = calculate_academic_progress(user_data)
    # Get user's saved career interests for the interests island
    interests = user_data.get('interests', {})
    if isinstance(interests, list):
        interests = {'careers': [], 'courses': [], 'internships': []}
    saved_career_ids = interests.get('careers', [])
    saved_careers = [get_career_by_id(cid) for cid in saved_career_ids if get_career_by_id(cid)]
    context = {
        'user': user_data,
        'name': user_data.get('name', 'Student'),
        'purpose': purpose,
        'purpose_display': purpose.replace('_', ' ').title() if purpose else '',
        'academic_summary': academic_summary,
        'progress_data': progress_data,
        'overall_progress': progress_data.get('overall', 0),
        'subject_progress': progress_data.get('by_subject', {}),
        'chapters_by_subject': progress_data.get('chapters_by_subject', {}),
        'total_chapters': progress_data.get('total_chapters', 0),
        'completed_chapters': progress_data.get('total_completed', 0),
        'saved_careers': saved_careers,
        'streak': user_data.get('login_streak', 0),
        'profile_picture': user_data.get('profile_picture')
    }
    return render_template('main_dashboard.html', **context)

@app.route('/student/class/files', methods=['GET'])
@require_login
def student_files():
    uid = session['uid']
    user_data = get_user_data(uid)
    class_ids = user_data.get('class_ids', [])
    files = []
    for class_id in class_ids:
        class_files = db.collection('class_files').where('class_id', '==', class_id).stream()
        for f in class_files:
            f_data = f.to_dict()
            # Add class name
            class_doc = db.collection('classes').document(class_id).get()
            class_name = class_doc.to_dict().get('name', 'Unknown') if class_doc.exists else 'Unknown'
            f_data['class_name'] = class_name
            files.append(f_data)
    # Group by class
    from collections import defaultdict
    grouped_files = defaultdict(list)
    for f in files:
        grouped_files[f['class_name']].append(f)
    return render_template('student_class_files.html', grouped_files=grouped_files)

@app.route('/download/class_file/<file_id>', methods=['GET'])
@require_login
def download_class_file(file_id):
    file_doc = db.collection('class_files').document(file_id).get()
    if not file_doc.exists:
        abort(404)
    file_data = file_doc.to_dict()
    class_id = file_data['class_id']
    uid = session['uid']
    user_data = get_user_data(uid)
    if class_id not in user_data.get('class_ids', []):
        abort(403)
    # Redirect to file_url
    return redirect(file_data['file_url'])

# ============================================================================
# COMMUNITY SYSTEM
# ============================================================================

@app.route('/community')
@require_login
def community_dashboard():
    """Community dashboard with connections and bubbles"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))

    # Get connections data
    connections_data = get_connections_data(uid)

    # Get user's bubbles (both created and joined)
    user_bubbles = []
    bubbles_ref = db.collection('bubbles')
    for bubble_doc in bubbles_ref.stream():
        bubble_data = bubble_doc.to_dict()
        member_uids = bubble_data.get('member_uids', [])

        # Show bubbles where user is a member (creator or joined via invitation)
        if uid in member_uids:
            user_bubbles.append({
                'id': bubble_doc.id,
                'name': bubble_data.get('name'),
                'description': bubble_data.get('description'),
                'member_count': len(member_uids),
                'created_at': bubble_data.get('created_at'),
                'is_creator': bubble_data.get('creator_uid') == uid
            })

    # Get user's bubble invitations
    bubble_invitations = []
    if hasattr(user_data, 'get') and user_data.get('pending_bubble_invitations'):
        for invitation_id in user_data.get('pending_bubble_invitations', []):
            try:
                invite_doc = db.collection('bubble_invitations').document(invitation_id).get()
                if invite_doc.exists:
                    invitation = invite_doc.to_dict()
                    bubble_invitations.append({
                        'id': invitation_id,
                        'bubble_name': invitation.get('bubble_name'),
                        'sender_name': None,  # Could fetch sender name if needed
                        'message': invitation.get('message'),
                        'created_at': invitation.get('created_at')
                    })
            except Exception as e:
                continue

    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'connections_data': connections_data,
        'connections_count': len(connections_data.get('accepted', [])),
        'user_bubbles': user_bubbles,
        'bubble_invitations': bubble_invitations
    }

    return render_template('community_dashboard.html', **context)

def get_connections_data(uid):
    """Helper function to get formatted connections data"""
    try:
        user_data = get_user_data(uid)
        if not user_data:
            return {'accepted': [], 'pending_sent': [], 'pending_received': []}

        connections = user_data.get('connections', {})

        # Get detailed info for each connection
        result = {
            'accepted': [],
            'pending_sent': [],
            'pending_received': []
        }

        # Get accepted connections
        for conn_uid in connections.get('accepted', []):
            conn_data = get_user_data(conn_uid)
            if conn_data:
                profile = {
                    'uid': conn_uid,
                    'name': conn_data.get('name'),
                    'purpose_display': conn_data.get('purpose', '').replace('_', ' ').title(),
                    'last_active': conn_data.get('last_login_date')
                }
                result['accepted'].append(profile)

        # Get pending sent requests
        for conn_uid in connections.get('pending_sent', []):
            conn_data = get_user_data(conn_uid)
            if conn_data:
                profile = {
                    'uid': conn_uid,
                    'name': conn_data.get('name'),
                    'purpose_display': conn_data.get('purpose', '').replace('_', ' ').title()
                }
                result['pending_sent'].append(profile)

        # Get pending received requests with connection IDs
        for conn_uid in connections.get('pending_received', []):
            # Find connection request
            conn_requests = db.collection('connections').where('sender_uid', '==', conn_uid).where('receiver_uid', '==', uid).where('status', '==', 'pending').stream()
            conn_request = None
            for req in conn_requests:
                conn_request = req
                break

            if conn_request:
                conn_data = get_user_data(conn_uid)
                if conn_data:
                    profile = {
                        'uid': conn_uid,
                        'name': conn_data.get('name'),
                        'purpose_display': conn_data.get('purpose', '').replace('_', ' ').title(),
                        'connection_id': conn_request.id,
                        'message': conn_request.to_dict().get('message', '')
                    }
                    result['pending_received'].append(profile)

        return result

    except Exception as e:
        logger.error(f"Get connections data error: {str(e)}")
        return {'accepted': [], 'pending_sent': [], 'pending_received': []}

# ============================================================================
# AI ASSISTANT
# ============================================================================

@app.route('/ai-assistant')
@require_login
def ai_assistant():
    """AI Assistant main page with consent check"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))

    # TEMPORARILY BYPASS CONSENT CHECK FOR DEBUGGING
    # Check if user has consented to AI features
    # ai_consent = user_data.get('ai_consent', False)
    # if not ai_consent:
    #     # Show consent screen
    #     return render_template('ai_consent.html', user=user_data)

    # Show AI assistant interface (force consent for debugging)
    ai_consent = True  # Force consent for debugging
    context = {
        'user': user_data,
        'name': user_data.get('name', 'Student'),
        'ai_consent': ai_consent
    }
    return render_template('ai_assistant.html', **context)

@app.route('/ai-assistant/consent', methods=['POST'])
@require_login
def ai_assistant_consent():
    """Handle AI consent decision"""
    uid = session['uid']
    consent = request.form.get('consent') == 'yes'

    if consent:
        # Update user with consent
        db.collection('users').document(uid).update({'ai_consent': True})
        flash('AI Assistant enabled! You can now use AI-powered academic planning and doubt resolution.', 'success')
    else:
        flash('AI Assistant access denied. You can enable it later from your profile.', 'info')

    return redirect(url_for('profile_dashboard'))

@app.route('/api/ai/chat/planning', methods=['POST'])
@require_login
def ai_chat_planning():
    """API endpoint for planning chatbot"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    # Check consent
    # TEMPORARILY BYPASS CONSENT CHECK FOR DEBUGGING
    # if not user_data.get('ai_consent', False):
    #     return jsonify({'error': 'AI consent required'}), 403

    message = request.json.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Message required'}), 400

    try:
        ai = get_ai_assistant()
        academic_context = ai.get_academic_context(user_data)
        
        # Save user message
        ai.save_message(uid, 'planning', 'user', message)
        
        response = ai.generate_planning_response(message, academic_context)
        
        # Save AI response
        ai.save_message(uid, 'planning', 'assistant', response)
        
        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"AI planning chat error: {str(e)}")
        return jsonify({'error': 'AI service temporarily unavailable'}), 500

@app.route('/api/ai/chat/doubt', methods=['POST'])
@require_login
def ai_chat_doubt():
    """API endpoint for doubt resolution chatbot"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    # Check consent
    # TEMPORARILY BYPASS CONSENT CHECK FOR DEBUGGING
    # if not user_data.get('ai_consent', False):
    #     return jsonify({'error': 'AI consent required'}), 403

    message = request.json.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Message required'}), 400

    try:
        ai = get_ai_assistant()
        academic_context = ai.get_academic_context(user_data)
        
        # Save user message
        ai.save_message(uid, 'doubt', 'user', message)
        
        response = ai.generate_doubt_response(message, academic_context)
        
        # Save AI response
        ai.save_message(uid, 'doubt', 'assistant', response)
        
        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"AI doubt chat error: {str(e)}")
        return jsonify({'error': 'AI service temporarily unavailable'}), 500

@app.route('/api/ai/chat/history/<chatbot_type>', methods=['GET'])
@require_login
def get_chat_history(chatbot_type):
    """Get conversation history for a specific chatbot type (active thread)"""
    uid = session['uid']
    
    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400
    
    try:
        ai = get_ai_assistant()
        history = ai.get_conversation_history(uid, chatbot_type)
        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"Error loading chat history: {str(e)}")
        return jsonify({'error': 'Failed to load conversation history'}), 500

@app.route('/api/ai/threads/<chatbot_type>', methods=['GET'])
@require_login
def get_threads(chatbot_type):
    """Get all conversation threads for a chatbot type"""
    uid = session['uid']

    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400

    try:
        ai = get_ai_assistant()
        threads = ai.get_user_threads(uid, chatbot_type)
        active_thread_id = ai.get_active_thread_id(uid, chatbot_type)
        return jsonify({
            'threads': threads,
            'active_thread_id': active_thread_id
        })
    except Exception as e:
        logger.error(f"Error loading threads: {str(e)}")
        return jsonify({'error': 'Failed to load threads'}), 500

@app.route('/api/ai/threads/<chatbot_type>/create', methods=['POST'])
@require_login
def create_thread(chatbot_type):
    """Create a new conversation thread"""
    uid = session['uid']

    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400

    title = request.json.get('title', f'New {chatbot_type.title()} Conversation')

    try:
        ai = get_ai_assistant()
        thread_id = ai.create_new_thread(uid, chatbot_type, title)
        if thread_id:
            return jsonify({
                'success': True,
                'thread_id': thread_id,
                'title': title
            })
        else:
            return jsonify({'error': 'Failed to create thread'}), 500
    except Exception as e:
        logger.error(f"Error creating thread: {str(e)}")
        return jsonify({'error': 'Failed to create thread'}), 500

@app.route('/api/ai/threads/<chatbot_type>/<thread_id>/switch', methods=['POST'])
@require_login
def switch_thread(chatbot_type, thread_id):
    """Switch active thread for a chatbot type"""
    uid = session['uid']

    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400

    try:
        ai = get_ai_assistant()
        success = ai.switch_thread(uid, chatbot_type, thread_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Thread not found or invalid'}), 404
    except Exception as e:
        logger.error(f"Error switching thread: {str(e)}")
        return jsonify({'error': 'Failed to switch thread'}), 500

@app.route('/api/ai/threads/<chatbot_type>/<thread_id>/delete', methods=['DELETE'])
@require_login
def delete_thread(chatbot_type, thread_id):
    """Delete a conversation thread"""
    uid = session['uid']

    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400

    try:
        ai = get_ai_assistant()
        success = ai.delete_thread(uid, chatbot_type, thread_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Cannot delete active thread or thread not found'}), 400
    except Exception as e:
        logger.error(f"Error deleting thread: {str(e)}")
        return jsonify({'error': 'Failed to delete thread'}), 500

@app.route('/api/ai/threads/<chatbot_type>/<thread_id>/export/<format_type>', methods=['GET'])
@require_login
def export_thread(chatbot_type, thread_id, format_type):
    """Export a conversation thread"""
    uid = session['uid']

    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400

    if format_type not in ['text', 'markdown', 'json']:
        return jsonify({'error': 'Invalid export format. Use: text, markdown, or json'}), 400

    try:
        ai = get_ai_assistant()
        export_data = ai.export_thread(uid, chatbot_type, thread_id, format_type)

        if export_data:
            if format_type == 'json':
                return jsonify(export_data)
            else:
                # Return as downloadable text file
                from flask import Response
                filename = f"conversation_{thread_id}.{format_type}"
                return Response(
                    export_data,
                    mimetype='text/plain',
                    headers={
                        'Content-Disposition': f'attachment; filename={filename}',
                        'Content-Type': 'text/plain; charset=utf-8'
                    }
                )
        else:
            return jsonify({'error': 'Thread not found or export failed'}), 404
    except Exception as e:
        logger.error(f"Error exporting thread: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500

@app.route('/api/ai/threads/<chatbot_type>/<thread_id>/history', methods=['GET'])
@require_login
def get_thread_history(chatbot_type, thread_id):
    """Get messages for a specific conversation thread"""
    uid = session['uid']
    
    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400
    
    try:
        ai = get_ai_assistant()
        history = ai.get_conversation_history(uid, chatbot_type, thread_id)
        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"Error loading thread history: {str(e)}")
        return jsonify({'error': 'Failed to load thread history'}), 500

# ============================================================================
# CONNECTIONS SYSTEM
# ============================================================================

@app.route('/api/people/search', methods=['GET'])
@require_login
def search_people():
    """Search for people by name with filters and privacy controls"""
    uid = session['uid']
    query = request.args.get('q', '').strip()
    grade_filter = request.args.get('grade')
    school_filter = request.args.get('school')
    subject_filter = request.args.get('subject')
    academic_range = request.args.get('academic_range')

    logger.info(f"MAIN Search request: uid={uid}, query='{query}'")

    if not query or len(query) < 2:
        return jsonify({'error': 'Search query must be at least 2 characters'}), 400

    try:
        logger.info("MAIN: Starting user search query")
        users_ref = db.collection('users')
        users = []

        logger.info("MAIN: Iterating through users collection")
        for doc in users_ref.stream():
            try:
                user_data = doc.to_dict()
                logger.debug(f"MAIN: Processing user: {doc.id}")

                # Skip self
                if doc.id == uid:
                    logger.debug("MAIN: Skipping self")
                    continue

                # Check privacy settings
                visibility = user_data.get('profile_visibility', {})
                if not visibility.get('name', True):
                    logger.debug(f"MAIN: Skipping user {doc.id} - name not visible")
                    continue

                # Name matching (case-insensitive)
                name = user_data.get('name', '').lower()
                if query.lower() not in name:
                    logger.debug(f"MAIN: Name '{name}' doesn't contain query '{query.lower()}'")
                    continue

                logger.debug(f"MAIN: User {doc.id} matches search")

                # Build profile for search results
                profile = {
                    'uid': doc.id,
                    'name': user_data.get('name'),
                    'purpose_display': user_data.get('purpose', '').replace('_', ' ').title(),
                    'academic_summary': '',
                    'connection_status': 'none'
                }

                users.append(profile)
                logger.debug(f"MAIN: Added user {doc.id} to results")

            except Exception as user_error:
                logger.error(f"MAIN: Error processing user {doc.id}: {str(user_error)}")
                continue

        logger.info(f"MAIN: Found {len(users)} matching users")

        # Limit results
        users = users[:20]

        return jsonify({
            'results': users,
            'total': len(users),
            'query': query
        })

    except Exception as e:
        logger.error(f"MAIN: People search error: {str(e)}")
        return jsonify({'error': 'Search failed', 'details': str(e)}), 500

# ============================================================================
# BUBBLES SYSTEM
# ============================================================================

@app.route('/api/bubbles/create', methods=['POST'])
@require_login
def create_bubble():
    """Create a new study bubble"""
    uid = session['uid']

    try:
        data = request.json
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        if not name:
            return jsonify({'error': 'Bubble name is required'}), 400

        bubble_id = f"bubble_{uid}_{int(time.time())}"
        bubble_data = {
            'bubble_id': bubble_id,
            'name': name,
            'description': description,
            'creator_uid': uid,
            'member_uids': [uid],  # Creator is automatically a member
            'created_at': datetime.utcnow().isoformat(),
            'settings': {
                'require_consent': True,
                'leaderboard_enabled': True
            }
        }

        # Save bubble
        db.collection('bubbles').document(bubble_id).set(bubble_data)

        # Add bubble to user's bubbles list
        user_ref = db.collection('users').document(uid)
        user_ref.update({
            'bubbles': firestore.ArrayUnion([bubble_id])
        })

        logger.info(f"Created bubble {bubble_id} by user {uid}")

        return jsonify({
            'success': True,
            'bubble_id': bubble_id,
            'message': 'Study bubble created successfully'
        })

    except Exception as e:
        logger.error(f"Bubble creation error: {str(e)}")
        return jsonify({'error': 'Failed to create bubble', 'details': str(e)}), 500

@app.route('/api/bubbles/<bubble_id>/delete', methods=['DELETE'])
@require_login
def delete_bubble(bubble_id):
    """Delete a study bubble"""
    uid = session['uid']

    try:
        # Get bubble to verify ownership
        bubble_doc = db.collection('bubbles').document(bubble_id).get()
        if not bubble_doc.exists:
            return jsonify({'error': 'Bubble not found'}), 404

        bubble_data = bubble_doc.to_dict()
        if bubble_data.get('creator_uid') != uid:
            return jsonify({'error': 'Not authorized to delete this bubble'}), 403

        # Remove bubble from all members' bubbles lists
        member_uids = bubble_data.get('member_uids', [])
        batch = db.batch()

        for member_uid in member_uids:
            batch.update(db.collection('users').document(member_uid), {
                'bubbles': firestore.ArrayRemove([bubble_id])
            })

        # Delete the bubble document
        batch.delete(db.collection('bubbles').document(bubble_id))

        batch.commit()

        return jsonify({
            'success': True,
            'message': 'Bubble deleted successfully'
        })

    except Exception as e:
        return jsonify({'error': f'Failed to delete bubble: {str(e)}'}), 500

@app.route('/api/user/privacy/leaderboard', methods=['POST'])
@require_login
def update_leaderboard_consent():
    """Update user's privacy consent for leaderboard participation"""
    uid = session['uid']

    try:
        data = request.get_json()
        allow_leaderboard = data.get('allow_leaderboard', False)

        # Update user privacy settings
        user_ref = db.collection('users').document(uid)
        user_ref.update({
            'privacy_settings.allow_leaderboard': allow_leaderboard
        })

        return jsonify({
            'success': True,
            'message': 'Privacy preference updated successfully'
        })

    except Exception as e:
        return jsonify({'error': f'Failed to update privacy settings: {str(e)}'}), 500

@app.route('/api/bubbles/join', methods=['POST'])
@require_login
def join_bubble_by_code():
    """Join a bubble using invite code"""
    uid = session['uid']

    try:
        data = request.get_json()
        invite_code = data.get('invite_code', '').strip()

        if not invite_code:
            return jsonify({'error': 'Invite code is required'}), 400

        # Find bubble by invite code
        bubbles_ref = db.collection('bubbles')
        bubble_query = bubbles_ref.where('invite_code', '==', invite_code).limit(1)
        bubble_docs = bubble_query.get()

        if not bubble_docs:
            return jsonify({'error': 'Invalid invite code'}), 404

        bubble_doc = next(iter(bubble_docs))
        bubble_data = bubble_doc.to_dict()
        bubble_id = bubble_doc.id

        # Check if user is already a member
        member_uids = bubble_data.get('member_uids', [])
        if uid in member_uids:
            return jsonify({'error': 'You are already a member of this bubble'}), 400

        # Add user to bubble members
        db.collection('bubbles').document(bubble_id).update({
            'member_uids': firestore.ArrayUnion([uid])
        })

        # Add bubble to user's bubbles list
        db.collection('users').document(uid).update({
            'bubbles': firestore.ArrayUnion([bubble_id])
        })

        return jsonify({
            'success': True,
            'message': 'Successfully joined the bubble!',
            'bubble_id': bubble_id,
            'bubble_name': bubble_data.get('name')
        })

    except Exception as e:
        return jsonify({'error': f'Failed to join bubble: {str(e)}'}), 500

@app.route('/api/bubbles/<bubble_id>/invite', methods=['POST'])
@require_login
def send_bubble_invitation(bubble_id):
    """Send bubble invitation to a connection"""
    uid = session['uid']

    try:
        data = request.get_json()
        target_uid = data.get('target_uid')

        if not target_uid:
            return jsonify({'error': 'Target user required'}), 400

        # Verify bubble ownership
        bubble_doc = db.collection('bubbles').document(bubble_id).get()
        if not bubble_doc.exists:
            return jsonify({'error': 'Bubble not found'}), 404

        bubble_data = bubble_doc.to_dict()
        if bubble_data.get('creator_uid') != uid:
            return jsonify({'error': 'Not authorized to send invitations for this bubble'}), 403

        # Check if target is already a member
        if target_uid in bubble_data.get('member_uids', []):
            return jsonify({'error': 'User is already a member of this bubble'}), 400

        # Check if invitation already sent (you could store pending invitations)
        # For now, just create a notification/invitation record

        invitation_id = f"invite_{bubble_id}_{target_uid}_{int(time.time())}"
        invitation_data = {
            'invitation_id': invitation_id,
            'bubble_id': bubble_id,
            'bubble_name': bubble_data.get('name'),
            'sender_uid': uid,
            'receiver_uid': target_uid,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'message': f'You have been invited to join the study bubble "{bubble_data.get("name")}"'
        }

        # Store invitation
        db.collection('bubble_invitations').document(invitation_id).set(invitation_data)

        # Add to receiver's pending invitations
        db.collection('users').document(target_uid).update({
            'pending_bubble_invitations': firestore.ArrayUnion([invitation_id])
        })

        return jsonify({
            'success': True,
            'invitation_id': invitation_id,
            'message': 'Invitation sent successfully'
        })

    except Exception as e:
        return jsonify({'error': f'Failed to send invitation: {str(e)}'}), 500

@app.route('/api/bubbles/invitations/<invitation_id>/accept', methods=['POST'])
@require_login
def accept_bubble_invitation(invitation_id):
    """Accept a bubble invitation"""
    uid = session['uid']

    try:
        # Get invitation
        invite_doc = db.collection('bubble_invitations').document(invitation_id).get()
        if not invite_doc.exists:
            return jsonify({'error': 'Invitation not found'}), 404

        invitation = invite_doc.to_dict()

        # Verify user is the receiver
        if invitation['receiver_uid'] != uid:
            return jsonify({'error': 'Not authorized'}), 403

        # Check if already processed
        if invitation['status'] != 'pending':
            return jsonify({'error': 'Invitation already processed'}), 400

        bubble_id = invitation['bubble_id']

        # Get bubble to verify it exists
        bubble_doc = db.collection('bubbles').document(bubble_id).get()
        if not bubble_doc.exists:
            return jsonify({'error': 'Bubble no longer exists'}), 404

        # Ask for consent
        consent_given = request.get_json().get('consent', False)
        if not consent_given:
            return jsonify({
                'needs_consent': True,
                'bubble_name': invitation['bubble_name'],
                'message': 'Please confirm you want to join this bubble and share your progress on the leaderboard.'
            }), 200

        # Add user to bubble
        db.collection('bubbles').document(bubble_id).update({
            'member_uids': firestore.ArrayUnion([uid])
        })

        # Add bubble to user's bubbles
        db.collection('users').document(uid).update({
            'bubbles': firestore.ArrayUnion([bubble_id]),
            'privacy_settings.allow_leaderboard': True  # They consented
        })

        # Update invitation status
        db.collection('bubble_invitations').document(invitation_id).update({
            'status': 'accepted',
            'accepted_at': datetime.utcnow().isoformat()
        })

        # Remove from pending invitations
        db.collection('users').document(uid).update({
            'pending_bubble_invitations': firestore.ArrayRemove([invitation_id])
        })

        return jsonify({
            'success': True,
            'bubble_id': bubble_id,
            'message': f'Successfully joined "{invitation["bubble_name"]}"'
        })

    except Exception as e:
        return jsonify({'error': f'Failed to accept invitation: {str(e)}'}), 500

@app.route('/api/bubbles/invitations/<invitation_id>/decline', methods=['POST'])
@require_login
def decline_bubble_invitation(invitation_id):
    """Decline a bubble invitation"""
    uid = session['uid']

    try:
        # Get invitation
        invite_doc = db.collection('bubble_invitations').document(invitation_id).get()
        if not invite_doc.exists:
            return jsonify({'error': 'Invitation not found'}), 404

        invitation = invite_doc.to_dict()

        # Verify user is the receiver
        if invitation['receiver_uid'] != uid:
            return jsonify({'error': 'Not authorized'}), 403

        # Update invitation status
        db.collection('bubble_invitations').document(invitation_id).update({
            'status': 'declined',
            'declined_at': datetime.utcnow().isoformat()
        })

        # Remove from pending invitations
        db.collection('users').document(uid).update({
            'pending_bubble_invitations': firestore.ArrayRemove([invitation_id])
        })

        return jsonify({
            'success': True,
            'message': 'Invitation declined'
        })

    except Exception as e:
        return jsonify({'error': f'Failed to decline invitation: {str(e)}'}), 500

@app.route('/api/people/search/debug', methods=['GET'])
def debug_search_people():
    """Debug version of search without authentication"""
    query = request.args.get('q', '').strip()

    logger.info(f"DEBUG Search request: query='{query}'")

    if not query or len(query) < 2:
        return jsonify({'error': 'Search query must be at least 2 characters'}), 400

    try:
        logger.info("DEBUG: Starting user search query")
        users_ref = db.collection('users')
        users = []

        logger.info("DEBUG: Iterating through users collection")
        for doc in users_ref.stream():
            try:
                user_data = doc.to_dict()
                logger.debug(f"DEBUG: Processing user: {doc.id}")

                # Check privacy settings
                visibility = user_data.get('profile_visibility', {})
                if not visibility.get('name', True):
                    continue

                # Name matching (case-insensitive)
                name = user_data.get('name', '').lower()
                if query.lower() not in name:
                    continue

                logger.debug(f"DEBUG: User {doc.id} matches search")

                # Build profile for search results
                profile = {
                    'uid': doc.id,
                    'name': user_data.get('name'),
                    'purpose_display': user_data.get('purpose', '').replace('_', ' ').title(),
                    'academic_summary': '',
                    'connection_status': 'none'
                }

                users.append(profile)

            except Exception as user_error:
                logger.error(f"DEBUG: Error processing user {doc.id}: {str(user_error)}")
                continue

        logger.info(f"DEBUG: Found {len(users)} matching users")
        users = users[:5]  # Limit for debug

        return jsonify({
            'results': users,
            'total': len(users),
            'query': query,
            'debug': True
        })

    except Exception as e:
        logger.error(f"DEBUG: Search error: {str(e)}")
        logger.error(f"DEBUG: Error type: {type(e).__name__}")
        import traceback
        logger.error(f"DEBUG: Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Search failed', 'details': str(e), 'debug': True}), 500

@app.route('/api/debug/users', methods=['GET'])
def debug_list_users():
    """Debug endpoint to list all users in database"""
    try:
        users_ref = db.collection('users')
        users = []
        
        for doc in users_ref.stream():
            user_data = doc.to_dict()
            users.append({
                'uid': doc.id,
                'name': user_data.get('name'),
                'purpose': user_data.get('purpose'),
                'has_profile_visibility': 'profile_visibility' in user_data,
                'name_visible': user_data.get('profile_visibility', {}).get('name', True)
            })
        
        return jsonify({
            'total_users': len(users),
            'users': users[:10],  # Limit to first 10
            'debug': True
        })
    except Exception as e:
        return jsonify({'error': str(e), 'debug': True}), 500

@app.route('/bubbles')
@require_login
def academic_leaderboard():
    """Academic leaderboard - shows study performance rankings"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))

    # Get all users for leaderboard
    users_ref = db.collection('users')
    leaderboard_data = []

    for doc in users_ref.stream():
        user_doc = doc.to_dict()
        user_id = doc.id

        # Calculate academic progress for each user
        try:
            progress = calculate_academic_progress(user_doc)
            overall_score = progress.get('overall', 0)

            leaderboard_data.append({
                'uid': user_id,
                'name': user_doc.get('name', 'Anonymous'),
                'purpose_display': user_doc.get('purpose', '').replace('_', ' ').title(),
                'overall_score': overall_score,
                'total_chapters': progress.get('total_chapters', 0),
                'completed_chapters': progress.get('total_completed', 0),
                'grade': None,
                'is_current_user': user_id == uid
            })

            # Add grade info if available
            purpose = user_doc.get('purpose')
            if purpose == 'high_school' and user_doc.get('highschool'):
                leaderboard_data[-1]['grade'] = user_doc['highschool'].get('grade')
            elif purpose == 'after_tenth' and user_doc.get('after_tenth'):
                leaderboard_data[-1]['grade'] = user_doc['after_tenth'].get('grade')

        except Exception as e:
            # Skip users with calculation errors
            continue

    # Sort by overall score (highest first)
    leaderboard_data.sort(key=lambda x: x['overall_score'], reverse=True)

    # Add rankings
    for i, user in enumerate(leaderboard_data, 1):
        user['rank'] = i

    # Find current user's rank
    current_user_rank = None
    current_user_data = None
    for user in leaderboard_data:
        if user['is_current_user']:
            current_user_rank = user['rank']
            current_user_data = user
            break

    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'leaderboard': leaderboard_data[:50],  # Top 50
        'current_user_rank': current_user_rank,
        'current_user_data': current_user_data,
        'total_participants': len(leaderboard_data)
    }

    return render_template('academic_leaderboard.html', **context)

@app.route('/bubble/<bubble_id>')
@require_login
def bubble_detail(bubble_id):
    """Individual bubble page with bubble-specific leaderboard"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))

    # Get bubble data
    bubble_doc = db.collection('bubbles').document(bubble_id).get()
    if not bubble_doc.exists:
        flash('Bubble not found', 'error')
        return redirect(url_for('community_dashboard'))

    bubble_data = bubble_doc.to_dict()

    # Check if user is a member of this bubble
    is_member = uid in bubble_data.get('member_uids', [])
    is_creator = bubble_data.get('creator_uid') == uid

    if not is_member and not is_creator:
        flash('You are not a member of this bubble', 'error')
        return redirect(url_for('community_dashboard'))

    # Get bubble members for leaderboard
    member_uids = bubble_data.get('member_uids', [])
    leaderboard_data = []

    for member_uid in member_uids:
        try:
            member_data = get_user_data(member_uid)
            if member_data:
                # Check if user has consented to leaderboard participation
                privacy_settings = member_data.get('privacy_settings', {})
                allow_leaderboard = privacy_settings.get('allow_leaderboard', False)

                if allow_leaderboard:
                    progress = calculate_academic_progress(member_data)
                    overall_score = progress.get('overall', 0)

                    leaderboard_data.append({
                        'uid': member_uid,
                        'name': member_data.get('name', 'Anonymous'),
                        'purpose_display': member_data.get('purpose', '').replace('_', ' ').title(),
                        'overall_score': overall_score,
                        'total_chapters': progress.get('total_chapters', 0),
                        'completed_chapters': progress.get('total_completed', 0),
                        'grade': None,
                        'is_current_user': member_uid == uid
                    })

                    # Add grade info if available
                    purpose = member_data.get('purpose')
                    if purpose == 'high_school' and member_data.get('highschool'):
                        leaderboard_data[-1]['grade'] = member_data['highschool'].get('grade')
                    elif purpose == 'after_tenth' and member_data.get('after_tenth'):
                        leaderboard_data[-1]['grade'] = member_data['after_tenth'].get('grade')

        except Exception as e:
            # Skip members with calculation errors
            continue

    # Sort by overall score (highest first)
    leaderboard_data.sort(key=lambda x: x['overall_score'], reverse=True)

    # Add rankings
    for i, user in enumerate(leaderboard_data, 1):
        user['rank'] = i

    # Find current user's rank
    current_user_rank = None
    current_user_data = None
    for user in leaderboard_data:
        if user['is_current_user']:
            current_user_rank = user['rank']
            current_user_data = user
            break

    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'bubble': {
            'id': bubble_id,
            'name': bubble_data.get('name'),
            'description': bubble_data.get('description'),
            'member_count': len(member_uids),
            'created_at': bubble_data.get('created_at'),
            'is_creator': is_creator
        },
        'leaderboard': leaderboard_data[:50],  # Top 50 in bubble
        'current_user_rank': current_user_rank,
        'current_user_data': current_user_data,
        'total_participants': len(leaderboard_data)
    }

    return render_template('bubble_detail.html', **context)

@app.route('/api/connections/send', methods=['POST'])
@require_login
def send_connection_request():
    """Send a connection request to another user"""
    uid = session['uid']

    try:
        data = request.get_json()
        target_uid = data.get('target_uid')
        message = data.get('message', 'Hi! I found you on StudyOS and thought we might study together.')

        if not target_uid:
            return jsonify({'error': 'Target user ID is required'}), 400

        if target_uid == uid:
            return jsonify({'error': 'Cannot send connection request to yourself'}), 400

        # Check if users are already connected
        user_data = get_user_data(uid)
        target_data = get_user_data(target_uid)

        if not user_data or not target_data:
            return jsonify({'error': 'User not found'}), 404

        # Check if already connected
        user_connections = user_data.get('connections', {})
        target_connections = target_data.get('connections', {})

        if target_uid in user_connections.get('accepted', []):
            return jsonify({'error': 'Already connected to this user'}), 400

        # Check if request already sent
        if target_uid in user_connections.get('pending_sent', []):
            return jsonify({'error': 'Connection request already sent'}), 400

        # Check if request already received
        if uid in target_connections.get('pending_received', []):
            return jsonify({'error': 'Connection request already exists'}), 400

        # Create connection request
        connection_id = f"{uid}_{target_uid}_{int(time.time())}"
        connection_data = {
            'connection_id': connection_id,
            'sender_uid': uid,
            'receiver_uid': target_uid,
            'status': 'pending',
            'message': message,
            'created_at': datetime.utcnow().isoformat()
        }

        # Save to connections collection
        db.collection('connections').document(connection_id).set(connection_data)

        # Update user connection lists
        db.collection('users').document(uid).update({
            'connections.pending_sent': firestore.ArrayUnion([target_uid])
        })
        db.collection('users').document(target_uid).update({
            'connections.pending_received': firestore.ArrayUnion([uid])
        })

        return jsonify({
            'success': True,
            'message': 'Connection request sent successfully'
        })

    except Exception as e:
        logger.error(f"Send connection error: {str(e)}")
        return jsonify({'error': 'Failed to send connection request', 'details': str(e)}), 500

@app.route('/api/connections/<connection_id>/accept', methods=['POST'])
@require_login
def accept_connection_request(connection_id):
    """Accept a connection request"""
    uid = session['uid']

    try:
        # Get connection request
        connection_doc = db.collection('connections').document(connection_id).get()
        if not connection_doc.exists:
            return jsonify({'error': 'Connection request not found'}), 404

        connection_data = connection_doc.to_dict()

        # Verify user is the receiver
        if connection_data['receiver_uid'] != uid:
            return jsonify({'error': 'Unauthorized'}), 403

        # Check if already accepted
        if connection_data['status'] != 'pending':
            return jsonify({'error': 'Connection request already processed'}), 400

        batch = db.batch()

        # Update connection status
        batch.update(db.collection('connections').document(connection_id), {
            'status': 'accepted',
            'accepted_at': datetime.utcnow().isoformat()
        })

        # Update user connection lists
        sender_uid = connection_data['sender_uid']
        batch.update(db.collection('users').document(uid), {
            'connections.accepted': firestore.ArrayUnion([sender_uid]),
            'connections.pending_received': firestore.ArrayRemove([sender_uid])
        })
        batch.update(db.collection('users').document(sender_uid), {
            'connections.accepted': firestore.ArrayUnion([uid]),
            'connections.pending_sent': firestore.ArrayRemove([uid])
        })

        batch.commit()

        return jsonify({'success': True, 'message': 'Connection accepted'})

    except Exception as e:
        logger.error(f"Accept connection error: {str(e)}")
        return jsonify({'error': 'Failed to accept connection', 'details': str(e)}), 500

@app.route('/api/connections/<connection_id>/decline', methods=['POST'])
@require_login
def decline_connection_request(connection_id):
    """Decline a connection request"""
    uid = session['uid']

    try:
        # Get connection request
        connection_doc = db.collection('connections').document(connection_id).get()
        if not connection_doc.exists:
            return jsonify({'error': 'Connection request not found'}), 404

        connection_data = connection_doc.to_dict()

        # Verify user is the receiver
        if connection_data['receiver_uid'] != uid:
            return jsonify({'error': 'Unauthorized'}), 403

        # Check if already processed
        if connection_data['status'] != 'pending':
            return jsonify({'error': 'Connection request already processed'}), 400

        batch = db.batch()

        # Update connection status
        batch.update(db.collection('connections').document(connection_id), {
            'status': 'declined'
        })

        # Update user connection lists
        sender_uid = connection_data['sender_uid']
        batch.update(db.collection('users').document(uid), {
            'connections.pending_received': firestore.ArrayRemove([sender_uid])
        })
        batch.update(db.collection('users').document(sender_uid), {
            'connections.pending_sent': firestore.ArrayRemove([uid])
        })

        batch.commit()

        return jsonify({'success': True, 'message': 'Connection request declined'})

    except Exception as e:
        logger.error(f"Decline connection error: {str(e)}")
        return jsonify({'error': 'Failed to decline connection', 'details': str(e)}), 500

@app.route('/api/connections/<connection_id>/block', methods=['POST'])
@require_login
def block_connection(connection_id):
    """Block a user (removes any connection and prevents future requests)"""
    uid = session['uid']

    try:
        # Get connection request
        connection_doc = db.collection('connections').document(connection_id).get()
        if not connection_doc.exists:
            return jsonify({'error': 'Connection request not found'}), 404

        connection_data = connection_doc.to_dict()
        other_uid = connection_data['sender_uid'] if connection_data['receiver_uid'] == uid else connection_data['receiver_uid']

        batch = db.batch()

        # Remove from all connection lists
        batch.update(db.collection('users').document(uid), {
            'connections.accepted': firestore.ArrayRemove([other_uid]),
            'connections.pending_sent': firestore.ArrayRemove([other_uid]),
            'connections.pending_received': firestore.ArrayRemove([other_uid])
        })
        batch.update(db.collection('users').document(other_uid), {
            'connections.accepted': firestore.ArrayRemove([uid]),
            'connections.pending_sent': firestore.ArrayRemove([uid]),
            'connections.pending_received': firestore.ArrayRemove([uid])
        })

        # Delete connection record
        batch.delete(db.collection('connections').document(connection_id))

        batch.commit()

        return jsonify({'success': True, 'message': 'User blocked'})

    except Exception as e:
        logger.error(f"Block connection error: {str(e)}")
        return jsonify({'error': 'Failed to block user', 'details': str(e)}), 500

@app.route('/api/connections', methods=['GET'])
@require_login
def get_connections():
    """Get user's connections list"""
    uid = session['uid']

    try:
        user_data = get_user_data(uid)
        if not user_data:
            return jsonify({'error': 'User data not found'}), 404

        connections = user_data.get('connections', {})

        # Get detailed info for each connection
        result = {
            'accepted': [],
            'pending_sent': [],
            'pending_received': []
        }

        # Get accepted connections
        for conn_uid in connections.get('accepted', []):
            conn_data = get_user_data(conn_uid)
            if conn_data:
                profile = {
                    'uid': conn_uid,
                    'name': conn_data.get('name'),
                    'purpose_display': conn_data.get('purpose', '').replace('_', ' ').title(),
                    'last_active': conn_data.get('last_login_date')
                }
                result['accepted'].append(profile)

        # Get pending sent requests
        for conn_uid in connections.get('pending_sent', []):
            conn_data = get_user_data(conn_uid)
            if conn_data:
                profile = {
                    'uid': conn_uid,
                    'name': conn_data.get('name'),
                    'purpose_display': conn_data.get('purpose', '').replace('_', ' ').title()
                }
                result['pending_sent'].append(profile)

        # Get pending received requests with connection IDs
        for conn_uid in connections.get('pending_received', []):
            # Find connection request
            conn_requests = db.collection('connections').where('sender_uid', '==', conn_uid).where('receiver_uid', '==', uid).where('status', '==', 'pending').stream()
            conn_request = None
            for req in conn_requests:
                conn_request = req
                break

            if conn_request:
                conn_data = get_user_data(conn_uid)
                if conn_data:
                    profile = {
                        'uid': conn_uid,
                        'name': conn_data.get('name'),
                        'purpose_display': conn_data.get('purpose', '').replace('_', ' ').title(),
                        'connection_id': conn_request.id,
                        'message': conn_request.to_dict().get('message', '')
                    }
                    result['pending_received'].append(profile)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Get connections error: {str(e)}")
        return jsonify({'error': 'Failed to get connections', 'details': str(e)}), 500
@app.route('/profile/resume')
@require_login
def profile_resume():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    purpose = user_data.get('purpose')
    academic_summary = ''
    if purpose == 'highschool' and user_data.get('highschool'):
        hs = user_data['highschool']
        academic_summary = f"{hs.get('board', '')} – Grade {hs.get('grade', '')}"
    elif purpose == 'exam' and user_data.get('exam'):
        academic_summary = f"{user_data['exam'].get('type', '')} Preparation"
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        academic_summary = f"{at.get('stream', '')} – Grade {at.get('grade', '')}"
    context = {
        'user': user_data,
        'name': user_data.get('name', 'Student'),
        'about': user_data.get('about', ''),
        'purpose_display': purpose.replace('_', ' ').title() if purpose else '',
        'academic_summary': academic_summary,
        'skills': user_data.get('skills', []),
        'hobbies': user_data.get('hobbies', []),
        'certificates': user_data.get('certificates', []),
        'achievements': user_data.get('achievements', []),
        'goals': [g for g in user_data.get('goals', []) if not g.get('completed', False)][:5],
        'profile_picture': user_data.get('profile_picture'),
        'profile_banner': user_data.get('profile_banner')
    }
    return render_template('profile_resume.html', **context)

def allowed_file(filename):
    """Check if file has allowed extension"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/profile/edit', methods=['GET', 'POST'])
@require_login
def profile_edit():
    uid = session['uid']
    if request.method == 'POST':
        # Handle profile picture removal
        action = request.form.get('action')
        if action == 'remove_pfp':
            # Remove profile picture from database
            db.collection('users').document(uid).update({'profile_picture': None})
            flash('Profile picture removed successfully!', 'success')
            return redirect(url_for('profile_edit'))
        
        # Handle banner removal
        if action == 'remove_banner':
            # Remove profile banner from database
            db.collection('users').document(uid).update({'profile_banner': None})
            flash('Profile banner removed successfully!', 'success')
            return redirect(url_for('profile_edit'))
        
        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                # Validate file
                if not allowed_file(file.filename):
                    flash('Invalid file type. Please upload JPG, PNG, or WebP images.', 'error')
                    return redirect(url_for('profile_edit'))
                
                if file.content_length > 5 * 1024 * 1024:  # 5MB limit
                    flash('File size too large. Please upload images smaller than 5MB.', 'error')
                    return redirect(url_for('profile_edit'))
                
                try:
                    # Create profile pictures directory if it doesn't exist
                    upload_dir = os.path.join(app.root_path, 'static', 'profile_pictures')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Generate unique filename
                    filename = secure_filename(f"{uid}_{int(time.time())}_{file.filename}")
                    file_path = os.path.join(upload_dir, filename)
                    
                    # Save file to local storage
                    file.save(file_path)
                    
                    # Store relative path in database (will be served via Flask route)
                    profile_picture_path = f"profile_pictures/{filename}"
                    
                    # Update user data with profile picture path
                    db.collection('users').document(uid).update({'profile_picture': profile_picture_path})
                    
                    logger.info(f"Profile picture saved successfully: {profile_picture_path}")
                    
                except Exception as e:
                    logger.error(f"Profile picture upload error: {str(e)}")
                    logger.error(f"Error type: {type(e).__name__}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    flash(f'Failed to upload profile picture: {str(e)}', 'error')
                    return redirect(url_for('profile_edit'))
        
        # Handle banner upload
        if 'profile_banner' in request.files:
            file = request.files['profile_banner']
            if file and file.filename:
                # Validate file
                if not allowed_file(file.filename):
                    flash('Invalid file type. Please upload JPG, PNG, or WebP images.', 'error')
                    return redirect(url_for('profile_edit'))
                
                if file.content_length > 10 * 1024 * 1024:  # 10MB limit for banners
                    flash('Banner file size too large. Please upload images smaller than 10MB.', 'error')
                    return redirect(url_for('profile_edit'))
                
                try:
                    # Process and convert image to banner format
                    try:
                        from PIL import Image
                        import io
                    except ImportError:
                        # PIL/Pillow not available, skip processing
                        flash('Banner processing not available. Please install Pillow for image processing.', 'warning')
                        # Still save the original file
                        upload_dir = os.path.join(app.root_path, 'static', 'profile_banners')
                        os.makedirs(upload_dir, exist_ok=True)
                        filename = secure_filename(f"{uid}_{int(time.time())}_banner{file.filename[file.filename.rfind('.'):]}")
                        file_path = os.path.join(upload_dir, filename)
                        file.save(file_path)
                        profile_banner_path = f"profile_banners/{filename}"
                        db.collection('users').document(uid).update({'profile_banner': profile_banner_path})
                        logger.info(f"Profile banner saved without processing: {profile_banner_path}")
                        flash('Profile banner uploaded successfully!', 'success')
                        return redirect(url_for('profile_edit'))
                    
                    # Read image
                    image = Image.open(file)
                    
                    # Convert to RGB if necessary (for JPEG compatibility)
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")
                    
                    # Resize to banner dimensions (1200x400 - good aspect ratio for banners)
                    banner_width = 1200
                    banner_height = 400
                    
                    # Calculate aspect ratios
                    target_ratio = banner_width / banner_height
                    image_ratio = image.width / image.height
                    
                    if image_ratio > target_ratio:
                        # Image is wider, crop width
                        new_width = int(image.height * target_ratio)
                        left = (image.width - new_width) // 2
                        image = image.crop((left, 0, left + new_width, image.height))
                    elif image_ratio < target_ratio:
                        # Image is taller, crop height
                        new_height = int(image.width / target_ratio)
                        top = (image.height - new_height) // 2
                        image = image.crop((0, top, image.width, top + new_height))
                    
                    # Resize to exact dimensions
                    image = image.resize((banner_width, banner_height), Image.Resampling.LANCZOS)
                    
                    # Save as WebP for better compression
                    output = io.BytesIO()
                    image.save(output, format='WebP', quality=85)
                    output.seek(0)
                    
                    # Create profile banners directory if it doesn't exist
                    upload_dir = os.path.join(app.root_path, 'static', 'profile_banners')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Generate unique filename
                    filename = secure_filename(f"{uid}_{int(time.time())}_banner.webp")
                    file_path = os.path.join(upload_dir, filename)
                    
                    # Save processed image
                    with open(file_path, 'wb') as f:
                        f.write(output.getvalue())
                    
                    # Store relative path in database
                    profile_banner_path = f"profile_banners/{filename}"
                    
                    # Update user data with profile banner path
                    db.collection('users').document(uid).update({'profile_banner': profile_banner_path})
                    
                    logger.info(f"Profile banner processed and saved successfully: {profile_banner_path}")
                    
                except Exception as e:
                    logger.error(f"Profile banner processing error: {str(e)}")
                    logger.error(f"Error type: {type(e).__name__}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    flash(f'Failed to process banner image: {str(e)}', 'error')
                    return redirect(url_for('profile_edit'))
        
        updates = {
            'name': request.form.get('name'),
            'about': request.form.get('about'),
            'skills': [s.strip() for s in request.form.get('skills', '').split(',') if s.strip()],
            'hobbies': [h.strip() for h in request.form.get('hobbies', '').split(',') if h.strip()],
            'certificates': [c.strip() for c in request.form.get('certificates', '').split(',') if c.strip()],
            'achievements': [a.strip() for a in request.form.get('achievements', '').split(',') if a.strip()]
        }
        db.collection('users').document(uid).update(updates)
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile_resume'))
    user_data = get_user_data(uid)
    context = {
        'user': user_data,
        'name': user_data.get('name', ''),
        'about': user_data.get('about', ''),
        'skills': ', '.join(user_data.get('skills', [])),
        'hobbies': ', '.join(user_data.get('hobbies', [])),
        'certificates': ', '.join(user_data.get('certificates', [])),
        'achievements': ', '.join(user_data.get('achievements', [])),
        'profile_picture': user_data.get('profile_picture')
    }
    return render_template('profile_edit.html', **context)

# ============================================================================
# PROFILE PICTURE SERVING
# ============================================================================

@app.route('/profile_pictures/<filename>')
def serve_profile_picture(filename):
    """Serve profile pictures from local storage"""
    try:
        return send_from_directory(
            os.path.join(app.root_path, 'static', 'profile_pictures'),
            filename
        )
    except FileNotFoundError:
        # Return default profile picture or 404
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'default-profile.png'
        ), 404

# ============================================================================
# ACADEMIC DASHBOARD

# ============================================================================

@app.route('/academic')
@require_login
def academic_dashboard():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    purpose = user_data.get('purpose')
    syllabus_purpose = {
        'high_school': 'highschool',
        'exam_prep': 'exam',
        'after_tenth': 'after_tenth'
    }.get(purpose, purpose)
    syllabus = {}
    if purpose == 'high_school' and user_data.get('highschool'):
        hs = user_data['highschool']
        syllabus = get_syllabus(syllabus_purpose, hs.get('board'), hs.get('grade'))
    elif purpose == 'exam_prep' and user_data.get('exam'):
        syllabus = get_syllabus(syllabus_purpose, user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        syllabus = get_syllabus(syllabus_purpose, 'CBSE', at.get('grade'), at.get('subjects', []))
    progress_data = calculate_academic_progress(user_data)
    chapters_completed = user_data.get('chapters_completed', {})
    # Merge institution and class exclusions for UI consistency
    all_exclusions = {}
    inst_id = user_data.get('institution_id')
    class_ids = user_data.get('class_ids', [])
    if inst_id:
        try:
            inst_excl = db.collection('institutions').document(inst_id).collection('syllabus_exclusions').document('current').get()
            if inst_excl.exists: all_exclusions.update(inst_excl.to_dict().get('chapters', {}))
        except: pass
    if class_ids:
        for cid in class_ids:
            try:
                class_excl = db.collection('classes').document(cid).collection('excluded_chapters').document('current').get()
                if class_excl.exists: all_exclusions.update(class_excl.to_dict().get('chapters', {}))
            except: pass
    academic_exclusions = user_data.get('academic_exclusions', {})
    all_exclusions.update(academic_exclusions)
    # Build flat chapter list with completion status for left panel
    syllabus_flat = {}
    for subject_name, subject_data in syllabus.items():
        chapters = subject_data.get('chapters', {})
        syllabus_flat[subject_name] = {}
        for chapter_name in chapters.keys():
            exclusion_key = f"{subject_name}::{chapter_name}"
            is_excluded = all_exclusions.get(exclusion_key, False)
            is_done = False
            # Check completion even if excluded (but UI will show it as excluded)
            is_done = chapters_completed.get(subject_name, {}).get(chapter_name, False)
            syllabus_flat[subject_name][chapter_name] = {
                'completed': is_done,
                'excluded': is_excluded
            }
    # Goals and tasks for right panel
    goals = user_data.get('goals', [])
    tasks = user_data.get('tasks', [])
    results = user_data.get('exam_results', [])
    # Stats for results
    total_exams = len(results)
    avg_percentage = 0
    avg_percentage = calculate_average_percentage(results)
    # Subjects for goal dropdown
    subjects = list(syllabus.keys())
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'syllabus': syllabus,
        'syllabus_flat': syllabus_flat,
        'progress_data': progress_data,
        'goals': goals,
        'tasks': tasks,
        'results': sorted(results, key=lambda x: x.get('date', ''), reverse=True),
        'total_exams': total_exams,
        'avg_percentage': avg_percentage,
        'subjects': subjects,
        'test_types': TEST_TYPES
    }
    return render_template('academic_dashboard.html', **context)

@app.route('/master-library')
@require_login
def master_library():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'library_data': ACADEMIC_SYLLABI,
        'active_nav': 'library'
    }
    return render_template('master_library.html', **context)

@app.route('/academic/subject/<subject_name>/chapter/<chapter_name>')
@require_login
def chapter_detail(subject_name, chapter_name):
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    purpose = user_data.get('purpose')
    syllabus_purpose = {
        'high_school': 'highschool',
        'exam_prep': 'exam',
        'after_tenth': 'after_tenth'
    }.get(purpose, purpose)
    syllabus = {}
    if purpose == 'high_school' and user_data.get('highschool'):
        hs = user_data['highschool']
        syllabus = get_syllabus(syllabus_purpose, hs.get('board'), hs.get('grade'))
    elif purpose == 'exam_prep' and user_data.get('exam'):
        syllabus = get_syllabus(syllabus_purpose, user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        syllabus = get_syllabus(syllabus_purpose, 'CBSE', at.get('grade'), at.get('subjects', []))
    subject_data = syllabus.get(subject_name, {})
    if not subject_data:
        flash('Subject not found', 'error')
        return redirect(url_for('academic_dashboard'))
    chapters = subject_data.get('chapters', {})
    chapter_data = chapters.get(chapter_name, {})
    if not chapter_data:
        flash('Chapter not found', 'error')
        return redirect(url_for('academic_dashboard'))
    topics = chapter_data.get('topics', [])
    chapters_completed = user_data.get('chapters_completed', {})
    is_completed = chapters_completed.get(subject_name, {}).get(chapter_name, False)
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'subject_name': subject_name,
        'chapter_name': chapter_name,
        'topics': topics,
        'is_completed': is_completed
    }
    return render_template('chapter_detail.html', **context)

@app.route('/academic/toggle_chapter', methods=['POST'])
@require_login
def toggle_chapter_completion():
    uid = session['uid']
    subject_name = request.form.get('subject_name')
    chapter_name = request.form.get('chapter_name')
    if not subject_name or not chapter_name:
        flash('Invalid request', 'error')
        return redirect(url_for('academic_dashboard'))
    user_data = get_user_data(uid)
    chapters_completed = user_data.get('chapters_completed', {})
    if subject_name not in chapters_completed:
        chapters_completed[subject_name] = {}
    current_status = chapters_completed[subject_name].get(chapter_name, False)
    chapters_completed[subject_name][chapter_name] = not current_status
    db.collection('users').document(uid).update({'chapters_completed': chapters_completed})
    # Redirect back to academic dashboard (the chapter list lives there now)
    return redirect(url_for('academic_dashboard'))

@app.route('/academic/toggle_chapter_exclusion', methods=['POST'])
@require_login
def toggle_chapter_exclusion():
    uid = session['uid']
    subject_name = None
    chapter_name = None
    if not subject_name or not chapter_name:
        subject_name = request.form.get('subject_name')
        chapter_name = request.form.get('chapter_name')
    if not subject_name or not chapter_name:
        return redirect(url_for('academic_dashboard'))
    key = f"{subject_name}::{chapter_name}"
    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    exclusions = user_data.get('academic_exclusions', {})
    # Toggle exclusion (REVERSIBLE)
    if exclusions.get(key):
        exclusions.pop(key)
    else:
        exclusions[key] = True
    user_ref.update({'academic_exclusions': exclusions})
    return redirect(url_for('academic_dashboard'))

# ============================================================
# STUDY MODE (Pomodoro) ChatGPT

# ============================================================

@app.route('/study-mode')
@require_login
def study_mode():
    uid = session['uid']
    user_data = get_user_data(uid)
    name = user_data.get('name', 'Student') if user_data else 'Student'
    todos = db.collection('users').document(uid).collection('study_todos').stream()
    todo_list = [{'id': t.id, **t.to_dict()} for t in todos]
    
    return render_template(
        'study_mode.html',
        name=name,
        todos=todo_list
    )

@app.route('/study-mode/time', methods=['POST'])
@require_login
def study_time():
    uid = session['uid']
    data = request.json
    seconds = int(data.get('seconds', 0))
    local_hour = data.get('local_hour')
    local_weekday = data.get('local_weekday')
    db.collection('users').document(uid).set({
        'study_mode': {'total_seconds': Increment(seconds)}
    }, merge=True)
    # Record/Update session for heatmap
    # Using YYYY-MM-DD-HH as a unique key for the hour to avoid document spam
    now = datetime.utcnow()
    hour_id = now.strftime("%Y-%m-%d-%H")
    session_ref = db.collection('users').document(uid).collection('study_sessions').document(hour_id)
    session_data = {
        'start_time': now.isoformat(),
        'duration_seconds': Increment(seconds),
        'last_updated': now.isoformat()
    }
    if local_hour is not None:
        session_data['local_hour'] = local_hour
    if local_weekday is not None:
        session_data['local_weekday'] = local_weekday
    session_ref.set(session_data, merge=True)
    return jsonify(ok=True)

@app.route('/study-mode/todo/add', methods=['POST'])
@require_login
def add_study_todo():
    uid = session['uid']
    text = request.json['text']
    db.collection('users').document(uid).collection('study_todos').add({
            'text': text,
            'done': False
        })
    return jsonify(ok=True)

@app.route('/study-mode/todo/<tid>/toggle', methods=['POST'])
@require_login
def toggle_study_todo(tid):
    uid = session['uid']
    ref = db.collection('users').document(uid).collection('study_todos').document(tid)
    doc = ref.get()
    ref.update({'done': not doc.to_dict().get('done', False)})
    return jsonify(ok=True)

@app.route('/study-mode/todo/<tid>/delete', methods=['POST'])
@require_login
def delete_study_todo(tid):
    uid = session['uid']
    db.collection('users').document(uid).collection('study_todos').document(tid).delete()
    return jsonify(ok=True)
#=============================================================================
# DOC - V1 - ChatGPT - Temporary Not Perfect
#=============================================================================

# ============================================================================
# GOALS (POST handler only — rendered inside academic_dashboard)

# ============================================================================

@app.route('/goals', methods=['GET', 'POST'])
@require_login
def goals_dashboard():
    uid = session['uid']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            title = request.form.get('title')
            if title:
                user_data = get_user_data(uid)
                goals = user_data.get('goals', [])
                goals.append({
                    'id': len(goals), 'title': title,
                    'description': request.form.get('description', ''),
                    'subject': request.form.get('subject', ''),
                    'target_date': request.form.get('target_date', ''),
                    'completed': False,
                    'created_at': datetime.utcnow().isoformat()
                })
                db.collection('users').document(uid).update({'goals': goals})
                flash('Goal added!', 'success')
        elif action == 'toggle':
            goal_id = int(request.form.get('goal_id'))
            user_data = get_user_data(uid)
            goals = user_data.get('goals', [])
            for g in goals:
                if g.get('id') == goal_id:
                    g['completed'] = not g.get('completed', False)
                    break
            db.collection('users').document(uid).update({'goals': goals})
        elif action == 'delete':
            goal_id = int(request.form.get('goal_id'))
            user_data = get_user_data(uid)
            goals = [g for g in user_data.get('goals', []) if g.get('id') != goal_id]
            db.collection('users').document(uid).update({'goals': goals})
            flash('Goal deleted!', 'success')
        return redirect(url_for('academic_dashboard'))
    # GET fallback — redirect to academic dashboard
    return redirect(url_for('academic_dashboard'))

# ============================================================================
# TASKS

# ============================================================================

@app.route('/tasks', methods=['GET', 'POST'])
@require_login
def tasks_dashboard():
    uid = session['uid']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            title = request.form.get('title')
            if title:
                user_data = get_user_data(uid)
                tasks = user_data.get('tasks', [])
                tasks.append({
                    'id': len(tasks), 'title': title,
                    'description': request.form.get('description', ''),
                    'goal_id': request.form.get('goal_id', ''),
                    'due_date': request.form.get('due_date', ''),
                    'completed': False,
                    'created_at': datetime.utcnow().isoformat()
                })
                db.collection('users').document(uid).update({'tasks': tasks})
                flash('Task added!', 'success')
        elif action == 'toggle':
            task_id = int(request.form.get('task_id'))
            user_data = get_user_data(uid)
            tasks = user_data.get('tasks', [])
            for t in tasks:
                if t.get('id') == task_id:
                    t['completed'] = not t.get('completed', False)
                    break
            db.collection('users').document(uid).update({'tasks': tasks})
        elif action == 'delete':
            task_id = int(request.form.get('task_id'))
            user_data = get_user_data(uid)
            tasks = [t for t in user_data.get('tasks', []) if t.get('id') != task_id]
            db.collection('users').document(uid).update({'tasks': tasks})
            flash('Task deleted!', 'success')
        return redirect(url_for('academic_dashboard'))
    return redirect(url_for('academic_dashboard'))

# ============================================================================
# RESULTS

# ============================================================================

@app.route('/results', methods=['POST'])
@require_login
def results_dashboard():
    uid = session['uid']
    action = request.form.get('action')
    user_data = get_user_data(uid)
    results = user_data.get('exam_results', [])
    if action == 'add':
        test_types = request.form.get('test_types')          # dropdown value
        subject = request.form.get('subject', '')
        score = request.form.get('score')
        max_score = request.form.get('max_score')
        exam_date = request.form.get('exam_date')
        if test_types and score:
            results.append({
                'id': int(datetime.utcnow().timestamp() * 1000),  # robust unique id
                'test_types': test_types,
                'subject': subject,
                'score': float(score),
                'max_score': float(max_score) if max_score else 100.0,
                'exam_date': exam_date,
                'created_at': datetime.utcnow().isoformat()
            })
            db.collection('users').document(uid).update({
                'exam_results': results
            })
            flash('Result added!', 'success')
    elif action == 'delete':
        result_id = request.form.get('result_id')
        if result_id:
            results = [
                r for r in results
                if str(r.get('id')) != str(result_id)
            ]
            db.collection('users').document(uid).update({
                'exam_results': results
            })
            flash('Result deleted!', 'success')
    return redirect(url_for('academic_dashboard'))

# ============================================================================
# STATISTICS

# ============================================================================

@app.route('/statistics')
@require_login
def statistics_dashboard():
    uid = session['uid']
    user = get_user_data(uid)
    # --- PRODUCTIVITY STATS ---
    goals = user.get('goals', [])
    tasks = user.get('tasks', [])
    total_goals = len(goals)
    completed_goals = sum(1 for g in goals if g.get('completed'))
    goals_pct = round((completed_goals / total_goals) * 100) if total_goals > 0 else 0
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.get('completed'))
    tasks_pct = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
    # --- EXAM ANALYTICS ---
    results = user.get('exam_results', [])
    # 1. Overall Average per Test Type (Timeline Bar Chart)
    exam_map = {}
    timeline = []
    # 2. Subject-wise Performance (Line Chart)
    # Structure: {'Math': [{'date': '...', 'pct': 80}, ...], 'Science': ...}
    subject_performance = {}
    for r in results:
        if not r.get('max_score'):
            continue
        pct = (r['score'] / r['max_score']) * 100
        # For Overall Stats
        et = r.get('test_types') # Changed from 'test_type' to 'test_types' to match data entry
        if et:
            exam_map.setdefault(et, []).append(pct)
        if r.get('exam_date'):
            timeline.append({
                'date': r['exam_date'],
                'percentage': round(pct, 2)
            })
            # For Subject Stats
            subj = r.get('subject')
            if subj:
                subject_performance.setdefault(subj, []).append({
                    'date': r['exam_date'],
                    'percentage': round(pct, 2)
                })
    exam_avg = {
        k: round(sum(v) / len(v), 2)
        for k, v in exam_map.items()
    }
    timeline = sorted(timeline, key=lambda x: x['date'])
    # Sort subject performance by date too
    for subj in subject_performance:
        subject_performance[subj] = sorted(subject_performance[subj], key=lambda x: x['date'])
    return render_template(
        'statistics.html',
        exam_avg=exam_avg,
        timeline=timeline,
        streak=user.get('login_streak', 0),
        productivity={
            'goals': {'total': total_goals, 'completed': completed_goals, 'pct': goals_pct},
            'tasks': {'total': total_tasks, 'completed': completed_tasks, 'pct': tasks_pct}
        },
        subject_performance=subject_performance,
        subjects=sorted(list(subject_performance.keys())), # Only show subjects that have data
        name=user.get('name', 'Student')
    )

# ============================================================================
# PROJECTS (FUTURE FEATURE)

# ============================================================================
# @app.route('/projects', methods=['GET', 'POST'])
# @require_login
# def projects_dashboard():
#     uid = session['uid']
#     if request.method == 'POST':
#         action = request.form.get('action')
#         if action == 'add':
#             title = request.form.get('title')
#             if title:
#                 user_data = get_user_data(uid)
#                 projects = user_data.get('projects', [])
#                 projects.append({
#                     'id': len(projects), 'title': title,
#                     'description': request.form.get('description', ''),
#                     'subject': request.form.get('subject', ''),
#                     'status': request.form.get('status', 'Not Started'),
#                     'created_at': datetime.utcnow().isoformat()
#                 })
#                 db.collection('users').document(uid).update({'projects': projects})
#                 flash('Project added!', 'success')
#         elif action == 'update_status':
#             project_id = int(request.form.get('project_id'))
#             user_data = get_user_data(uid)
#             projects = user_data.get('projects', [])
#             for p in projects:
#                 if p.get('id') == project_id:
#                     p['status'] = request.form.get('status')
#                     break
#             db.collection('users').document(uid).update({'projects': projects})
#         elif action == 'delete':
#             project_id = int(request.form.get('project_id'))
#             user_data = get_user_data(uid)
#             projects = [p for p in user_data.get('projects', []) if p.get('id') != project_id]
#             db.collection('users').document(uid).update({'projects': projects})
#             flash('Project deleted!', 'success')
#         return redirect(url_for('academic_dashboard'))
#     return redirect(url_for('academic_dashboard'))

# ============================================================================
# INTERESTS → CAREERS → COURSES → INTERNSHIPS

# ============================================================================

@app.route('/interests')
@require_login
def interests_dashboard():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    interests = user_data.get('interests', {})
    if isinstance(interests, list):
        interests = {'careers': [], 'courses': [], 'internships': []}
    saved_career_ids = interests.get('careers', [])
    saved_careers = [get_career_by_id(cid) for cid in saved_career_ids if get_career_by_id(cid)]
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'saved_careers': saved_careers,
        'all_careers': CAREERS_DATA,
        'all_courses': COURSES_DATA,
        'all_internships': INTERNSHIPS_DATA,
    }
    return render_template('interests_dashboard.html', **context)

@app.route('/career/<career_id>')
@require_login
def career_detail(career_id):
    uid = session['uid']
    user_data = get_user_data(uid)
    career = get_career_by_id(career_id)
    if not career:
        flash('Career not found', 'error')
        return redirect(url_for('interests_dashboard'))
    # Check if user has this career saved
    interests = user_data.get('interests', {})
    if isinstance(interests, list):
        interests = {'careers': [], 'courses': [], 'internships': []}
    is_saved = career_id in interests.get('careers', [])
    # Resolve related courses and internships
    related_courses = [get_course_by_id(cid) for cid in career.get('courses', []) if get_course_by_id(cid)]
    related_internships = [get_internship_by_id(iid) for iid in career.get('internships', []) if get_internship_by_id(iid)]
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'career': career,
        'is_saved': is_saved,
        'related_courses': related_courses,
        'related_internships': related_internships,
    }
    return render_template('career_detail.html', **context)

@app.route('/career/<career_id>/toggle', methods=['POST'])
@require_login
def toggle_career_interest(career_id):
    uid = session['uid']
    user_data = get_user_data(uid)
    interests = user_data.get('interests', {})
    if isinstance(interests, list):
        interests = {'careers': [], 'courses': [], 'internships': []}
    saved = interests.get('careers', [])
    if career_id in saved:
        saved.remove(career_id)
    else:
        saved.append(career_id)
    interests['careers'] = saved
    db.collection('users').document(uid).update({'interests': interests})
    return redirect(url_for('career_detail', career_id=career_id))

@app.route('/course/<course_id>')
@require_login
def course_detail(course_id):
    uid = session['uid']
    user_data = get_user_data(uid)
    course = get_course_by_id(course_id)
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('interests_dashboard'))
    related_careers = [get_career_by_id(cid) for cid in course.get('related_careers', []) if get_career_by_id(cid)]
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'course': course,
        'related_careers': related_careers,
    }
    return render_template('course_detail.html', **context)

@app.route('/internship/<internship_id>')
@require_login
def internship_detail(internship_id):
    uid = session['uid']
    user_data = get_user_data(uid)
    internship = get_internship_by_id(internship_id)
    if not internship:
        flash('Internship not found', 'error')
        return redirect(url_for('interests_dashboard'))
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'internship': internship,
    }
    return render_template('internship_detail.html', **context)

# ============================================================================
# LEGACY / COMPATIBILITY ROUTES

# ============================================================================

@app.route('/dashboard/highschool')
@require_login
def dashboard_highschool():
    return redirect(url_for('profile_dashboard'))

@app.route('/dashboard/exam')
@require_login
def dashboard_exam():
    return redirect(url_for('profile_dashboard'))

@app.route('/dashboard/after_tenth')
@require_login
def dashboard_after_tenth():
    return redirect(url_for('profile_dashboard'))

@app.route('/todo', methods=['GET', 'POST'])
@require_login
def todo():
    return redirect(url_for('academic_dashboard'))

@app.route('/about')
@require_login
def about():
    uid = session['uid']
    user_data = get_user_data(uid)
    return render_template('about.html', user=user_data, name=user_data.get('name') if user_data else 'Student')

@app.route('/settings', methods=['GET', 'POST'])
@require_login
def settings():
    """User settings page for account preferences and academic configuration"""
    uid = session['uid']
    user_data = get_user_data(uid) or {}
    if request.method == 'POST':
        action = request.form.get('action', 'general')
        if action == 'general':
            # Handle appearance and notification settings
            theme = request.form.get('theme', 'dark')
            email_notifications = request.form.get('email_notifications') == 'on'
            updates = {
                'settings': {
                    'theme': theme,
                    'email_notifications': email_notifications
                }
            }
            db.collection('users').document(uid).update(updates)
            flash('General settings updated successfully!', 'success')
        elif action == 'academic':
            # Handle academic configuration change with WARNING
            confirm_delete = request.form.get('confirm_delete') == 'on'
            if not confirm_delete:
                flash('You must confirm data deletion to change academic settings.', 'error')
                return redirect(url_for('settings'))
            new_purpose = request.form.get('purpose')
            new_board = request.form.get('board')
            new_grade = request.form.get('grade')
            # Fields to clear when changing academic config
            updates = {
                'purpose': new_purpose,
                'chapters_completed': {},  # Clear all progress
                'exam_results': [],        # Clear exam results
                'time_studied': 0,         # Reset study time
                'highschool': None,
                'exam': None,
                'after_tenth': None,
            }
            # Set new academic data based on purpose
            if new_purpose == 'high_school':
                updates['highschool'] = {'board': new_board, 'grade': new_grade}
            elif new_purpose == 'exam_prep':
                exam_type = request.form.get('exam_type', 'JEE')
                updates['exam'] = {'type': exam_type}
            elif new_purpose == 'after_tenth':
                stream = request.form.get('stream', 'Science')
                grade = request.form.get('grade_after')
                updates['after_tenth'] = {
                    'grade': grade,
                    'stream': stream,
                    'subjects': []
                }
            db.collection('users').document(uid).update(updates)
            flash('Academic configuration updated. All previous progress has been reset.', 'success')
        elif action == 'account':
            # Handle account updates
            name = request.form.get('name')
            if name:
                db.collection('users').document(uid).update({'name': name})
                flash('Profile name updated!', 'success')
        return redirect(url_for('settings'))
    # Get current settings or defaults
    current_settings = user_data.get('settings', {})
    # Get available options for academic configuration
    available_boards = ['CBSE', 'ICSE', 'State Board']
    available_grades = ['9', '10', '11', '12']
    available_exams = ['JEE', 'NEET', 'SAT', 'ACT', 'GRE', 'GMAT', 'CAT', 'UPSC', 'SSC', 'Bank PO', 'Other']
    available_streams = ['Science (PCM)', 'Science (PCB)', 'Commerce', 'Arts', 'Diploma', 'Vocational']
    return render_template('settings.html',
                         user=user_data,
                         name=user_data.get('name') or 'Student',
                         settings=current_settings,
                         available_boards=available_boards,
                         available_grades=available_grades,
                         available_exams=available_exams,
                         available_streams=available_streams)

@app.route('/contact', methods=['GET', 'POST'])
@require_login
def contact():
    """Contact/Support page for user inquiries - sends email to support team"""
    uid = session['uid']
    user_data = get_user_data(uid) or {}
    if request.method == 'POST':
        subject = request.form.get('subject')
        message = request.form.get('message')
        category = request.form.get('category', 'general')
        if not subject or not message:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('contact'))
        # Build email content
        email_body = f"""
New Support Request from StudyOS
User Details:
- Name: {user_data.get('name', 'Unknown')}
- Email: {user_data.get('email', 'Unknown')}
- User ID: {uid}
- Category: {category}
Subject: {subject}
Message:
{message}
---
This email was sent from the StudyOS contact form.
        """
        try:
            # Send email to support (sample email - user will change later)
            msg = Message(
                subject=f"[StudyOS Support] {subject}",
                sender=app.config.get('MAIL_DEFAULT_SENDER', 'noreply@studyos.app'),
                recipients=['support@studyos.example.com'],  # Sample email - change this
                body=email_body
            )
            mail.send(msg)
            # Also store in Firestore as backup
            ticket = {
                'uid': uid,
                'user_email': user_data.get('email'),
                'user_name': user_data.get('name'),
                'subject': subject,
                'message': message,
                'category': category,
                'status': 'open',
                'created_at': datetime.utcnow().isoformat(),
                'email_sent': True
            }
            db.collection('support_tickets').add(ticket)
            flash('Your message has been sent! We will get back to you within 24-48 hours.', 'success')
            logger.info("support_ticket_created", user_id=uid, subject=subject, category=category)
        except Exception as e:
            logger.error("contact_email_error", error=str(e), user_id=uid)
            # Still store ticket even if email fails
            ticket = {
                'uid': uid,
                'user_email': user_data.get('email'),
                'user_name': user_data.get('name'),
                'subject': subject,
                'message': message,
                'category': category,
                'status': 'open',
                'created_at': datetime.utcnow().isoformat(),
                'email_sent': False,
                'email_error': str(e)
            }
            db.collection('support_tickets').add(ticket)
            flash('Your message has been saved. Our team will review it shortly.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html',
                         user=user_data,
                         name=user_data.get('name') or 'Student')

# ============================================================================
# INSTITUTIONAL ECOSYSTEM (PHASE 2)

# ============================================================================

# Legacy require_role deprecated. Use require_institution_role instead.

@app.route('/institution/join', methods=['GET', 'POST'])
@require_login
def institution_join():
    """Redirect to student join class if student, or teacher join if applicable."""
    account_type = _get_account_type()
    if account_type == 'teacher':
        return redirect(url_for('institution_teacher_join'))
    return redirect(url_for('student_join_class'))

@app.route('/institution/dashboard')
@require_institution_role(['admin', 'teacher'])
def institution_dashboard_redirect():
    """Redirect legacy dashboard to specific V2 dashboards."""
    account_type = _get_account_type()
    if account_type == 'admin':
        return redirect(url_for('institution_admin_dashboard'))
    return redirect(url_for('institution_teacher_dashboard'))

@app.route('/institution/generate_invite', methods=['POST'])
@require_institution_role(['admin', 'teacher'])
def generate_invite():
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    class_id = request.form.get('class_id')
    role = request.form.get('role', 'student')
    # Generate 6-char code
    code = _generate_code(6)
    db.collection('invites').add({
        'code': code,
        'institution_id': inst_id,
        'class_id': class_id,
        'role': role,
        'created_by': uid,
        'created_at': datetime.utcnow().isoformat(),
        'used': False,
        'one_time': True # or configurable
    })
    return jsonify({'code': code})

@app.route('/institution/nudge', methods=['POST'])
@require_institution_role(['teacher', 'admin'])
def send_nudge():
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    student_uid = request.json.get('student_uid')
    message = request.json.get('message', 'Your teacher has sent you a reminder to stay on track!')
    
    if not inst_id:
        return jsonify({'success': False, 'message': 'No institution context found.'}), 400

    # Create notification
    db.collection('institutions').document(inst_id).collection('notifications').add({
        'recipient_uid': student_uid,
        'sender_uid': uid,
        'sender_name': profile.get('name', 'Instructor'),
        'message': message,
        'type': 'nudge',
        'read': False,
        'created_at': datetime.utcnow().isoformat()
    })
    return jsonify({'success': True, 'message': 'Nudge sent!'})

@app.route('/institution/broadcast', methods=['POST'])
@require_institution_role(['teacher', 'admin'])
def broadcast_message():
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    message = request.form.get('message')
    class_id = request.form.get('class_id')
    
    if not message:
        return jsonify({'error': 'Message required'}), 400
    
    # Get target students
    student_uids = []
    if class_id:
        class_doc = db.collection(CLASSES_COL).document(class_id).get()
        if class_doc.exists:
            student_uids = class_doc.to_dict().get('student_uids', [])
    else:
        # Broadcast to all students in institution
        users_ref = db.collection('users').where('institution_id', '==', inst_id)
        student_uids = [u.id for u in users_ref.stream()]
        
    if student_uids:
        batch = db.batch()
        notif_ref = db.collection('institutions').document(inst_id).collection('notifications')
        for s_uid in student_uids:
            batch.set(notif_ref.document(), {
                'recipient_uid': s_uid,
                'sender_uid': uid,
                'sender_name': profile.get('name', 'Instructor'),
                'message': message,
                'type': 'broadcast',
                'read': False,
                'created_at': datetime.utcnow().isoformat()
            })
        batch.commit()
        
    flash(f'Message sent to {len(student_uids)} students!', 'success')
    dest = 'institution_admin_dashboard' if profile.get('account_type') == 'admin' else 'institution_teacher_dashboard'
    return redirect(url_for(dest))

@app.route('/institution/class/<class_id>/syllabus', methods=['GET', 'POST'])
@require_institution_role(['teacher', 'admin'])
def manage_class_syllabus(class_id):
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    # Verify class belongs to institution
    class_doc = db.collection(CLASSES_COL).document(class_id).get()
    if not class_doc.exists or class_doc.to_dict().get('institution_id') != inst_id:
        abort(403)
    class_data = class_doc.to_dict()
    if request.method == 'POST':
        # Handle exclusion toggle
        subject = request.form.get('subject')
        chapter = request.form.get('chapter')
        action = request.form.get('action')  # 'exclude' or 'include'
        exclusion_key = f"{subject}::{chapter}"
        exclusions_ref = db.collection('classes').document(class_id).collection('excluded_chapters').document('current')
        exclusions_doc = exclusions_ref.get()
        exclusions = exclusions_doc.to_dict().get('chapters', {}) if exclusions_doc.exists else {}
        if action == 'exclude':
            exclusions[exclusion_key] = True
        else:
            exclusions.pop(exclusion_key, None)
        exclusions_ref.set({'chapters': exclusions})
        flash(f'Chapter {chapter} {"excluded" if action == "exclude" else "included"}!', 'success')
        return redirect(url_for('manage_class_syllabus', class_id=class_id))
    # Get current exclusions
    exclusions_doc = db.collection('classes').document(class_id).collection('excluded_chapters').document('current').get()
    exclusions = exclusions_doc.to_dict().get('chapters', {}) if exclusions_doc.exists else {}
    # Get syllabus based on class metadata
    purpose = class_data.get('purpose', 'highschool')
    syllabus_purpose = {
        'high_school': 'highschool',
        'exam_prep': 'exam',
        'after_tenth': 'after_tenth'
    }.get(purpose, purpose)
    board = class_data.get('board', 'CBSE')
    grade = class_data.get('grade', '10')
    syllabus = get_syllabus(syllabus_purpose, board, grade)
    if not syllabus:
        syllabus = {} # Fallback to empty if not found
    context = {
        'profile': profile,
        'class_id': class_id,
        'class_data': class_data,
        'syllabus': syllabus,
        'exclusions': exclusions
    }
    return render_template('class_syllabus.html', **context)

@app.route('/institution/student/<student_uid>')
@require_institution_role(['teacher', 'admin'])
def student_detail(student_uid):
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    # Get student data
    student_doc = db.collection('users').document(student_uid).get()
    if not student_doc.exists:
        abort(404)
    student_data = student_doc.to_dict()
    # Verify student belongs to same institution
    if student_data.get('institution_id') != inst_id:
        abort(403)
    # Calculate progress
    progress_data = calculate_academic_progress(student_data)
    # Get recent results
    results = student_data.get('exam_results', [])
    recent_results = sorted(results, key=lambda x: x.get('date', ''), reverse=True)[:5]
    # Get study sessions (if available)
    sessions_ref = db.collection('users').document(student_uid).collection('study_sessions').order_by('start_time', direction=firestore.Query.DESCENDING).limit(10)
    sessions = [s.to_dict() for s in sessions_ref.stream()]
    context = {
        'profile': profile,
        'student': student_data,
        'student_uid': student_uid,
        'progress_data': progress_data,
        'recent_results': recent_results,
        'sessions': sessions
    }
    return render_template('student_detail.html', **context)

@app.route('/institution/students')
@require_institution_role(['teacher', 'admin'])
def all_students():
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    if not inst_id:
        flash('No institution assigned.', 'error')
        return redirect(url_for('profile_dashboard'))
    # Get all students in institution
    students_ref = db.collection('users').where('institution_id', '==', inst_id)
    students_docs = list(students_ref.stream())
    students_list = []
    for s_doc in students_docs:
        s_data = s_doc.to_dict()
        s_data['uid'] = s_doc.id
        # Calculate quick stats
        progress = calculate_academic_progress(s_data, uid=s_doc.id)
        s_data['progress_overall'] = progress.get('overall', 0)
        # Last login
        last_login = s_data.get('last_login_date', '')
        if last_login:
            try:
                last_date = datetime.fromisoformat(last_login).date() if isinstance(last_login, (str, datetime)) else last_login
                days_ago = (date.today() - last_date).days
                s_data['days_inactive'] = days_ago
            except:
                s_data['days_inactive'] = 999
        else:
            s_data['days_inactive'] = 999
        # Get class names
        class_ids = s_data.get('class_ids', [])
        class_names = []
        for cid in class_ids:
            c_doc = db.collection(CLASSES_COL).document(cid).get()
            if c_doc.exists:
                class_names.append(c_doc.to_dict().get('name', cid))
        s_data['class_names'] = ', '.join(class_names) if class_names else 'No class'
        students_list.append(s_data)
    # Sort by name
    students_list.sort(key=lambda x: x.get('name', ''))
    context = {
        'profile': profile,
        'students': students_list,
        'total_students': len(students_list),
    }
    return render_template('all_students.html', **context)

@app.route('/institution/teacher/settings')
@require_institution_role(['teacher'])
def institution_teacher_settings():
    uid = session['uid']
    profile = _get_teacher_profile(uid)
    inst_id = profile.get('institution_id')

    # Get institution data
    institution = {}
    if inst_id:
        inst_doc = db.collection('institutions').document(inst_id).get()
        if inst_doc.exists:
            institution = inst_doc.to_dict()

    # Get teacher's classes
    classes_docs = db.collection('classes').where('teacher_id', '==', uid).stream()
    classes = [{'id': c.id, **c.to_dict()} for c in classes_docs]

    # Get all students in institution
    students_docs = db.collection('users').where('institution_id', '==', inst_id).stream()
    students = [{'id': s.id, **s.to_dict()} for s in students_docs]

    logger.info("fetched_students", count=len(students), institution_id=inst_id)

    # Populate students for each class
    for cls in classes:
        cls['students'] = [s['id'] for s in students if cls['id'] in s.get('class_ids', [])]
        logger.info("class_student_count", class_name=cls.get('name', cls['id']), class_id=cls['id'], student_count=len(cls['students']))

    context = {
        'profile': profile,
        'institution': institution,
        'institution_id': inst_id,
        'classes': classes,
        'settings': profile.get('settings', {})
    }
    return render_template('institution_teacher_settings.html', **context)


@app.route('/institution/admin/settings')
@require_institution_role(['admin'])
def institution_admin_settings():
    uid = session['uid']
    profile = _get_admin_profile(uid)
    inst_id = profile.get('institution_id')

    # Get institution data
    institution = {}
    if inst_id:
        inst_doc = db.collection('institutions').document(inst_id).get()
        if inst_doc.exists:
            institution = inst_doc.to_dict()

    # Get all classes in institution
    classes_docs = db.collection('classes').where('institution_id', '==', inst_id).stream()
    classes = [{'id': c.id, **c.to_dict()} for c in classes_docs]

    # Get all students in institution
    students_docs = db.collection('users').where('institution_id', '==', inst_id).stream()
    students = [{'id': s.id, **s.to_dict()} for s in students_docs]

    logger.info("fetched_students", count=len(students), institution_id=inst_id)

    # Populate students for each class
    for cls in classes:
        cls['students'] = [s['id'] for s in students if cls['id'] in s.get('class_ids', [])]
        logger.info("class_student_count", class_name=cls.get('name', cls['id']), class_id=cls['id'], student_count=len(cls['students']))

    context = {
        'profile': profile,
        'institution': institution,
        'institution_id': inst_id,
        'classes': classes,
        'settings': profile.get('settings', {})
    }
    return render_template('institution_admin_settings.html', **context)

# ============================================================================
# SCLERA AI INSTITUTIONAL ANALYTICS API ROUTES
# ============================================================================

@app.route('/api/user/profile')
@require_login
def get_user_profile():
    """Get current user profile for SCLERA AI"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    # Get user role from institution system
    profile = _get_any_profile(uid)
    account_type = profile.get('account_type', 'student') if profile else 'student'

    return jsonify({
        'name': user_data.get('name', 'User'),
        'email': user_data.get('email'),
        'role': account_type,
        'initials': ''.join([word[0] for word in user_data.get('name', 'User').split()[:2]]).upper()
    })

@app.route('/api/sclera/threads/<mode>/create', methods=['POST'])
@require_login
def create_sclera_thread(mode):
    """Create a new SCLERA AI thread"""
    uid = session['uid']
    if mode not in ['academic', 'institutional', 'research']:
        return jsonify({'error': 'Invalid mode'}), 400

    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403

    data = request.json or {}
    title = data.get('title', f'New {mode.title()} Analysis')

    try:
        thread_data = {
            'title': title,
            'mode': mode,
            'created_at': datetime.utcnow().isoformat(),
            'last_message_at': datetime.utcnow().isoformat(),
            'message_count': 0
        }

        # Create thread document
        thread_ref = db.collection('users').document(uid).collection('sclera_threads').document()
        thread_ref.set(thread_data)

        return jsonify({
            'success': True,
            'thread_id': thread_ref.id,
            'thread': {**thread_data, 'thread_id': thread_ref.id}
        })
    except Exception as e:
        logger.error(f"SCLERA create thread error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sclera/threads/<mode>/<thread_id>/delete', methods=['DELETE'])
@require_login
def delete_sclera_thread(mode, thread_id):
    """Delete a SCLERA AI thread"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400

    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403

    try:
        # Delete thread document (messages will be deleted by Firestore rules)
        thread_ref = db.collection('users').document(uid).collection('sclera_threads').document(thread_id)
        thread_doc = thread_ref.get()

        if not thread_doc.exists:
            return jsonify({'success': False, 'error': 'Thread not found'}), 404

        thread_ref.delete()

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"SCLERA delete thread error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sclera/threads/<mode>/<thread_id>/export')
@require_login
def export_sclera_thread(mode, thread_id):
    """Export a SCLERA AI thread conversation"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400

    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403

    format_type = request.args.get('format', 'text')
    if format_type not in ['text', 'markdown', 'json']:
        return jsonify({'error': 'Invalid format. Use text, markdown, or json'}), 400

    try:
        # Get AI assistant for export functionality
        ai_assistant = get_ai_assistant()

        # Export the thread
        exported_data = ai_assistant.export_thread(uid, mode, format_type, thread_id)

        if exported_data is None:
            return jsonify({'error': 'Failed to export thread'}), 500

        # Return the exported data as plain text (works for all formats)
        return exported_data, 200, {'Content-Type': 'text/plain'}

    except Exception as e:
        logger.error(f"SCLERA export thread error: {str(e)}")
        return jsonify({'error': 'Failed to export thread', 'details': str(e)}), 500

@app.route('/api/sclera/threads/<mode>/<thread_id>/history')
@require_login
def get_sclera_thread_history(mode, thread_id):
    """Get conversation history for a SCLERA AI thread"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400

    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403

    try:
        # Get thread messages (simplified - no ordering to avoid issues)
        messages_ref = db.collection('users').document(uid).collection('sclera_threads').document(thread_id).collection('messages')
        messages_docs = messages_ref.stream()

        history = []
        for msg_doc in messages_docs:
            msg_data = msg_doc.to_dict()
            history.append({
                'role': msg_data.get('role'),
                'content': msg_data.get('content'),
                'timestamp': msg_data.get('timestamp')
            })

        # Sort in memory instead of Firestore
        history.sort(key=lambda x: x.get('timestamp', ''))

        return jsonify({'history': history})

    except Exception as e:
        logger.error(f"SCLERA thread history error: {str(e)}")
        return jsonify({'history': [], 'error': str(e)}), 500

@app.route('/api/sclera/threads/<mode>')
@require_login
def get_sclera_threads(mode):
    """Get all threads for a SCLERA AI mode"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400

    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403

    try:
        # Get all threads for this mode
        threads_ref = db.collection('users').document(uid).collection('sclera_threads')
        thread_docs = list(threads_ref.where('mode', '==', mode).stream())

        threads = []
        for doc in thread_docs:
            thread_data = doc.to_dict()
            threads.append({
                'thread_id': doc.id,
                'title': thread_data.get('title', 'Untitled'),
                'mode': thread_data.get('mode'),
                'created_at': thread_data.get('created_at'),
                'last_message_at': thread_data.get('last_message_at'),
                'message_count': thread_data.get('message_count', 0)
            })

        # Sort by last message (most recent first)
        threads.sort(key=lambda x: x.get('last_message_at', ''), reverse=True)

        # Find active thread (most recent one)
        active_thread_id = threads[0]['thread_id'] if threads else None

        return jsonify({
            'threads': threads,
            'active_thread_id': active_thread_id
        })

    except Exception as e:
        logger.error(f"SCLERA get threads error: {str(e)}")
        return jsonify({'threads': [], 'active_thread_id': None, 'error': str(e)}), 500

@app.route('/api/sclera/chat/<mode>', methods=['POST'])
@require_login
def sclera_chat(mode):
    """Send a message to SCLERA AI and get response"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400

    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403

    data = request.json or {}
    message = data.get('message', '').strip()
    force_new_thread = data.get('force_new_thread', False)  # New parameter
    if not message:
        return jsonify({'error': 'Message is required'}), 400

    try:
        # Get threads for this mode
        threads_ref = db.collection('users').document(uid).collection('sclera_threads')
        thread_docs = list(threads_ref.where('mode', '==', mode).stream())

        # Determine which thread to use
        if force_new_thread or not thread_docs:
            # Create new thread
            thread_data = {
                'title': f'New {mode.replace("_", " ").title()} Conversation',
                'mode': mode,
                'created_at': get_current_time_for_user({'uid': uid}),  # Use user's timezone
                'last_message_at': get_current_time_for_user({'uid': uid}),  # Use user's timezone
                'message_count': 0
            }
            thread_ref = threads_ref.document()
            thread_ref.set(thread_data)
            logger.info(f"Created new thread {thread_ref.id} for {mode}")
        else:
            # Use most recent thread (sort by last_message_at descending)
            thread_docs.sort(key=lambda doc: doc.to_dict().get('last_message_at', ''), reverse=True)
            thread_ref = thread_docs[0].reference

        # Save user message
        message_data = {
            'role': 'user',
            'content': message,
            'timestamp': get_current_time_for_user({'uid': uid})  # Use user's timezone
        }
        thread_ref.collection('messages').add(message_data)

        # Update thread metadata
        thread_ref.update({
            'last_message_at': get_current_time_for_user({'uid': uid}),  # Use user's timezone
            'message_count': firestore.Increment(1)
        })

        # Generate AI response using the correct AI assistant
        ai_response = generate_sclera_response(message, mode, uid)

        # Save AI response
        ai_message_data = {
            'role': 'assistant',
            'content': ai_response,
            'timestamp': get_current_time_for_user({'uid': uid})  # Use user's timezone
        }
        thread_ref.collection('messages').add(ai_message_data)

        # Update thread metadata again
        thread_ref.update({
            'last_message_at': get_current_time_for_user({'uid': uid})  # Use user's timezone
        })

        return jsonify({
            'response': ai_response,
            'thread_id': thread_ref.id  # Return thread ID so frontend knows which thread was used
        })

    except Exception as e:
        logger.error(f"SCLERA chat error: {str(e)}")
        return jsonify({'error': 'Failed to process message', 'details': str(e)}), 500

def generate_sclera_response(message, mode, uid):
    """Generate AI response based on mode and context"""
    try:
        # Get AI assistant - now handles missing API gracefully
        ai_assistant = get_ai_assistant()

        # Get user context
        user_data = get_user_data(uid)
        profile = _get_any_profile(uid)

        # Create context based on mode
        context = {
            'user_name': user_data.get('name', 'Student') if user_data else 'Student',
            'purpose': profile.get('account_type', 'student') if profile else 'student'
        }

        # Add academic context
        academic_context = ai_assistant.get_academic_context(user_data or {})
        context.update(academic_context)

        # Generate response based on mode
        if mode == 'academic_planner':
            # Use planning response for academic planner (combines academic + planning)
            response = ai_assistant.generate_planning_response(message, context)
        elif mode == 'doubt_solver':
            response = ai_assistant.generate_doubt_response(message, context)
        elif mode == 'institutional':
            # For institutional mode, use planning response with institutional context
            context['purpose'] = 'institutional'
            response = ai_assistant.generate_planning_response(message, context)
        else:
            # Default to planning response
            response = ai_assistant.generate_planning_response(message, context)

        # Format response based on mode
        if mode == 'institutional':
            # Ensure institutional responses are well-structured
            if not any(keyword in response.lower() for keyword in ['analysis', 'assessment', 'recommendations', 'findings']):
                response = f"Analysis Results:\n\n{response}\n\nStrategic Insights:\n\nBased on your query, the institutional data suggests focused interventions in this area."

        return response

    except Exception as e:
        logger.error(f"SCLERA response generation error: {str(e)}")

        # Fallback responses based on mode
        if mode == 'institutional':
            return f"""Analysis Results:

Based on your query: "{message}"

**Key Findings:**
- Institutional data indicates trends requiring attention
- Comparative analysis shows opportunities for improvement
- Strategic interventions recommended for optimal outcomes

**Recommended Actions:**
- Implement targeted support programs
- Monitor key performance indicators
- Develop comprehensive improvement strategies

**Next Steps:**
Would you like me to generate a detailed report or analyze specific metrics further?"""
        elif mode == 'academic_planner':
            return f"""Academic Planning Response:

For your question about: "{message}"

**Study Recommendations:**
- Focus on core concepts and foundational principles
- Practice regularly with diverse problem sets
- Utilize active recall and spaced repetition techniques

**Resource Suggestions:**
- Review course materials and supplementary texts
- Join study groups for collaborative learning
- Seek clarification on challenging topics promptly

**Goal Setting:**
- Break down large objectives into manageable tasks
- Track progress and adjust strategies as needed
- Celebrate achievements and maintain motivation

How else can I assist with your academic planning?"""
        else:  # doubt_solver
            return f"""Doubt Resolution Response:

I understand you're asking about: "{message[:50]}..."

**Step-by-step explanation:**
1. Let's break down your question
2. Here's the key concept you need to understand
3. Related examples and applications
4. Practice problems to help you master this

**Additional Resources:**
- Textbook references for this topic
- Online tutorials and video explanations
- Practice exercises at your level

Would you like me to explain any specific part in more detail?"""


@app.route('/api/sclera/threads/<mode>/<thread_id>/rename', methods=['POST'])
@require_login
def rename_sclera_thread(mode, thread_id):
    """Rename a SCLERA AI conversation thread"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400

    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403

    data = request.json or {}
    new_title = data.get('title', '').strip()
    if not new_title:
        return jsonify({'error': 'Title is required'}), 400

    # Map mode to chatbot_type for AIAssistant
    mode_mapping = {
        'academic_planner': 'planning',
        'doubt_solver': 'doubt',
        'institutional': 'planning'  # institutional uses planning responses
    }
    chatbot_type = mode_mapping.get(mode)
    if not chatbot_type:
        return jsonify({'error': 'Invalid mode'}), 400

    try:
        # Rename SCLERA thread directly in Firestore
        thread_ref = db.collection('users').document(uid).collection('sclera_threads').document(thread_id)
        thread_doc = thread_ref.get()

        if not thread_doc.exists:
            return jsonify({'error': 'Thread not found'}), 404

        # Update the thread title
        thread_ref.update({'title': new_title.strip()})

        return jsonify({'success': True, 'message': 'Thread renamed successfully'})

    except Exception as e:
        logger.error(f"SCLERA rename thread error: {str(e)}")
        return jsonify({'error': 'Failed to rename thread', 'details': str(e)}), 500

@app.route('/api/notifications', methods=['GET'])
@require_login
def get_notifications():
    """API endpoint for students to fetch their notifications"""
    uid = session['uid']
    profile = _get_any_profile(uid)
    if not profile:
        return jsonify({'notifications': []})
    inst_id = profile.get('institution_id')
    if not inst_id:
        return jsonify({'notifications': []})
    # Get all unread notifications for this user in their institution
    # We remove order_by to avoid the need for a composite index
    try:
        notifs_ref = db.collection('institutions').document(inst_id).collection('notifications').where('recipient_uid', '==', uid).where('read', '==', False)
        notifications = []
        # Calling stream() with a simple query (single field filter or multiple equality filters)
        # usually doesn't require a composite index unless combined with order_by or inequalities.
        for n in notifs_ref.stream():
            n_data = n.to_dict()
            n_data['id'] = n.id
            notifications.append(n_data)
        # Sort in memory by created_at descending
        notifications.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        # Limit to 10 for the response
        return jsonify({'notifications': notifications[:10]})
    except Exception as e:
        print(f"Notification error: {e}")
        return jsonify({'notifications': [], 'error': str(e)})

@app.route('/api/notifications/<notif_id>/mark_read', methods=['POST'])
@require_login
def mark_notification_read(notif_id):
    """Mark a notification as read"""
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    if not inst_id:
        return jsonify({'error': 'No institution'}), 400
    notif_ref = db.collection('institutions').document(inst_id).collection('notifications').document(notif_id)
    notif_doc = notif_ref.get()
    if notif_doc.exists:
        notif_data = notif_doc.to_dict()
        # Verify this notification belongs to the user
        if notif_data.get('recipient_uid') == uid:
            notif_ref.update({'read': True})
            return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404

# ============================================================================
# ERROR HANDLERS

# ============================================================================
@app.errorhandler(400)
def bad_request(error):
    """Handle bad request errors"""
    logger.warning("bad_request", error=str(error), path=request.path)
    if request.is_json:
        return jsonify({'error': 'Bad request', 'message': str(error)}), 400
    return render_template('error.html', error_code=400, error_message="Bad request"), 400
@app.errorhandler(403)
def forbidden(error):
    """Handle forbidden errors"""
    logger.security_event("forbidden_access", user_id=session.get('uid'), ip_address=request.remote_addr)
    if request.is_json:
        return jsonify({'error': 'Forbidden', 'message': 'Access denied'}), 403
    return render_template('error.html', error_code=403, error_message="Access denied"), 403
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    logger.warning("page_not_found", path=request.path, ip=request.remote_addr)
    if request.is_json:
        return jsonify({'error': 'Not found', 'message': 'Resource not found'}), 404
    return render_template('error.html', error_code=404, error_message="Page not found"), 404
@app.errorhandler(429)
def rate_limit_handler(error):
    """Handle rate limit exceeded"""
    logger.security_event("rate_limit_exceeded", user_id=session.get('uid'), ip_address=request.remote_addr)
    if request.is_json:
        return jsonify({'error': 'Too many requests', 'message': 'Rate limit exceeded. Please try again later.'}), 429
    return render_template('error.html', error_code=429, error_message="Too many requests. Please try again later."), 429
@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.error("internal_server_error", error=str(error), path=request.path, traceback=traceback.format_exc())
    if request.is_json:
        return jsonify({'error': 'Internal server error', 'message': 'Something went wrong'}), 500
    return render_template('error.html', error_code=500, error_message="Internal server error"), 500

# ============================================================================
# REQUEST LOGGING

# ============================================================================
@app.before_request
def log_request():
    """Log all incoming requests"""
    guard_resp = _institution_login_guard()
    if guard_resp is not None:
        return guard_resp
    logger.debug("request_started",
                 method=request.method,
                 path=request.path,
                 ip=request.remote_addr,
                 user_agent=str(request.user_agent))
@app.after_request
def log_response(response):
    """Log all responses"""
    logger.info("request_completed",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                ip=request.remote_addr)
    return response
if __name__ == '__main__':
    env = os.environ.get('FLASK_ENV', 'production')
    debug = env == 'development'
    port = int(os.environ.get('PORT', 5000))  # Use PORT env var for deployment, default to 5000 for local dev
    logger.info("application_startup", environment=env, debug=debug, port=port)
    app.run(debug=debug, host='0.0.0.0', port=port)
