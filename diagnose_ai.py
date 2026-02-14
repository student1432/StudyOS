
import os
import sys
from dotenv import load_dotenv

# Force load .env
load_dotenv(override=True)

api_key = os.getenv('GEMINI_API_KEY')
print(f"API Key present: {bool(api_key)}")
if api_key:
    print(f"API Key length: {len(api_key)}")
    print(f"API Key start: {api_key[:4]}")

try:
    from google import genai
    print("google.genai imported successfully")
    
    # Try different initialization methods
    print("\nAttempt 1: Standard Client Init")
    try:
        client = genai.Client(api_key=api_key)
        print("Client initialized")
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents='Hello'
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Attempt 1 Failed: {e}")

    print("\nAttempt 2: Init with explicit http_options")
    try:
        from google.genai import types
        client = genai.Client(
            api_key=api_key,
            http_options={'api_version': 'v1beta'}
        )
        print("Client initialized with v1beta")
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents='Hello'
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Attempt 2 Failed: {e}")

except ImportError:
    print("google-genai not installed")
except Exception as e:
    print(f"General Error: {e}")
