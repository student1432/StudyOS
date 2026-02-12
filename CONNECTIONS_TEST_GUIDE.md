# StudyOS Connections System - Complete Test Guide

## Overview
This guide provides comprehensive testing instructions for the StudyOS connections system, including people search, connections management, and study bubbles functionality.

## Prerequisites
1. **Flask App Running**: Ensure the StudyOS Flask application is running on `http://localhost:5000`
2. **Test Users**: Have at least 2-3 user accounts created for testing connections
3. **Browser Console**: Keep browser developer tools open to monitor JavaScript errors
4. **Network Tab**: Monitor API calls in browser network tab

## 🔍 Phase 1: Core Infrastructure Testing

### 1.1 Navigation & UI Loading
**Test Steps:**
1. Log in to StudyOS with a user account
2. Click "Community" in the left sidebar
3. Verify the page loads with:
   - ✅ Header: "Community - Connect with fellow students and build study groups"
   - ✅ Search section with input field and filter chips
   - ✅ Connections card (shows count)
   - ✅ Study Bubbles card with "Create Bubble" button
   - ✅ Theme compatibility (dark/light mode toggle works)

**Expected Results:**
- Page loads within 2 seconds
- All UI elements are visible and properly styled
- No JavaScript console errors
- Theme toggle affects all elements

### 1.2 People Search Functionality
**Test Steps:**
1. Navigate to Community dashboard
2. Type a name in the search box (minimum 2 characters)
3. Wait for search results to appear
4. Click filter chips (Grade, School, Subject)
5. Click "Connect" on a search result
6. Check browser console for API calls

**API Calls to Verify:**
```
GET /api/people/search?q=searchterm
POST /api/connections/send
```

**Expected Results:**
- ✅ Search results appear after typing
- ✅ Results show user avatars, names, academic info
- ✅ Connection status indicators work (Connect/Pending/Connected)
- ✅ Filter chips highlight when active
- ✅ "Connect" button sends request successfully
- ✅ Success toast notification appears

### 1.3 Connection Management
**Test Steps:**
1. Send connection requests to other users
2. Switch to different user account
3. Check "Connection Requests" section appears
4. Click "Accept" or "Decline" on requests
5. Verify connection appears in "Connections" list

**API Calls to Verify:**
```
GET /api/connections (for dashboard data)
POST /api/connections/{id}/accept
POST /api/connections/{id}/decline
```

**Expected Results:**
- ✅ Connection requests appear for recipient
- ✅ Accept/decline buttons work
- ✅ Page refreshes after action
- ✅ Connections list updates correctly
- ✅ Connection count badge updates

## 🫧 Phase 2: Study Bubbles Testing

### 2.1 Bubble Creation
**Test Steps:**
1. Click "Create Bubble" button in Study Bubbles card
2. Fill in bubble name (required) and description (optional)
3. Click "Create Bubble"
4. Verify bubble appears in dashboard

**API Calls to Verify:**
```
POST /api/bubbles/create
```

**Expected Results:**
- ✅ Modal appears when button clicked
- ✅ Form validation works (name required)
- ✅ Bubble creation succeeds
- ✅ Success notification appears
- ✅ Page refreshes and shows new bubble

### 2.2 Bubble Management (Future Phase)
**Note:** Full bubble management is Phase 3 - currently only creation is implemented

## 🔧 Troubleshooting Guide

### Search System Issues

**Problem: Search not working**
```
Solutions:
1. Check browser console for JavaScript errors
2. Verify Flask app is running: curl http://localhost:5000
3. Check API endpoint: GET /api/people/search?q=test
4. Verify user authentication (session cookie)
```

**Problem: No search results**
```
Solutions:
1. Ensure search query is ≥2 characters
2. Check user privacy settings in database
3. Verify other users exist in database
4. Check Firestore security rules
```

**Problem: Connection request fails**
```
Solutions:
1. Verify target user exists
2. Check if already connected/pending
3. Monitor POST /api/connections/send response
4. Verify session authentication
```

### Bubble Creation Issues

**Problem: Create Bubble button not visible**
```
Solutions:
1. Check CSS for .create-bubble-btn visibility
2. Verify button exists in HTML
3. Check JavaScript event binding
```

**Problem: Bubble creation fails**
```
Solutions:
1. Verify POST /api/bubbles/create endpoint exists
2. Check request payload format
3. Monitor API response for errors
4. Verify user authentication
```

### Common Issues

**Problem: JavaScript errors in console**
```
Solutions:
1. Check for missing DOM elements
2. Verify all required functions are defined
3. Check for syntax errors in JavaScript
4. Ensure proper event binding
```

**Problem: API returns 500 error**
```
Solutions:
1. Check Flask application logs
2. Verify database connection
3. Check Firestore permissions
4. Monitor server-side errors
```

**Problem: Page not loading**
```
Solutions:
1. Check Flask app startup logs
2. Verify route registration
3. Check template file existence
4. Monitor browser network tab
```

## 🧪 Automated Testing Checklist

### Frontend Tests
- [ ] Page loads without errors
- [ ] Search input triggers API calls
- [ ] Filter chips update search parameters
- [ ] Connection buttons send correct requests
- [ ] Modal dialogs open/close properly
- [ ] Toast notifications display correctly
- [ ] Theme toggle affects all components

### API Tests
- [ ] `/api/people/search` returns valid JSON
- [ ] `/api/connections/send` creates requests
- [ ] `/api/connections/{id}/accept` updates status
- [ ] `/api/connections` returns user connections
- [ ] `/api/bubbles/create` creates new bubbles

### Database Tests
- [ ] User documents have connection fields
- [ ] Connections collection stores requests
- [ ] Bubbles collection stores group data
- [ ] Privacy settings control visibility

## 📊 Performance Benchmarks

### Response Times
- Page load: < 2 seconds
- Search results: < 1 second
- API responses: < 500ms
- Connection actions: < 1 second

### Scalability Tests
- 100+ users in search results
- 50+ active connections
- 20+ bubbles per user
- Concurrent API requests

## 🚀 Next Steps After Testing

### Phase 2 Implementation
1. Enhanced bubble management (join, leave, invite codes)
2. Bubble member lists and management
3. Improved connection request UI

### Phase 3 Implementation
1. Academic leaderboards
2. Consent management system
3. Advanced bubble settings

### Phase 4 Implementation
1. Real-time notifications
2. Bubble activity feeds
3. Advanced search filters

## 📝 Test Results Summary

**Date:** [Current Date]
**Tester:** [Your Name]
**Environment:** [Browser, OS, Flask version]

### Test Results:
- ✅ Passed: [List]
- ❌ Failed: [List]
- 🔄 Needs Attention: [List]

### Issues Found:
1. [Issue description and solution]

### Recommendations:
1. [Improvement suggestions]

---

**This test guide ensures comprehensive coverage of all connections system functionality. Run these tests after any code changes to maintain system stability.**
