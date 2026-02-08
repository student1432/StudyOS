from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from firebase_config import auth, db
from firebase_admin import auth as admin_auth
from datetime import datetime
from templates.academic_data import get_syllabus, get_available_subjects, ACADEMIC_SYLLABI
import os
import hashlib
from google.cloud.firestore import Increment
import uuid
from functools import wraps
from flask import render_template, request, redirect, url_for, abort, jsonify
from firebase_admin import firestore
from datetime import datetime
from datetime import date, datetime, timedelta
from collections import defaultdict
import random
import string



app = Flask(__name__)
app.secret_key = os.urandom(24)
user_ref = None

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
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, provided_password):
    return stored_hash == hash_password(provided_password)

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
    return redirect(url_for('signup'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        age = request.form.get('age')
        email = request.form.get('email')
        password = request.form.get('password')
        purpose = request.form.get('purpose')
        try:
            try:
                admin_auth.get_user_by_email(email)
                flash('Email already exists. Please login.', 'error')
                return redirect(url_for('login'))
            except admin_auth.UserNotFoundError:
                pass
            user = admin_auth.create_user(email=email, password=password)
            uid = user.uid
            password_hash = hash_password(password)
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
            flash(f'Error creating account: {str(e)}', 'error')
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
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            user = admin_auth.get_user_by_email(email)
            uid = user.uid
            user_doc = db.collection('users').document(uid).get()
            if not user_doc.exists:
                flash('Invalid email or password', 'error')
                return redirect(url_for('login'))
            user_data = user_doc.to_dict()
            stored_hash = user_data.get('password_hash')
            if not stored_hash:
                flash('Please contact support to reset your password', 'error')
                return redirect(url_for('login'))
            if not verify_password(stored_hash, password):
                flash('Invalid email or password', 'error')
                return redirect(url_for('login'))
            session['uid'] = uid
            
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
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

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
    
    todos = db.collection('users').document(uid)\
        .collection('study_todos').stream()
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
    seconds = int(request.json['seconds'])
    db.collection('users').document(uid).set({
        'study_mode': {'total_seconds': Increment(seconds)}
    }, merge=True)
    
    # Record/Update session for heatmap
    # Using YYYY-MM-DD-HH as a unique key for the hour to avoid document spam
    now = datetime.utcnow()
    hour_id = now.strftime("%Y-%m-%d-%H")
    session_ref = db.collection('users').document(uid).collection('study_sessions').document(hour_id)
    
    session_ref.set({
        'start_time': now.isoformat(),
        'duration_seconds': Increment(seconds),
        'last_updated': now.isoformat()
    }, merge=True)
    
    return jsonify(ok=True)

@app.route('/study-mode/todo/add', methods=['POST'])
@require_login
def add_study_todo():
    uid = session['uid']
    text = request.json['text']
    db.collection('users').document(uid)\
        .collection('study_todos').add({
            'text': text,
            'done': False
        })
    return jsonify(ok=True)

@app.route('/study-mode/todo/<tid>/toggle', methods=['POST'])
@require_login
def toggle_study_todo(tid):
    uid = session['uid']
    ref = db.collection('users').document(uid)\
        .collection('study_todos').document(tid)
    doc = ref.get()
    ref.update({'done': not doc.to_dict().get('done', False)})
    return jsonify(ok=True)

@app.route('/study-mode/todo/<tid>/delete', methods=['POST'])
@require_login
def delete_study_todo(tid):
    uid = session['uid']
    db.collection('users').document(uid)\
        .collection('study_todos').document(tid).delete()
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

def require_role(allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'uid' not in session:
                return redirect(url_for('login'))
            
            # Verify claim via admin SDK (production) or session cache (dev)
            # In production, we'd verify session cookie claims.
            # Here we check the user doc for 'role' field as the source of truth for simplicity in this setup,
            # but ideally this should be a Custom Claim on the ID token.
            uid = session['uid']
            user_doc = db.collection('users').document(uid).get()
            if not user_doc.exists:
                abort(403)
            
            user_data = user_doc.to_dict()
            user_role = user_data.get('role', 'student') # Default to student
            
            if user_role not in allowed_roles:
                abort(403) # Unauthorized
                
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/institution/join', methods=['GET', 'POST'])
@require_login
def institution_join():
    if request.method == 'POST':
        code = request.form.get('invite_code', '').strip().upper()
        uid = session['uid']
        
        # Validate Code
        invites_ref = db.collection('invites').where('code', '==', code).where('used', '==', False).limit(1)
        invites = list(invites_ref.stream())
        
        if not invites:
            flash('Invalid or expired invite code.', 'error')
            return redirect(url_for('institution_join'))
            
        invite_doc = invites[0]
        invite_data = invite_doc.to_dict()
        
        # Link User to Institution
        inst_id = invite_data['institution_id']
        class_id = invite_data.get('class_id')
        role = invite_data.get('role', 'student')
        
        batch = db.batch()
        user_ref = db.collection('users').document(uid)
        
        updates = {
            'institution_id': inst_id,
            'role': role
        }
        if class_id:
            updates['class_ids'] = firestore.ArrayUnion([class_id])
            
        batch.update(user_ref, updates)
        
        if invite_data.get('one_time', True):
            batch.update(invite_doc.reference, {'used': True, 'used_by': uid, 'used_at': datetime.utcnow().isoformat()})
            
        # Add to class roster
        if class_id:
             class_ref = db.collection('classes').document(class_id)
             batch.update(class_ref, {'students': firestore.ArrayUnion([uid])})
             
        batch.commit()
        
        flash('Successfully joined institution!', 'success')
        return redirect(url_for('profile_dashboard'))
        
    return render_template('institution_join.html')


@app.route('/institution/dashboard')
@require_role(['teacher', 'admin'])
def institution_dashboard():
    uid = session['uid']
    user_data = get_user_data(uid)
    inst_id = user_data.get('institution_id')
    
    if not inst_id:
        flash('No institution assigned.', 'error')
        return redirect(url_for('profile_dashboard'))

    # --- 1. DATA FETCHING (ISOLATED) ---
    
    # Get Classes assigned to teacher
    classes_ref = db.collection('classes').where('institution_id', '==', inst_id)
    classes_docs = list(classes_ref.stream())
    
    # Filter by teacher's assigned classes if applicable
    if user_data.get('role') == 'teacher':
        my_class_ids = user_data.get('class_ids', [])
        if my_class_ids:
            classes_docs = [d for d in classes_docs if d.id in my_class_ids]
    
    classes = {d.id: d.to_dict() for d in classes_docs}
    
    # --- 2. ISLAND A: REAL-TIME HEATMAP AGGREGATION ---
    heatmap_data = defaultdict(int)
    
    # Fetch sessions for all students in this institution from the last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Note: In production with thousands of students, this should be pre-aggregated.
    # For now, we aggregate in real-time for currently active classes.
    for class_id, cls_data in classes.items():
        student_ids = cls_data.get('students', [])
        for sid in student_ids:
            sessions_ref = db.collection('users').document(sid).collection('study_sessions')\
                .where('start_time', '>=', thirty_days_ago.isoformat()).stream()
            
            for s in sessions_ref:
                s_data = s.to_dict()
                start_time_str = s_data.get('start_time')
                if start_time_str:
                    try:
                        dt = datetime.fromisoformat(start_time_str)
                        # Key: "DayIndex-Hour" (e.g., "0-14" for Monday 2 PM)
                        key = f"{dt.weekday()}-{dt.hour}"
                        heatmap_data[key] += 1
                    except:
                        pass
    
    # --- 3. ISLAND B: PREDICTIVE ENGINE (AI Logic) ---
    at_risk_students = []
    
    # Collect all unique student IDs from all classes
    all_student_ids = set()
    for class_id, cls_data in classes.items():
        all_student_ids.update(cls_data.get('students', []))
    
    # Batch process for performance
    for sid in all_student_ids:
        s_doc = db.collection('users').document(sid).get()
        if not s_doc.exists:
            continue
        s_data = s_doc.to_dict()
        
        # Risk Logic 1: Stagnation Trigger
        last_active_str = s_data.get('last_login_date')
        status = 'healthy'
        days_inactive = 0
        
        if last_active_str:
            try:
                last_active = datetime.fromisoformat(last_active_str)
                days_inactive = (datetime.utcnow() - last_active).days
                if days_inactive > 7:
                    status = 'stagnating'
            except:
                days_inactive = 30
        else:
            days_inactive = 30
            status = 'stagnating'
            
        # Risk Logic 2: Velocity Gradient
        results = s_data.get('exam_results', [])
        momentum = 0 # Slope
        if len(results) >= 2:
            sorted_res = sorted(results, key=lambda x: x.get('date', ''), reverse=True)
            try:
                # Calculate slope of last 4 exams
                series = [float(r.get('percentage', r.get('score', 0))) for r in sorted_res[:4]][::-1]
                if len(series) >= 2:
                    momentum = series[-1] - series[0] # Simple gradient
                    if momentum < -5: # Grade drop > 5%
                        status = 'declining' if status == 'healthy' else 'critical'
            except:
                pass

        if status != 'healthy':
            # Map back to class name
            student_class = "Unknown"
            for cid, cdata in classes.items():
                if sid in cdata.get('students', []):
                    student_class = cdata.get('name', cid)
                    break

            at_risk_students.append({
                'uid': sid,
                'name': s_data.get('name', 'Unknown Student'),
                'class': student_class,
                'status': status,
                'days_inactive': days_inactive,
                'momentum': round(momentum, 2)
            })

    context = {
        'user': user_data,
        'institution_id': inst_id,
        'classes': classes,
        'at_risk_students': at_risk_students,
        'heatmap_data': dict(heatmap_data)
    }
    
    return render_template('institution_dashboard.html', **context)

@app.route('/institution/generate_invite', methods=['POST'])
@require_role(['admin', 'teacher'])
def generate_invite():
    uid = session['uid']
    user_data = get_user_data(uid)
    inst_id = user_data.get('institution_id')
    
    class_id = request.form.get('class_id')
    role = request.form.get('role', 'student')
    
    # Generate 6-char code
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
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
@require_role(['teacher', 'admin'])
def send_nudge():
    uid = session['uid']
    user_data = get_user_data(uid)
    inst_id = user_data.get('institution_id')
    
    student_uid = request.json.get('student_uid')
    message = request.json.get('message', 'Your teacher has sent you a reminder to stay on track!')
    
    # Create notification
    db.collection('institutions').document(inst_id).collection('notifications').add({
        'recipient_uid': student_uid,
        'sender_uid': uid,
        'sender_name': user_data.get('name', 'Teacher'),
        'message': message,
        'type': 'nudge',
        'read': False,
        'created_at': datetime.utcnow().isoformat()
    })
    
    return jsonify({'success': True, 'message': 'Nudge sent!'})

@app.route('/institution/broadcast', methods=['POST'])
@require_role(['teacher', 'admin'])
def broadcast_message():
    uid = session['uid']
    user_data = get_user_data(uid)
    inst_id = user_data.get('institution_id')
    
    message = request.form.get('message')
    class_id = request.form.get('class_id')  # Optional: target specific class
    
    if not message:
        return jsonify({'error': 'Message required'}), 400
    
    # Get target students
    if class_id:
        class_doc = db.collection('classes').document(class_id).get()
        if class_doc.exists:
            student_uids = class_doc.to_dict().get('students', [])
        else:
            student_uids = []
    else:
        # Broadcast to all students in institution
        users_ref = db.collection('users').where('institution_id', '==', inst_id).where('role', '==', 'student')
        student_uids = [u.id for u in users_ref.stream()]
    
    # Create notification for each student
    batch = db.batch()
    notif_ref = db.collection('institutions').document(inst_id).collection('notifications')
    
    for student_uid in student_uids:
        batch.set(notif_ref.document(), {
            'recipient_uid': student_uid,
            'sender_uid': uid,
            'sender_name': user_data.get('name', 'Teacher'),
            'message': message,
            'type': 'broadcast',
            'read': False,
            'created_at': datetime.utcnow().isoformat()
        })
    
    batch.commit()
    
    flash(f'Message sent to {len(student_uids)} students!', 'success')
    return redirect(url_for('institution_dashboard'))

@app.route('/institution/class/<class_id>/syllabus', methods=['GET', 'POST'])
@require_role(['teacher', 'admin'])
def manage_class_syllabus(class_id):
    uid = session['uid']
    user_data = get_user_data(uid)
    inst_id = user_data.get('institution_id')
    
    # Verify class belongs to institution
    class_doc = db.collection('classes').document(class_id).get()
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
    
    # Get syllabus (simplified - you'd fetch based on class metadata)
    # For now, using a sample structure
    syllabus = get_syllabus('highschool', 'CBSE', '10')  # Placeholder
    
    context = {
        'user': user_data,
        'class_id': class_id,
        'class_data': class_data,
        'syllabus': syllabus,
        'exclusions': exclusions
    }
    
    return render_template('class_syllabus.html', **context)

@app.route('/institution/student/<student_uid>')
@require_role(['teacher', 'admin'])
def student_detail(student_uid):
    uid = session['uid']
    user_data = get_user_data(uid)
    inst_id = user_data.get('institution_id')
    
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
        'user': user_data,
        'student': student_data,
        'student_uid': student_uid,
        'progress_data': progress_data,
        'recent_results': recent_results,
        'sessions': sessions
    }
    
    return render_template('student_detail.html', **context)

@app.route('/institution/students')
@require_role(['teacher', 'admin'])
def all_students():
    uid = session['uid']
    user_data = get_user_data(uid)
    inst_id = user_data.get('institution_id')
    
    if not inst_id:
        flash('No institution assigned.', 'error')
        return redirect(url_for('profile_dashboard'))
    
    # Get all students in institution
    students_ref = db.collection('users').where('institution_id', '==', inst_id).where('role', '==', 'student')
    students_docs = list(students_ref.stream())
    
    students_list = []
    for s_doc in students_docs:
        s_data = s_doc.to_dict()
        s_data['uid'] = s_doc.id
        
        # Calculate quick stats
        progress = calculate_academic_progress(s_data)
        s_data['progress_overall'] = progress.get('overall', 0)
        
        # Last login
        last_login = s_data.get('last_login_date', '')
        if last_login:
            try:
                last_date = datetime.fromisoformat(last_login).date() if isinstance(last_login, str) else last_login
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
            c_doc = db.collection('classes').document(cid).get()
            if c_doc.exists:
                class_names.append(c_doc.to_dict().get('name', cid))
        s_data['class_names'] = ', '.join(class_names) if class_names else 'No class'
        
        students_list.append(s_data)
    
    # Sort by name
    students_list.sort(key=lambda x: x.get('name', ''))
    
    context = {
        'user': user_data,
        'students': students_list,
        'total_students': len(students_list)
    }
    
    return render_template('all_students.html', **context)

@app.route('/institution/settings')
@require_role(['admin'])
def institution_settings():
    uid = session['uid']
    user_data = get_user_data(uid)
    inst_id = user_data.get('institution_id')
    
    if not inst_id:
        flash('No institution assigned.', 'error')
        return redirect(url_for('profile_dashboard'))
    
    # Get institution data
    inst_doc = db.collection('institutions').document(inst_id).get()
    inst_data = inst_doc.to_dict() if inst_doc.exists else {}
    
    # Get all classes
    classes_ref = db.collection('classes').where('institution_id', '==', inst_id)
    classes = [{'id': c.id, **c.to_dict()} for c in classes_ref.stream()]
    
    context = {
        'user': user_data,
        'institution': inst_data,
        'institution_id': inst_id,
        'classes': classes
    }
    
    return render_template('institution_settings.html', **context)

# ============================================================================
# STUDENT-SIDE NOTIFICATIONS
# ============================================================================

@app.route('/api/notifications')
@require_login
def get_notifications():
    """API endpoint for students to fetch their notifications"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        return jsonify({'notifications': []})
        
    inst_id = user_data.get('institution_id')
    if not inst_id:
        return jsonify({'notifications': []})
    
    # Get all unread notifications for this user in their institution
    # We remove order_by to avoid the need for a composite index
    try:
        notifs_ref = db.collection('institutions').document(inst_id).collection('notifications')\
            .where('recipient_uid', '==', uid)\
            .where('read', '==', False)
        
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
    user_data = get_user_data(uid)
    inst_id = user_data.get('institution_id')
    
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



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
