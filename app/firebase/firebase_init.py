import firebase_admin
from firebase_admin import credentials
import os

_app = None

def get_firebase_app():
    global _app
    if _app is None:
        cred_path = os.path.join(os.path.dirname(__file__), 
                    "allo-tiak-tiak-770c6-firebase-adminsdk-fbsvc-0f3e7e7229.json")
        cred = credentials.Certificate(cred_path)
        _app = firebase_admin.initialize_app(cred)
    return _app