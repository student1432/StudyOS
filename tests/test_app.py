"""
Test suite for StudyOS application
Includes unit tests for security utilities, validation, and routes
"""
import pytest
from flask import session
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.security import PasswordManager, RateLimiter, TokenManager
from utils.validators import (
    user_registration_schema, user_login_schema, goal_schema,
    validate_schema, validate_email
)
from utils.cache import CacheManager, cached
from config import config


# ============================================================================
# SECURITY TESTS
# ============================================================================

class TestPasswordManager:
    """Test suite for PasswordManager"""
    
    def test_password_hashing(self):
        """Test that passwords are properly hashed and verified"""
        password = "TestPassword123!"
        hashed = PasswordManager.hash_password(password)
        
        # Hashed password should be different from plain text
        assert hashed != password
        
        # Same password should verify correctly
        assert PasswordManager.verify_password(password, hashed) is True
        
        # Wrong password should fail
        assert PasswordManager.verify_password("WrongPassword123!", hashed) is False
    
    def test_password_uniqueness(self):
        """Test that same password produces different hashes each time"""
        password = "TestPassword123!"
        hash1 = PasswordManager.hash_password(password)
        hash2 = PasswordManager.hash_password(password)
        
        # Hashes should be different (due to salt)
        assert hash1 != hash2
        
        # But both should verify correctly
        assert PasswordManager.verify_password(password, hash1) is True
        assert PasswordManager.verify_password(password, hash2) is True
    
    def test_password_strength_valid(self):
        """Test strong password validation"""
        valid_passwords = [
            "TestPassword123!",
            "MyP@ssw0rd2024",
            "Str0ng!Pass",
            "C0mpl3x#Pass123"
        ]
        
        for pwd in valid_passwords:
            is_strong, msg = PasswordManager.is_strong_password(pwd)
            assert is_strong is True, f"Password {pwd} should be strong: {msg}"
    
    def test_password_strength_invalid(self):
        """Test weak password detection"""
        weak_passwords = [
            ("short", "at least 8 characters"),
            ("nouppercase123!", "uppercase letter"),
            ("NOLOWERCASE123!", "lowercase letter"),
            ("NoDigits!@#", "digit"),
            ("NoSpecial123", "special character"),
        ]
        
        for pwd, expected_error in weak_passwords:
            is_strong, msg = PasswordManager.is_strong_password(pwd)
            assert is_strong is False
            assert expected_error.lower() in msg.lower()


class TestRateLimiter:
    """Test suite for RateLimiter"""
    
    def test_rate_limiter_allows_initial_requests(self):
        """Test that initial requests are allowed"""
        limiter = RateLimiter()
        identifier = "192.168.1.1"
        
        # First 5 requests should be allowed
        for _ in range(5):
            assert limiter.is_allowed(identifier, max_attempts=5) is True
            limiter.record_attempt(identifier)
    
    def test_rate_limiter_blocks_excess_requests(self):
        """Test that excess requests are blocked"""
        limiter = RateLimiter()
        identifier = "192.168.1.2"
        
        # Record 5 attempts
        for _ in range(5):
            limiter.record_attempt(identifier)
        
        # 6th request should be blocked
        assert limiter.is_allowed(identifier, max_attempts=5) is False
    
    def test_rate_limiter_reset(self):
        """Test that reset clears attempts"""
        limiter = RateLimiter()
        identifier = "192.168.1.3"
        
        # Record some attempts
        for _ in range(5):
            limiter.record_attempt(identifier)
        
        # Should be blocked
        assert limiter.is_allowed(identifier, max_attempts=5) is False
        
        # Reset
        limiter.reset_attempts(identifier)
        
        # Should be allowed again
        assert limiter.is_allowed(identifier, max_attempts=5) is True


class TestTokenManager:
    """Test suite for TokenManager"""
    
    def test_generate_secure_token(self):
        """Test secure token generation"""
        token1 = TokenManager.generate_secure_token()
        token2 = TokenManager.generate_secure_token()
        
        # Tokens should be unique
        assert token1 != token2
        
        # Tokens should be non-empty strings
        assert isinstance(token1, str)
        assert len(token1) > 0
    
    def test_generate_csrf_token(self):
        """Test CSRF token generation"""
        token = TokenManager.generate_csrf_token()
        
        # Should be a hex string
        assert isinstance(token, str)
        assert len(token) == 32  # 16 bytes = 32 hex characters


# ============================================================================
# VALIDATION TESTS
# ============================================================================

class TestUserRegistrationSchema:
    """Test suite for user registration validation"""
    
    def test_valid_registration_data(self):
        """Test valid registration data"""
        data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'password': 'TestPassword123!',
            'purpose': 'high_school'
        }
        
        is_valid, result = validate_schema(user_registration_schema, data)
        assert is_valid is True
        assert result['email'] == 'john@example.com'
    
    def test_invalid_email(self):
        """Test invalid email validation"""
        data = {
            'name': 'John Doe',
            'email': 'invalid-email',
            'password': 'TestPassword123!',
            'purpose': 'high_school'
        }
        
        is_valid, errors = validate_schema(user_registration_schema, data)
        assert is_valid is False
        assert 'email' in errors
    
    def test_missing_required_fields(self):
        """Test missing required fields"""
        data = {
            'name': 'John Doe'
        }
        
        is_valid, errors = validate_schema(user_registration_schema, data)
        assert is_valid is False
        assert 'email' in errors
        assert 'password' in errors
        assert 'purpose' in errors
    
    def test_weak_password(self):
        """Test weak password rejection"""
        data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'password': 'weak',
            'purpose': 'high_school'
        }
        
        is_valid, errors = validate_schema(user_registration_schema, data)
        assert is_valid is False
        assert 'password' in errors


class TestUserLoginSchema:
    """Test suite for user login validation"""
    
    def test_valid_login_data(self):
        """Test valid login data"""
        data = {
            'email': 'john@example.com',
            'password': 'anypassword123'
        }
        
        is_valid, result = validate_schema(user_login_schema, data)
        assert is_valid is True
    
    def test_missing_password(self):
        """Test missing password"""
        data = {
            'email': 'john@example.com'
        }
        
        is_valid, errors = validate_schema(user_login_schema, data)
        assert is_valid is False
        assert 'password' in errors


class TestGoalSchema:
    """Test suite for goal validation"""
    
    def test_valid_goal(self):
        """Test valid goal data"""
        data = {
            'title': 'Complete Math Chapter 1',
            'description': 'Study all topics',
            'target_date': '2024-12-31',
            'priority': 'high'
        }
        
        is_valid, result = validate_schema(goal_schema, data)
        assert is_valid is True
    
    def test_invalid_priority(self):
        """Test invalid priority value"""
        data = {
            'title': 'Test Goal',
            'target_date': '2024-12-31',
            'priority': 'invalid'
        }
        
        is_valid, errors = validate_schema(goal_schema, data)
        assert is_valid is False
        assert 'priority' in errors


# ============================================================================
# UTILITY TESTS
# ============================================================================

class TestEmailValidation:
    """Test suite for email validation"""
    
    def test_valid_emails(self):
        """Test valid email addresses"""
        valid_emails = [
            'user@example.com',
            'user.name@example.co.uk',
            'user+tag@example.com',
            'first.last@example.org',
            'user123@example.net'
        ]
        
        for email in valid_emails:
            assert validate_email(email) is True, f"{email} should be valid"
    
    def test_invalid_emails(self):
        """Test invalid email addresses"""
        invalid_emails = [
            'invalid-email',
            '@example.com',
            'user@',
            'user@.com',
            'user name@example.com',
            ''
        ]
        
        for email in invalid_emails:
            assert validate_email(email) is False, f"{email} should be invalid"


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

class TestConfiguration:
    """Test suite for configuration"""
    
    def test_development_config(self):
        """Test development configuration"""
        dev_config = config['development']
        assert dev_config.DEBUG is True
        assert dev_config.SESSION_COOKIE_SECURE is False
    
    def test_production_config(self):
        """Test production configuration"""
        prod_config = config['production']
        assert prod_config.DEBUG is False
        assert prod_config.SESSION_COOKIE_SECURE is True
    
    def test_testing_config(self):
        """Test testing configuration"""
        test_config = config['testing']
        assert test_config.TESTING is True
        assert test_config.DEBUG is True


# ============================================================================
# INTEGRATION TESTS (Flask App)
# ============================================================================

@pytest.fixture
def app():
    """Create application for testing"""
    # Import app here to avoid circular imports
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.config['SECRET_KEY'] = 'test-secret-key'
    flask_app.app.config['WTF_CSRF_ENABLED'] = False
    return flask_app.app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


class TestFlaskRoutes:
    """Test suite for Flask routes"""
    
    def test_index_loads(self, client):
        """Test index loads landing page when not logged in"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'SCLERA' in response.data

    def test_index_redirects_when_logged_in(self, client):
        """Test index redirects to dashboard when logged in"""
        with client.session_transaction() as sess:
            sess['uid'] = 'test-uid'
            sess['account_type'] = 'student'
        response = client.get('/')
        assert response.status_code == 302
        assert '/dashboard' in response.location

    def test_auth_choice_page_loads(self, client):
        """Test auth choice page loads correctly"""
        response = client.get('/auth-choice')
        assert response.status_code == 200
        assert b'Choose Your Role' in response.data
    
    def test_signup_page_loads(self, client):
        """Test signup page loads correctly"""
        response = client.get('/signup')
        assert response.status_code == 200
        assert b'Sign Up' in response.data or b'signup' in response.data.lower()
    
    def test_login_page_loads(self, client):
        """Test login page loads correctly"""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Login' in response.data or b'login' in response.data.lower()
    
    def test_protected_routes_redirect(self, client):
        """Test that protected routes redirect when not logged in"""
        protected_routes = [
            '/dashboard',
            '/profile',
            '/academic',
            '/study-mode',
            '/goals',
            '/tasks'
        ]
        
        for route in protected_routes:
            response = client.get(route, follow_redirects=False)
            assert response.status_code == 302, f"Route {route} should redirect"
            assert '/login' in response.location, f"Route {route} should redirect to login"


# ============================================================================
# CACHE TESTS
# ============================================================================

class TestCacheManager:
    """Test suite for cache functionality"""
    
    def test_cache_set_get(self):
        """Test cache set and get operations"""
        key = "test_key"
        value = {"data": "test_value"}
        
        # Set value
        assert CacheManager.set(key, value) is True
        
        # Get value
        cached_value = CacheManager.get(key)
        assert cached_value == value
    
    def test_cache_delete(self):
        """Test cache delete operation"""
        key = "test_delete_key"
        value = "test_value"
        
        # Set and verify
        CacheManager.set(key, value)
        assert CacheManager.get(key) == value
        
        # Delete and verify
        assert CacheManager.delete(key) is True
        assert CacheManager.get(key) is None
    
    def test_cache_key_generation(self):
        """Test cache key generation"""
        key1 = CacheManager.generate_key("arg1", "arg2", kwarg1="value1")
        key2 = CacheManager.generate_key("arg1", "arg2", kwarg1="value1")
        key3 = CacheManager.generate_key("arg1", "arg3", kwarg1="value1")
        
        # Same args should produce same key
        assert key1 == key2
        # Different args should produce different key
        assert key1 != key3


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
