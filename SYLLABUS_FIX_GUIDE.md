# Syllabus Configuration Fix Guide

This guide describes how to fix the issue where the teacher's dashboard shows the wrong syllabus (e.g., Grade 10 chapters for a Grade 9 class).

## 1. The Issue
In `app.py`, the route `/institution/class/<class_id>/syllabus` was using a hardcoded placeholder to fetch the syllabus:
```python
syllabus = get_syllabus('highschool', 'CBSE', '10')  # Placeholder
```
This caused every class, regardless of its name or ID, to display the Grade 10 syllabus.

## 2. The Code Fix
I have updated `app.py` to retrieve the `grade`, `board`, and `purpose` dynamically from the class document in Firestore:

```python
# Updated logic in manage_class_syllabus
purpose = class_data.get('purpose', 'highschool')
board = class_data.get('board', 'CBSE')
grade = class_data.get('grade', '10')

syllabus = get_syllabus(purpose, board, grade)
```

## 3. Database Update (Action Required)
To ensure the correct syllabus is shown for **CLASS_9A9**, you must ensure the document in the `classes` collection has the correct metadata fields.

### Steps:
1.  Open the [Firebase Console](https://console.firebase.google.com/).
2.  Navigate to **Firestore Database** -> **classes** collection.
3.  Select the document with ID `CLASS_9A9`.
4.  Add or update the following fields:
    *   `grade`: `9` (String)
    *   `board`: `CBSE` (String)
    *   `purpose`: `highschool` (String)

Once these fields are set, the dashboard will fetch the Grade 9 syllabus for that specific class.

## 4. Why renaming the class wasn't enough
The system doesn't "read" the name of the class (e.g., "Class 9 - Section A9") to determine the syllabus. It relies on structured data fields (`grade`, `board`) to query the `academic_data.py` module. This ensures that names can be flexible while the logic remains robust.
