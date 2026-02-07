# Quick Start Guide

## ⚠️ IMPORTANT FIX APPLIED

**Issue**: Duplicate `logout` route was causing startup error.
**Status**: ✅ FIXED in the provided code.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- Firebase project (see SETUP_GUIDE.md)
- `serviceAccountKey.json` from Firebase

### Step 1: Install Dependencies
```bash
cd student_platform
pip install -r requirements.txt
```

### Step 2: Add Firebase Key
1. Download `serviceAccountKey.json` from Firebase Console
2. Place it in the project root (same folder as `app.py`)

### Step 3: Run the Application
```bash
python app.py
```

You should see:
```
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://0.0.0.0:5000
```

### Step 4: Open in Browser
Navigate to: `http://localhost:5000`

---

## ✅ Verification Checklist

After starting the app:

1. **Homepage Loads**
   - Should redirect to `/signup`
   - Signup form displays

2. **Create Account**
   - Fill in all fields
   - Select purpose
   - Should redirect to setup page

3. **Complete Setup**
   - Fill in purpose-specific fields
   - Should redirect to profile dashboard

4. **Test Navigation**
   - Profile dashboard loads
   - All dashboard links work
   - Logout works

---

## 🐛 Troubleshooting

### Error: "AssertionError: View function mapping is overwriting an existing endpoint function: logout"

**Status**: ✅ Already fixed in provided code
**Cause**: Duplicate `logout` route definition
**Solution**: The duplicate has been removed

### Error: "ModuleNotFoundError: No module named 'firebase_admin'"

**Cause**: Dependencies not installed
**Solution**: Run `pip install -r requirements.txt`

### Error: "serviceAccountKey.json not found"

**Cause**: Firebase key missing
**Solution**: 
1. Go to Firebase Console
2. Project Settings → Service Accounts
3. Generate new private key
4. Download and rename to `serviceAccountKey.json`
5. Place in project root

### Error: "Firebase connection failed"

**Cause**: Invalid Firebase credentials or network issue
**Solution**:
1. Verify `serviceAccountKey.json` is valid
2. Check internet connection
3. Verify Firebase project is active

### Port Already in Use

**Cause**: Port 5000 is occupied
**Solution**: Change port in `app.py`:
```python
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)  # Changed to 5001
```

---

## 📝 Quick Test Sequence

1. **Signup Test**
   ```
   URL: http://localhost:5000/signup
   - Enter test data
   - Submit
   - Should redirect to setup
   ```

2. **Login Test**
   ```
   URL: http://localhost:5000/login
   - Enter credentials
   - Submit
   - Should reach profile dashboard
   ```

3. **Profile Dashboard Test**
   ```
   URL: http://localhost:5000/dashboard
   - See your name and avatar
   - All navigation buttons present
   ```

4. **Academic Dashboard Test**
   ```
   URL: http://localhost:5000/academic
   - See subjects based on your purpose
   - Syllabus displays (READ-ONLY)
   ```

5. **Goals Dashboard Test**
   ```
   URL: http://localhost:5000/goals
   - Add a goal
   - Should save successfully
   ```

6. **Tasks Dashboard Test**
   ```
   URL: http://localhost:5000/tasks
   - Add a task
   - Should save successfully
   ```

7. **Results Dashboard Test**
   ```
   URL: http://localhost:5000/results
   - Add exam result
   - Statistics calculate
   ```

7. **Logout Test**
   ```
   - Click logout
   - Should redirect to login
   - Session cleared
   ```

---

## 🔥 Firebase Setup Reminder

Before running, ensure Firebase is configured:

1. ✅ Firebase project created
2. ✅ Authentication enabled (Email/Password)
3. ✅ Firestore database created
4. ✅ Service account key downloaded
5. ✅ `serviceAccountKey.json` in project root

See `SETUP_GUIDE.md` for detailed Firebase setup instructions.

---

## 📞 Getting Help

- Check `SETUP_GUIDE.md` for Firebase configuration
- See `TESTING_GUIDE.md` for comprehensive testing
- Review `DEPLOYMENT.md` for production deployment
- Read `PHASE2_GUIDE.md` for feature documentation

---

## ✅ All Fixed and Ready!

The duplicate logout issue has been resolved. The app is ready to run.

**Next Steps:**
1. Install dependencies: `pip install -r requirements.txt`
2. Add Firebase key: `serviceAccountKey.json`
3. Run: `python app.py`
4. Test: Open `http://localhost:5000`

🚀 **You're ready to go!**
