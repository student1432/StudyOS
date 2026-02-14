import os
from dotenv import load_dotenv
 
# Load environment variables from .env file
load_dotenv()
 
# Import the package
import google.generativeai as genai
 
# Get the API key from environment
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    print("ERROR: GEMINI_API_KEY not found in environment variables")
    exit(1)
 
# Configure the API key
genai.configure(api_key=api_key.strip())
 
try:
    # List available models
    print("Available models:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name} (supports generateContent)")
 
    # Try to generate content
    print("\\nGenerating response...")
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content("Hello, are you working?")
    
    print("\\nSUCCESS! API Key is valid.")
    print("Response:", response.text)
    
except Exception as e:
    print(f"\\nERROR: {str(e)}")
    print("\\nTroubleshooting steps:")
    print("1. Make sure you have the package: pip install google-generativeai")
    print("2. Check the API documentation: https://ai.google.dev/api/rest/v1/models/generateContent")