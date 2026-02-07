import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
import json

# Try to load from file first, then from environment variable
if os.path.exists('serviceAccountKey.json'):
    cred = credentials.Certificate('serviceAccountKey.json')
else:
    # Load from environment variable
    firebase_creds = os.environ.get('FIREBASE_CREDENTIALS')
    if firebase_creds:
        cred_dict = json.loads(firebase_creds)
        cred = credentials.Certificate(cred_dict)
    else:
        raise FileNotFoundError("Firebase credentials not found!")

firebase_admin.initialize_app(cred)
auth = auth 
db = firestore.client()