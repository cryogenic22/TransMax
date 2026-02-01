
import requests
import json

url = "http://localhost:8078/api/documents"
files = {'file': ('test_doc.txt', 'This is a test document content for upload verification.', 'text/plain')}
data = {'source_language': 'en', 'target_language': 'fr'}

try:
    print("Attempting upload...")
    response = requests.post(url, files=files, data=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Failed: {e}")
