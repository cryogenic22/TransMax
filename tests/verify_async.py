import requests
import time
import sys

def verify_async_translate():
    url = "http://127.0.0.1:8000/api/v1/translate"
    payload = {
        "content": "Hello world",
        "source_language": "en",
        "target_language": "es"
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload)
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"Request took {duration:.4f} seconds")
        
        if response.status_code != 200:
            print(f"FAILED: Status code {response.status_code}")
            print(response.text)
            sys.exit(1)
            
        data = response.json()
        print(f"Response: {data}")
        
        if data.get("decision") == "PENDING" and data.get("job_id"):
            print("SUCCESS: Endpoint returned PENDING and job_id")
        else:
            print("FAILED: Did not return PENDING or job_id missing")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_async_translate()
