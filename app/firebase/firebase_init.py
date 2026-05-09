import firebase_admin
from firebase_admin import credentials
import os
import json

_app = None

def get_firebase_app():
    global _app
    if _app is None:
        firebase_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if firebase_json:
            cred_dict = json.loads(firebase_json)
            cred = credentials.Certificate(cred_dict)
        else:
            # Fallback local dev : fichier JSON
            cred_path = os.path.join(os.path.dirname(__file__),
                        "allo-tiak-tiak-770c6-firebase-adminsdk-fbsvc-0f3e7e7229.json")
            cred = credentials.Certificate(cred_path)
        _app = firebase_admin.initialize_app(cred)
    return _app