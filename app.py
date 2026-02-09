from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from firebase_config import auth, db
from firebase_admin import auth as admin_auth
from datetime import datetime, date, timedelta
from templates.academic_data import get_syllabus, get_available_subjects, ACADEMIC_SYLLABI
from utils import (
    PasswordManager, login_rate_limiter, logger, validate_schema,
    user_registration_schema, user_login_schema, CacheManager
)
from config import config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_mail import Mail, Message
import os
from google.cloud.firestore import Increment
import uuid
from functools import wraps
from firebase_admin import firestore
from collections import defaultdict
import random
import string
from marshmallow import ValidationError
import traceback
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
    content_security_policy={
        'default-src': "'self'",
        'script-src': ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://cdnjs.cloudflare.com", "https://cdn.jsdelivr.net"],
        'style-src': ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com"],
        'img-src': ["'self'", "data:", "https:"],
        'font-src': ["'self'", "https://cdnjs.cloudflare.com"],
        'connect-src': "'self'",
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
                series = [float(r.get('percentage', r.get('score', 0))) for r in sorted_res[:4]][::-1]
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
# UTILITY FUNCTIONS

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

def hash_password(password):
    """DEPRECATED: Use PasswordManager.hash_password() instead"""
    return PasswordManager.hash_password(password)

def verify_password(stored_hash, provided_password):
    """DEPRECATED: Use PasswordManager.verify_password() instead"""
    return PasswordManager.verify_password(provided_password, stored_hash)

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
    if purpose == 'highschool' and user_data.get('highschool'):
        hs = user_data['highschool']
        syllabus = get_syllabus('highschool', hs.get('board'), hs.get('grade'))
    elif purpose == 'exam' and user_data.get('exam'):
        syllabus = get_syllabus('exam', user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        syllabus = get_syllabus('after_tenth', 'CBSE', at.get('grade'), at.get('subjects', []))
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
        'goals': [], 'tasks': [], 'milestones': [], 'exam_results': []
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
# STATIC DATA: CAREERS, COURSES, INTERNSHIPS

# ============================================================================
CAREERS_DATA = {
    'Technology': [
        {'id': 'software_engineer', 'name': 'Software Engineer', 'description': 'Design and build software systems that power modern applications, from mobile apps to enterprise platforms.', 'subjects': ['Mathematics', 'Computer Science', 'Physics'], 'skills': ['Programming', 'Problem Solving', 'System Design', 'Algorithms'], 'courses': ['python_beginners', 'web_development'], 'internships': ['software_dev_intern', 'data_analytics_intern']},
        {'id': 'data_scientist', 'name': 'Data Scientist', 'description': 'Analyse massive datasets to extract insights, build predictive models, and drive business decisions through data.', 'subjects': ['Mathematics', 'Statistics', 'Computer Science'], 'skills': ['Python', 'Machine Learning', 'Statistics', 'Data Visualisation'], 'courses': ['intro_ai', 'data_science_spec'], 'internships': ['data_analytics_intern']},
        {'id': 'cyber_security', 'name': 'Cyber Security Analyst', 'description': 'Protect organisations from digital threats by identifying vulnerabilities and implementing security protocols.', 'subjects': ['Computer Science', 'Mathematics'], 'skills': ['Networking', 'Security Protocols', 'Penetration Testing', 'Risk Assessment'], 'courses': [], 'internships': []},
    ],
    'Medicine': [
        {'id': 'doctor', 'name': 'Doctor', 'description': 'Diagnose and treat patients across specialisations — from surgery to internal medicine and beyond.', 'subjects': ['Biology', 'Chemistry', 'Physics'], 'skills': ['Anatomy', 'Patient Care', 'Clinical Reasoning', 'Surgery'], 'courses': [], 'internships': []},
        {'id': 'pharmacist', 'name': 'Pharmacist', 'description': 'Manage pharmaceutical supplies, advise patients on medication, and ensure safe drug dispensing.', 'subjects': ['Biology', 'Chemistry'], 'skills': ['Drug Knowledge', 'Patient Interaction', 'Inventory Management'], 'courses': [], 'internships': []},
    ],
    'Engineering': [
        {'id': 'mechanical_engineer', 'name': 'Mechanical Engineer', 'description': 'Design machines, engines, and mechanical systems for manufacturing, aerospace, and energy sectors.', 'subjects': ['Physics', 'Mathematics', 'Chemistry'], 'skills': ['CAD', 'Mechanics', 'Thermodynamics', 'Prototyping'], 'courses': [], 'internships': []},
        {'id': 'civil_engineer', 'name': 'Civil Engineer', 'description': 'Plan and build infrastructure — bridges, buildings, roads, and water systems that shape cities.', 'subjects': ['Physics', 'Mathematics'], 'skills': ['Structural Design', 'Planning', 'AutoCAD', 'Project Management'], 'courses': [], 'internships': []},
    ],
    'Business': [
        {'id': 'chartered_accountant', 'name': 'Chartered Accountant', 'description': 'Manage finances, audit accounts, and advise businesses on tax strategy and compliance.', 'subjects': ['Accountancy', 'Economics', 'Mathematics'], 'skills': ['Accounting', 'Taxation', 'Financial Analysis', 'Auditing'], 'courses': [], 'internships': ['finance_intern']},
        {'id': 'management_consultant', 'name': 'Management Consultant', 'description': 'Help organisations solve complex problems, improve efficiency, and execute strategy.', 'subjects': ['Economics', 'Business Studies', 'Mathematics'], 'skills': ['Analysis', 'Strategy', 'Communication', 'Leadership'], 'courses': [], 'internships': ['marketing_intern']},
    ],
    'Creative': [
        {'id': 'graphic_designer', 'name': 'Graphic Designer', 'description': 'Create visual identities, marketing materials, and digital content that communicate ideas powerfully.', 'subjects': ['Art', 'Computer Science'], 'skills': ['Adobe Suite', 'Typography', 'Branding', 'UX Design'], 'courses': [], 'internships': ['graphic_design_intern']},
        {'id': 'content_writer', 'name': 'Content Writer', 'description': 'Craft compelling written content for blogs, marketing, journalism, and digital platforms.', 'subjects': ['English', 'History'], 'skills': ['Writing', 'Research', 'SEO', 'Editing'], 'courses': [], 'internships': ['content_writing_intern']},
    ]
}
COURSES_DATA = [
    {'id': 'python_beginners', 'name': 'Python for Beginners', 'provider': 'Coursera', 'level': 'Beginner', 'duration': '4 weeks', 'price': 'Free', 'description': 'A foundational course covering Python syntax, data structures, control flow, and basic scripting. Ideal for absolute beginners.', 'skills_gained': ['Python Basics', 'Problem Solving', 'Scripting'], 'related_careers': ['software_engineer', 'data_scientist'], 'link': 'https://www.coursera.org'},
    {'id': 'intro_ai', 'name': 'Introduction to AI', 'provider': 'edX', 'level': 'Beginner', 'duration': '6 weeks', 'price': 'Free', 'description': 'Understand the fundamentals of artificial intelligence — from machine learning basics to neural networks and ethics in AI.', 'skills_gained': ['AI Concepts', 'Machine Learning Basics', 'Critical Thinking'], 'related_careers': ['data_scientist', 'software_engineer'], 'link': 'https://www.edx.org'},
    {'id': 'web_development', 'name': 'Web Development', 'provider': 'freeCodeCamp', 'level': 'Intermediate', 'duration': '8 weeks', 'price': 'Free', 'description': 'Build real-world web applications using HTML, CSS, JavaScript, and React. Project-based learning throughout.', 'skills_gained': ['HTML/CSS', 'JavaScript', 'React', 'Responsive Design'], 'related_careers': ['software_engineer'], 'link': 'https://www.freecodecamp.org'},
    {'id': 'web_bootcamp', 'name': 'Complete Web Development Bootcamp', 'provider': 'Udemy', 'level': 'All Levels', 'duration': '12 weeks', 'price': '₹499', 'description': 'An all-in-one bootcamp covering front-end, back-end, databases, and deployment. Takes you from zero to full-stack.', 'skills_gained': ['Full Stack', 'Node.js', 'MongoDB', 'Deployment'], 'related_careers': ['software_engineer'], 'link': 'https://www.udemy.com'},
    {'id': 'data_science_spec', 'name': 'Data Science Specialization', 'provider': 'Coursera', 'level': 'Intermediate', 'duration': '6 months', 'price': '₹3,999/mo', 'description': 'A comprehensive specialisation covering statistics, Python, machine learning, and data storytelling for professionals.', 'skills_gained': ['Statistics', 'Python', 'Machine Learning', 'Data Visualisation'], 'related_careers': ['data_scientist'], 'link': 'https://www.coursera.org'},
]
INTERNSHIPS_DATA = [
    {'id': 'software_dev_intern', 'name': 'Software Development Intern', 'domain': 'Technology', 'company': 'Tech Corp', 'duration': '3 months', 'location': 'Remote', 'skills_required': ['Python', 'JavaScript', 'Git'], 'eligibility': 'Class 11/12 or undergraduate students with basic programming knowledge.', 'description': 'Work alongside senior developers building features for a SaaS product. Involves code reviews, sprint planning, and real deployments.', 'how_to_apply': 'Visit the company careers page and submit your resume with a link to a GitHub portfolio.'},
    {'id': 'data_analytics_intern', 'name': 'Data Analytics Intern', 'domain': 'Technology', 'company': 'Analytics Inc', 'duration': '6 months', 'location': 'Bangalore', 'skills_required': ['Python', 'SQL', 'Excel'], 'eligibility': 'Students pursuing Science or Commerce streams with an interest in data.', 'description': 'Analyse business data, create dashboards, and present findings to stakeholders. Hands-on with real datasets from day one.', 'how_to_apply': 'Apply via LinkedIn or the company website. Include a brief statement on why you are interested in data.'},
    {'id': 'marketing_intern', 'name': 'Marketing Intern', 'domain': 'Business', 'company': 'Brand Agency', 'duration': '2 months', 'location': 'Mumbai', 'skills_required': ['Communication', 'Social Media', 'Writing'], 'eligibility': 'Commerce or Arts stream students with strong communication skills.', 'description': 'Plan and execute social media campaigns, write content briefs, and assist in brand strategy for real clients.', 'how_to_apply': 'Send your resume and a short creative portfolio to the agency\'s internship email.'},
    {'id': 'finance_intern', 'name': 'Finance Intern', 'domain': 'Business', 'company': 'Investment Firm', 'duration': '4 months', 'location': 'Delhi', 'skills_required': ['Excel', 'Accounting', 'Attention to Detail'], 'eligibility': 'Commerce stream students in Class 11/12 or pursuing CA/CMA.', 'description': 'Support the finance team in budgeting, forecasting, and client portfolio management. Learn industry-standard tools.', 'how_to_apply': 'Apply through the firm\'s internship portal. A basic Excel proficiency test will be conducted.'},
    {'id': 'graphic_design_intern', 'name': 'Graphic Design Intern', 'domain': 'Creative', 'company': 'Design Studio', 'duration': '3 months', 'location': 'Pune', 'skills_required': ['Adobe Illustrator', 'Photoshop', 'Creative Thinking'], 'eligibility': 'Students with a portfolio demonstrating visual design work.', 'description': 'Design branding, marketing collaterals, and social media assets for live client projects under senior designer mentorship.', 'how_to_apply': 'Submit your portfolio (Behance or Dribbble link) along with your resume.'},
    {'id': 'content_writing_intern', 'name': 'Content Writing Intern', 'domain': 'Creative', 'company': 'Media House', 'duration': '2 months', 'location': 'Remote', 'skills_required': ['English Writing', 'Research', 'SEO Basics'], 'eligibility': 'Any stream. Strong English writing and research skills required.', 'description': 'Write blog posts, articles, and web content on assigned topics. Learn SEO best practices and content strategy.', 'how_to_apply': 'Send two sample articles you have written (personal or published) along with your resume.'},
]
# Helper lookups

def get_career_by_id(career_id):
    for domain, careers in CAREERS_DATA.items():
        for career in careers:
            if career['id'] == career_id:
                career['domain'] = domain
                return career
    return None

def get_course_by_id(course_id):
    for course in COURSES_DATA:
        if course['id'] == course_id:
            return course
    return None

def get_internship_by_id(internship_id):
    for internship in INTERNSHIPS_DATA:
        if internship['id'] == internship_id:
            return internship
    return None

# ============================================================================
# AUTH ROUTES

# ============================================================================

@app.route('/')
def index():
    if 'uid' in session:
        return redirect(url_for('profile_dashboard'))
    return render_template('landing.html')

@app.route('/auth-choice')
def auth_choice():
    return render_template('auth_choice.html')

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
                'created_at': datetime.utcnow().isoformat()
            }
            db.collection('users').document(uid).set(user_data)
            session['uid'] = uid
            logger.security_event("user_registered", user_id=uid, ip_address=request.remote_addr)
            if purpose == 'highschool':
                return redirect(url_for('setup_highschool'))
            elif purpose == 'exam':
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
    return redirect('/login')

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
        'saved_careers': saved_careers,
        'streak': user_data.get('login_streak', 0),
    }
    return render_template('main_dashboard.html', **context)

# ============================================================================
# PROFILE / RESUME

# ============================================================================

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
        'goals': [g for g in user_data.get('goals', []) if not g.get('completed', False)][:5]
    }
    return render_template('profile_resume.html', **context)

@app.route('/profile/edit', methods=['GET', 'POST'])
@require_login
def profile_edit():
    uid = session['uid']
    if request.method == 'POST':
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
        'achievements': ', '.join(user_data.get('achievements', []))
    }
    return render_template('profile_edit.html', **context)

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
    syllabus = {}
    if purpose == 'highschool' and user_data.get('highschool'):
        hs = user_data['highschool']
        syllabus = get_syllabus('highschool', hs.get('board'), hs.get('grade'))
    elif purpose == 'exam' and user_data.get('exam'):
        syllabus = get_syllabus('exam', user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        syllabus = get_syllabus('after_tenth', 'CBSE', at.get('grade'), at.get('subjects', []))
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
    syllabus = {}
    if purpose == 'highschool' and user_data.get('highschool'):
        hs = user_data['highschool']
        syllabus = get_syllabus('highschool', hs.get('board'), hs.get('grade'))
    elif purpose == 'exam' and user_data.get('exam'):
        syllabus = get_syllabus('exam', user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        syllabus = get_syllabus('after_tenth', 'CBSE', at.get('grade'), at.get('subjects', []))
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
            if new_purpose == 'highschool':
                updates['highschool'] = {'board': new_board, 'grade': new_grade}
            elif new_purpose == 'exam':
                exam_type = request.form.get('exam_type', 'JEE')
                updates['exam'] = {'type': exam_type}
            elif new_purpose == 'after_tenth':
                stream = request.form.get('stream', 'Science')
                updates['after_tenth'] = {
                    'grade': new_grade,
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
# ADMIN DASHBOARD ROUTES (TENANT APP)

# ============================================================================
#from admin_routes import (
    #admin_login, admin_logout, admin_dashboard,
    #admin_students, admin_student_add, admin_student_toggle,
    #admin_syllabus, admin_syllabus_update,
    #admin_goals, admin_goal_create, admin_goal_delete,
    #admin_progress, admin_resources, admin_resource_add,
    #admin_statistics, require_admin
#)
# Admin authentication
# app.route('/admin/login', methods=['GET', 'POST'])(admin_login)
# app.route('/admin/logout')(admin_logout)
# Admin dashboard
# app.route('/admin/dashboard')(require_admin(admin_dashboard))
#app.route('/admin/students')(require_admin(admin_students))
#app.route('/admin/students/add', methods=['GET', 'POST'])(require_admin(admin_student_add))
#app.route('/admin/students/<student_uid>/toggle', methods=['POST'])(require_admin(admin_student_toggle))
# Syllabus management
#app.route('/admin/syllabus')(require_admin(admin_syllabus))
#app.route('/admin/syllabus/update', methods=['POST'])(require_admin(admin_syllabus_update))
# Goals management
#app.route('/admin/goals')(require_admin(admin_goals))
#app.route('/admin/goals/create', methods=['GET', 'POST'])(require_admin(admin_goal_create))
#app.route('/admin/goals/<goal_id>/delete', methods=['POST'])(require_admin(admin_goal_delete))
# Progress and resources

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
    board = class_data.get('board', 'CBSE')
    grade = class_data.get('grade', '10')
    syllabus = get_syllabus(purpose, board, grade)
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

    context = {
        'profile': profile,
        'institution': institution,
        'institution_id': inst_id,
        'classes': classes,
        'settings': profile.get('settings', {})
    }
    return render_template('institution_admin_settings.html', **context)

# ============================================================================
# STUDENT-SIDE NOTIFICATIONS

# ============================================================================

@app.route('/api/notifications')
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
    logger.info("application_startup", environment=env, debug=debug)
    app.run(debug=debug, host='0.0.0.0', port=5000)
