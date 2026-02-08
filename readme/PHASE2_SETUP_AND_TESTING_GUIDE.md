# Phase 2: Institutional Ecosystem - Setup & Testing Guide

This guide details exactly how to set up your Firestore database, configure security, and test the new Institutional/Teacher features.

## 1. Firestore Data Structure (Manual Setup)

Since there is no "Super Admin" UI yet, you must manually create the initial Institution and Class documents in the Firebase Console to bootstrap the system.

### A. Create an Institution
**Collection**: `institutions`
**Document ID**: `INST_001` (or any unique ID)

| Field | Type | Value | Description |
| :--- | :--- | :--- | :--- |
| `name` | String | `Springfield High School` | Name of the institution |
| `plan` | String | `pro` | Subscription plan (optional) |
| `created_at` | String | `2023-10-27T10:00:00` | ISO Timestamp |

### B. Create a Class
**Collection**: `classes`
**Document ID**: `CLASS_10A` (or any unique ID)

| Field | Type | Value | Description |
| :--- | :--- | :--- | :--- |
| `name` | String | `Grade 10 - Section A` | Class name |
| `institution_id` | String | `INST_001` | **MUST MATCH** the Institution ID above |
| `teacher_id` | String | `(Leave empty for now)` | Will link to a teacher later |
| `students` | Array | `[]` (Empty Array) | List of student UIDs |

### C. Configure a Teacher User
Find an existing user (or create a new one via Signup) to act as the **Teacher**.
**Collection**: `users`
**Document ID**: `<TEACHER_UID>`

**Add/Update these specific fields:**

| Field | Type | Value | Description |
| :--- | :--- | :--- | :--- |
| `role` | String | `teacher` | **CRITICAL**: Grants access to dashboard |
| `institution_id` | String | `INST_001` | **CRITICAL**: Scopes access to this institution |
| `class_ids` | Array | `["CLASS_10A"]` | Access to specific class data |

### D. Configure a Student User (For Testing Risks)
Find another user to act as a **Student**.
**Collection**: `users`
**Document ID**: `<STUDENT_UID>`

**Ensure they are linked (Simulate Joining):**

| Field | Type | Value | Description |
| :--- | :--- | :--- | :--- |
| `role` | String | `student` | Default capability |
| `institution_id` | String | `INST_001` | Links to institution |
| `class_ids` | Array | `["CLASS_10A"]` | Links to class |

**Update `classes/CLASS_10A`:**
Add the `<STUDENT_UID>` to the `students` array.

---

## 2. Security Rules (Target: `firestore.rules`)

Ensure your `firestore.rules` file contains the RBAC logic we implemented.

**Key Logic to Verify:**
1.  **`isTenant(instId)`**: Checks if `request.auth.token.institution_id == instId`.
    *   *Note: In our current `app.py`, we are mocking RBAC via session checks. Real custom claims require a simplified Admin script to set `admin.auth().setCustomUserClaims(uid, {institution_id: '...'})`.*
    *   **For now**, the `app.py` decorator `@require_role` handles the logic on the server side using the User Document, which is safe for this phase.

---

## 3. Testing Scenarios

### Test 1: Accessing the Dashboard
1.  **Login** as the **Teacher** user you configured in Step 1C.
2.  Navigate manually to: `http://localhost:5000/institution/dashboard`
3.  **Expected Result**:
    *   You should see the "Institution Overview".
    *   The "Class Management" island should show `Grade 10 - Section A`.

### Test 2: "At-Risk" Logic
1.  **Login** as the **Student** user.
2.  **Simulate Stagnation**:
    *   In Firestore `users/<STUDENT_UID>`, set `last_login_date` to `2023-01-01` (Old date).
3.  **Simulate Grade Drop**:
    *   In Firestore `users/<STUDENT_UID>`, add `exam_results` map array:
        *   Item 0: `{ "date": "2023-10-01", "score": 90, "max_score": 100 }`
        *   Item 1: `{ "date": "2023-10-10", "score": 40, "max_score": 100 }` (Big drop)
4.  **Verify**:
    *   Login as **Teacher** again.
    *   Go to `/institution/dashboard`.
    *   **Expected**: The student should appear in the "At-Risk Students" list with tags **"Inactive"** and **"Grades Drop"**.

### Test 3: Invite System
1.  **As Teacher**:
    *   On the dashboard, click **"Generate Invite"**.
    *   Enter Role: `student` and Class ID: `CLASS_10A`.
    *   **Expected**: You get a 6-digit code (e.g., `ABC123`).
    *   **Firestore Check**: A new document in `invites` collection should appear with `code: "ABC123"`.
2.  **As New Student**:
    *   Create a **fresh** user account (Sign up).
    *   Navigate to `http://localhost:5000/institution/join`.
    *   Enter the code `ABC123`.
    *   Click "Join Now".
    *   **Expected**: Success message.
    *   **Firestore Check**:
        *   The New User document has `institution_id: "INST_001"` and `class_ids: ["CLASS_10A"]`.
        *   The `classes/CLASS_10A` document `students` array now contains the New User UID.

---

## 4. Troubleshooting

**Error: "No institution assigned"**
*   **Fix**: Ensure your Teacher User document has the `institution_id` field set exactly to the ID of an existing document in the `institutions` collection.

**Error: "403 Forbidden"**
*   **Fix**: Ensure your Teacher User document has `role: "teacher"` or `role: "admin"`.

**Dashboard is Empty**
*   **Fix**: Ensure `class_ids` in the Teacher User document matches the Document IDs in the `classes` collection.

**Invite Code Invalid**
*   **Fix**: Check the `invites` collection. Ensure `used` is `false`. Codes are case-sensitive (though our logic handles uppercase).
