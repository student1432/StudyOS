# Sclera Technical Report: File-by-File Analysis

This report provides a technical breakdown of the Sclera (formerly StudyOS) codebase, categorizing files by their functional roles within the Three-Layer Architecture.

## 1. Core Backend & Logic
*   **`app.py`**: The central Flask application. It defines the routing system, session management, and the core business logic for students, teachers, and admins. It also implements the AI Analytics Engine for calculating Momentum, Readiness, and Consistency.
*   **`config.py`**: Manages environment-specific configurations (Development, Production, Testing), including security keys, rate limits, and API credentials.
*   **`firebase_config.py`**: Initializes the Firebase Admin SDK, providing the bridge to Firestore (NoSQL database), Firebase Auth, and Firebase Storage.
*   **`ai_assistant.py`**: The interface for **Sclera AI**. It wraps the Google Gemini API, manages multi-turn conversation threads, and handles persistent storage of chat history in Firestore.

## 2. Academic & Career Data
*   **`templates/academic_data.py`**: The "Academic Backbone." It contains structured syllabi for boards like CBSE/ICSE and various grades, serving as the source of truth for progress tracking.
*   **`careers_data.py`**: A comprehensive database of career paths, related higher-education courses, and internships, enabling the career exploration features.
*   **`uploads/`**: A storage directory for academic resources (PDFs, docs) uploaded by teachers for specific classes.

## 3. Utility Modules (`utils/`)
*   **`utils/security.py`**: Implements the `PasswordManager` (using Bcrypt) and `login_rate_limiter` for application security.
*   **`utils/validators.py`**: Contains Marshmallow schemas used for rigorous input validation during registration and login.
*   **`utils/logger.py`**: Provides structured JSON logging for security auditing and error tracking.
*   **`utils/timezone.py`**: Ensures all timestamps across the global platform are synchronized and timezone-aware.
*   **`utils/cache.py`**: A disk-based caching system used to optimize the performance of data-heavy operations.

## 4. Frontend & Presentation
*   **`templates/`**: A collection of over 50 Jinja2 templates.
    *   `main_dashboard.html`: The central student hub.
    *   `institution_*.html`: Dedicated views for the Institutional Layer (Admin/Teacher portals).
    *   `ai_assistant.html`: The premium "Dark Academic" chat interface.
    *   `_sidebar.html`, `_topnav.html`: Modular UI components for consistent navigation.
*   **`static/styles.css`**: The primary stylesheet implementing the "Dark Academic" design philosophy.
*   **`static/notifications.js`**: Handles the asynchronous fetching and display of real-time student notifications.

## 5. Database & Deployment
*   **`firestore.rules`**: Defines granular security rules to protect user data and ensure only authorized roles (Student/Teacher/Admin) can access specific collections.
*   **`firestore.indexes.json`**: Configures composite indexes required for complex queries (e.g., filtering notifications or student analytics).
*   **`requirements.txt`**: Lists all Python dependencies, including Flask 3.0.0, Firebase Admin, and Flask-Talisman.
*   **`render.yaml`**: The Blueprint for deploying the application as a Web Service on the Render platform.
*   **`SUMMARY.md`**: High-level project overview for onboarding and documentation.

## 6. Maintenance & Infrastructure
*   **`migrate_chat_data.py`**: A utility script for migrating conversation history between different schema versions.
*   **`package.json`**: Manages JavaScript dependencies for frontend effects (e.g., the `ogl` library for landing page visuals).
*   **`tests/test_app.py`**: Contains unit and integration tests to verify the core functionality of the Flask application.
