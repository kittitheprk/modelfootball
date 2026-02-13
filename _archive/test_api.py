import requests
import json
import sys

# Key from analyze_match.py
API_KEY = "AIzaSyAIkLd916V-iQua89t3stHYtkwOLBXu8Us"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"

payload = {
    "contents": [{"parts": [{"text": "Hello, are you working?"}]}]
}

try:
    print(f"Testing API Key: {API_KEY[:5]}...{API_KEY[-5:]}")
    response = requests.post(API_URL, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success! Response:")
        print(response.json()['candidates'][0]['content']['parts'][0]['text'])
    else:
        print("Error Response:")
        print(response.text)
        
except Exception as e:
    print(f"Exception: {e}")
