import os
import sys

REQUIRED_VARS = [
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "REDIS_URL"
]

def check_env():
    missing = []
    for var in REQUIRED_VARS:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        print("CRITICAL: Missing environment variables:")
        for var in missing:
            print(f"  - {var}")
        sys.exit(1)
        
    print("Environment Config Verified.")

if __name__ == "__main__":
    check_env()
