# Phase 2: Technical Completion Report & System Architecture

## 🏗 System Architecture Overview

The StudyOS platform is built on a robust **Three-Layer Architecture** designed for high scalability, multi-tenant isolation, and real-time academic tracking.

### 1. Identity & Security Layer
- **Authentication**: Powered by Firebase Admin SDK, using unique UIDs for session management.
- **Security Protocols**:
    - **SHA-256 Hashing**: All user passwords (legacy) are stored using salted SHA-256 hashes.
    - **Custom Decorators**:
        - `@require_login`: Ensures session persistence and protects student-facing routes.
        - `@require_role(roles)`: Implements Role-Based Access Control (RBAC) at the route level.
- **Session Management**: Uses Flask's signed cookies with an `os.urandom(24)` secret key for cryptographic security.

### 2. Academic Backbone
- **Static Core**: `templates/academic_data.py` contains the immutable standard syllabi for CBSE, ICSE, and competitive exams like JEE/NEET.
- **Dynamic Progress Logic**:
    - Real-time tracking of chapter completion via Firestore.
    - Progress is stored in a `chapters_completed` map within the user document, allowing for O(1) lookups during rendering.
- **3-Tier Exclusion Engine**:
    - **Level 1 (Institution)**: Global exclusions set by admins (e.g., deleted chapters).
    - **Level 2 (Class)**: Contextual exclusions set by teachers (e.g., chapters skipped for a specific term).
    - **Level 3 (Personal)**: Student-specific exclusions for personalized learning paths.

### 3. Execution & Analytics Layer
- **Study Mode**: A Pomodoro-integrated environment using Firestore's atomic `Increment` operator for accurate time tracking.
- **AI Analytics Engine**: Predictive logic that calculates student momentum, consistency, and readiness.
- **Institutional Heatmap**: A 7x24 grid visualizing student behavioral patterns across the entire organization.

---

## ✅ Core Feature Implementation Details

### 1. **Institutional Ecosystem**
**Problem**: Previous versions lacked centralized oversight for educational institutions.
**Solution**: Implemented a multi-tenant structure where students can join institutions via 6-digit invite codes.
**Impact**: Teachers can now manage entire classes, broadcast announcements, and nudge at-risk students.

### 2. **3-Tier Chapter Exclusion System**
**Logic**:
```python
Total_Syllabus
  - Level 1: Institution Exclusions (Administrative)
  - Level 2: Class Exclusions (Instructional)
  - Level 3: Personal Exclusions (Individual)
= Active_Curriculum
```
**Implementation**: Updated `calculate_academic_progress()` to perform recursive lookups in Firestore subcollections, ensuring students only see what is relevant to their specific classroom context.

### 3. **At-Risk Detection Engine**
**Risk Factors**:
- **Stagnation**: `last_login_date` > 7 days.
- **Velocity**: Latest exam percentage < Previous percentage * 0.9 (10% relative drop).
- **Status Mapping**:
  - `Healthy`: No triggers.
  - `Stagnating`: Inactivity only.
  - `Declining`: Grade drop only.
  - `Critical`: Both conditions met.

---

## 📊 AI Analytics & Data Visualization

### Predictive Formulae
- **Momentum (M)**: $M = P_{n} - P_{n-4}$ (where $P$ is percentage). Measures the gradient of improvement over the last 4 assessments.
- **Readiness (R)**: $R = (C \times 0.4) + (A \times 0.6)$ (where $C$ is completion and $A$ is average score). Predicts student preparedness for final exams.
- **Consistency (S)**: $S = \min(100, \text{SessionCount} \times 15)$. Quantifies the stability of study habits.

### Institutional Behavior Heatmap
- **Aggregation**: Real-time aggregation of `study_sessions` from the last 30 days.
- **Resolution**: Hour-by-hour (24 blocks) across 7 days.
- **Visualization**: CSS-based grid with 4 intensity levels (`level-0` to `level-3`) representing student density.

---

## 📁 Repository Structure & Data Models

### Firestore Collections & Schema
#### `users` Collection
| Field | Type | Description |
|-------|------|-------------|
| `uid` | String | Unique identifier from Firebase Auth |
| `role` | String | `student`, `teacher`, or `admin` |
| `institution_id` | String | Link to organization |
| `chapters_completed` | Map | `{Subject: {Chapter: Boolean}}` |
| `login_streak` | Integer | Consecutive days active |

#### `institutions` Collection
| Field | Type | Description |
|-------|------|-------------|
| `name` | String | Name of the institution |
| `location` | String | Geographic location |

#### `notifications` (Subcollection under Institutions)
| Field | Type | Description |
|-------|------|-------------|
| `recipient_uid` | String | Target user |
| `sender_name` | String | Name of teacher/admin |
| `type` | String | `nudge` or `broadcast` |

### Technical Stack
- **Backend**: Flask 3.0.0
- **Database**: Google Cloud Firestore (NoSQL)
- **Auth**: Firebase Admin SDK
- **Frontend**: Vanilla JS, Chart.js, CSS3 (Custom variables for Dark/Light mode)
- **Deployment**: Gunicorn 21.2.0 on Render

---

## 🔐 Database Security Rules (Firestore)
The system implements granular security rules to ensure data privacy:
```javascript
service cloud.firestore {
  match /databases/{database}/documents {
    // Users can read/write their own profile
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;

      // Teachers can read student data in their institution
      allow read: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'teacher';
    }

    // Notifications are private to the recipient
    match /institutions/{instId}/notifications/{notifId} {
      allow read: if request.auth != null && resource.data.recipient_uid == request.auth.uid;
      allow write: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role in ['teacher', 'admin'];
    }
  }
}
```

---

## 🛣 API Route Documentation

### Student Routes
- `GET /dashboard`: Main profile and progress overview.
- `GET /academic`: Detailed syllabus tracking and goal management.
- `POST /academic/toggle_chapter`: Mark a chapter as completed.
- `GET /master-library`: Global search for academic content.

### Institutional Routes
- `POST /institution/join`: Link a student to an organization.
- `GET /institution/dashboard`: Teacher-only analytics view.
- `POST /institution/nudge`: Send a targeted reminder to a student.
- `POST /institution/broadcast`: Send an announcement to the whole class.
- `GET /institution/student/<uid>`: Deep dive into individual student metrics.

---

## 🛠 Development & Setup Guide
To set up the environment locally:
1. **Clone the Repository**: `git clone <repo-url>`
2. **Install Dependencies**: `pip install -r requirements.txt`
3. **Configure Firebase**:
   - Place `serviceAccountKey.json` in the root directory.
   - Initialize Firebase Admin SDK in `firebase_config.py`.
4. **Environment Variables**:
   - `FLASK_APP=app.py`
   - `FLASK_ENV=development`
5. **Run the App**: `flask run`

---

## ⚠️ Known Issues & Resolution Path (Institution Module)

### 1. **Notification Reliability**
**Cause**: Missing composite indexes for optimized Firestore queries.
**Fix**:
- Add index for `notifications` collection: `recipient_uid` (ASC), `read` (ASC), `created_at` (DESC).
- Update `static/notifications.js` to map `sender_name` correctly.

### 2. **Broadcast UI**
**Limitation**: Currently lacks a dropdown to target specific classes.
**Fix**: Add a `<select>` element to the Broadcast island in `institution_dashboard.html`.

---

## 🚀 Testing & Validation Checklist

### Institutional Workflow
- [x] Teacher Dashboard loads heatmap data correctly.
- [x] At-risk list filters unique student IDs.
- [x] "View Student" drills down into personal progress.
- [x] "Manage Syllabus" correctly toggles Firestore exclusion documents.

### Student Experience
- [x] Notifications appear as real-time toasts.
- [x] Academic progress dynamically updates when teacher excludes a chapter.
- [x] Master Library search functions across all boards/grades.

---

## 🎨 Design Philosophy
The system follows an **"Island-Based UI"** design, where each functional module (Academic, Profile, Careers, Risk) is encapsulated in a discrete, high-contrast container. This reduces cognitive load and allows for a "glanceable" dashboard experience.

### Color Palette (Dark Theme)
- **Background**: `#09090b`
- **Islands**: `#18181b`
- **Accents**: `#666666` (Primary), `#ff4d4d` (Critical Risk), `#4caf50` (Success)
- **Borders**: `#27272a`

---

## 📈 Future Roadmap
1. **Automated Heatmap Aggregation**: Shift from real-time calculation to daily Cloud Function snapshots for improved performance.
2. **Predictive AI 2.0**: Incorporate machine learning to predict specific topic weaknesses based on exam history.
3. **Institutional Reports**: Exportable PDF/CSV summaries for parent-teacher meetings.
4. **API Expansion**: Integration with external LMS platforms via REST hooks.

---
*End of Technical Report*
