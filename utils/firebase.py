import os
import requests


def verify_firebase_token(token: str):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={os.environ.get('FIREBASE_API_KEY')}"
    headers = {
        "Content-Type": "application/json"
    }
    body = {
        "idToken": token
    }
    response = requests.post(url, json=body, headers=headers)
    res = response.json()
    return res['users'][0]['email']
