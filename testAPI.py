test_script = """
import os
from google import genai
 
# Get the API key from environment
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    print("ERROR: GEMINI_API_KEY environment variable is not set")
    exit(1)
 
# Set the API key
os.environ['GOOGLE_API_KEY'] = "AIzaSyBd_vwjs4q5BT4Zdg1cl04vuouHpDnz9fI"
 
try:
    # Try to initialize a simple model
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content("Hello, are you working?")
    print("SUCCESS! API Key is valid.")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"ERROR: {str(e)}")
"""

# Write the test script to a file
with open("test_gemini.py", "w") as f:
    f.write(test_script)
 
print("Test script created: test_gemini.py")
print("Run it with: python test_gemini.py")