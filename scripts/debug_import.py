import sys
import os

print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    from app.agents.nodes.reverse_translate import reverse_translate_node
    print("Import Successful!")
except ImportError as e:
    print(f"Import Error: {e}")
except Exception as e:
    print(f"Other Error: {e}")
