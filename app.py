from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from firebase_config import auth, db
from firebase_admin import auth as admin_auth
from datetime import datetime
from templates.academic_data import get_syllabus, get_available_subjects
import os
import hashlib
from google.cloud.firestore import Increment
import uuid
from functools import wraps
from flask import render_template, request, redirect, url_for, abort, jsonify
from firebase_admin import firestore
from datetime import datetime
from datetime import date, datetime, timedelta



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

def calculate_academic_progress(user_data):
    purpose = user_data.get('purpose')
    chapters_completed = user_data.get('chapters_completed', {})
    academic_exclusions = user_data.get('academic_exclusions', {})
    chapter_name = user_data.get('chapter_name')
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
        return {'overall': 0, 'by_subject': {}, 'total_chapters': 0, 'total_completed': 0}
    by_subject = {}
    total_chapters = 0
    total_completed = 0
    for subject_name, subject_data in syllabus.items():
        chapters = subject_data.get('chapters', {})
        chapter_count = len(chapters)
        exclusion_key = f"{subject_name}::{chapter_name}"
        if academic_exclusions.get(exclusion_key):
            continue
        if chapter_count == 0:
            by_subject[subject_name] = 0
            continue
        completed = 0
        subject_completed_data = chapters_completed.get(subject_name, {})
        for chapter_name in chapters.keys():
            if subject_completed_data.get(chapter_name, False):
                completed += 1
        by_subject[subject_name] = round((completed / chapter_count) * 100, 1)
        total_chapters += chapter_count
        total_completed += completed
    overall = round((total_completed / total_chapters) * 100, 1) if total_chapters > 0 else 0
    return {'overall': overall, 'by_subject': by_subject, 'total_chapters': total_chapters, 'total_completed': total_completed}

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
    academic_exclusions = user_data.get('academic_exclusions', {})
    # Build flat chapter list with completion status for left panel
    syllabus_flat = {}
    for subject_name, subject_data in syllabus.items():
        chapters = subject_data.get('chapters', {})
        syllabus_flat[subject_name] = {}

        for chapter_name in chapters.keys():
            exclusion_key = f"{subject_name}::{chapter_name}"
            is_excluded = academic_exclusions.get(exclusion_key, False)

            is_done = False
            if not is_excluded:
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
    todos = db.collection('users').document(uid)\
        .collection('study_todos').stream()
    todo_list = [{'id': t.id, **t.to_dict()} for t in todos]

    return render_template(
        'study_mode.html',
        name=session.get('name'),
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

    results = user.get('exam_results', [])

    exam_map = {}
    timeline = []

    for r in results:
        if not r.get('max_score'):
            continue

        pct = (r['score'] / r['max_score']) * 100
        et = r.get('test_type')

        exam_map.setdefault(et, []).append(pct)

        if r.get('exam_date'):
            timeline.append({
                'date': r['exam_date'],
                'percentage': round(pct, 2)
            })

    exam_avg = {
        k: round(sum(v) / len(v), 2)
        for k, v in exam_map.items()
        
    }

    timeline = sorted(timeline, key=lambda x: x['date'])

    return render_template(
        'statistics.html',
        exam_avg=exam_avg,
        timeline=timeline,
        streak=user.get('login_streak', 0)
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
#app.routed('/admin/progress')(require_admin(admin_progress))
#app.route('/admin/resources')(require_admin(admin_resources))
#app.route('/admin/resources/add', methods=['GET', 'POST'])(require_admin(admin_resource_add))
#app.route('/admin/statistics')(require_admin(admin_statistics))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
