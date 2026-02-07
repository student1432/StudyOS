# Fix Guide: Institution Broadcast & Nudge System

This guide outlines the steps required to fix the issues with the Broadcast and Nudge systems in the Institution module.

## 1. Firestore Composite Index Requirement

The notification system queries Firestore using multiple filters and a sort order, which requires a composite index.

**Issue**: The following query in `app.py` (`/api/notifications`) will fail without an index:
```python
db.collection('institutions').document(inst_id).collection('notifications')\
    .where('recipient_uid', '==', uid)\
    .where('read', '==', False)\
    .order_by('created_at', direction=firestore.Query.DESCENDING)
```

**Fix Steps**:
1.  Open the [Firebase Console](https://console.firebase.google.com/).
2.  Navigate to **Firestore Database** -> **Indexes**.
3.  Click **Add Index**.
4.  Set the Collection ID to `notifications`.
5.  Add the following fields:
    *   `recipient_uid`: Ascending
    *   `read`: Ascending
    *   `created_at`: Descending
6.  Select **Collection** scope.
7.  Click **Create Index**.

---

## 2. Frontend Property Mismatch in `notifications.js`

The backend returns notification objects with a `sender_name` property, but the client-side script expects `sender`.

**Issue** in `static/notifications.js`:
```javascript
<span class="notification-sender">${notif.sender}</span>
```

**Fix Steps**:
1.  Open `static/notifications.js`.
2.  Locate the `showNotification` function.
3.  Change `${notif.sender}` to `${notif.sender_name}`.

---

## 3. Broadcast Targeting (UI Enhancement)

Currently, the Broadcast island sends messages to all students in the institution by default.

**Fix Steps**:
1.  Modify `templates/institution_dashboard.html`.
2.  In the **Broadcast** island, add a `<select>` dropdown before the `<textarea>` to allow selecting a specific class.
3.  Ensure the `class_id` is sent with the form submission.
4.  Example HTML:
    ```html
    <select name="class_id">
        <option value="">All Students</option>
        {% for cid, cdata in classes.items() %}
        <option value="{{ cid }}">{{ cdata.name }}</option>
        {% endfor %}
    </select>
    ```

---

## 4. Ensure Notification Listener is Active

The notification system relies on a JavaScript listener to poll for new messages.

**Fix Steps**:
1.  Ensure `{% include 'notifications_snippet.html' %}` is included at the end of the `<body>` tag in all student-facing templates (e.g., `academic_dashboard.html`, `profile_resume.html`).
2.  Alternatively, move the listener logic to a global layout if using template inheritance.
