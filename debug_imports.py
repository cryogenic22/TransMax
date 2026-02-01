
import sys
import traceback

print("1. Importing app.models.database...")
try:
    from app.models.database import Document, Segment
    print("   SUCCESS")
except Exception:
    traceback.print_exc()

print("\n2. Importing app.models.models...")
try:
    from app.models.models import TranslationJobQueue
    print("   SUCCESS")
except Exception:
    traceback.print_exc()

print("\n3. Importing app.agents.graph...")
try:
    from app.agents.graph import app as workflow_app
    print("   SUCCESS")
except Exception:
    traceback.print_exc()
