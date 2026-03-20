import os
import sys

# Hard requirements — app cannot function without these
REQUIRED_VARS = [
    "OPENAI_API_KEY",
]

# Soft requirements — app will use defaults if missing
OPTIONAL_VARS = [
    "DATABASE_URL",
    "REDIS_URL",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SECRET_KEY",
]

def check_env():
    missing = []
    for var in REQUIRED_VARS:
        if not os.environ.get(var):
            missing.append(var)

    warned = []
    for var in OPTIONAL_VARS:
        if not os.environ.get(var):
            warned.append(var)

    if warned:
        print("WARNING: Optional environment variables not set (defaults will be used):")
        for var in warned:
            print(f"  - {var}")

    if missing:
        print("CRITICAL: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        sys.exit(1)

    print("Environment Config Verified.")

if __name__ == "__main__":
    check_env()
