
import sys
import os

# Ensure app can be imported
sys.path.append(os.getcwd())

def verify_graph():
    print("--- Verifying TransMax Graph Compilation ---")
    try:
        from app.agents.graph import app
        print("SUCCESS: Graph compiled.")
        
        # Verify node existence
        nodes = app.nodes
        if "reflexion" in nodes:
            print("SUCCESS: 'reflexion' node found in graph.")
        else:
            print("FAILURE: 'reflexion' node missing.")
            return False
            
        return True
    except ImportError as e:
        print(f"FAILURE: ImportError during graph compilation: {e}")
        return False
    except Exception as e:
        print(f"FAILURE: Exception during graph compilation: {e}")
        return False

if __name__ == "__main__":
    if verify_graph():
        sys.exit(0)
    else:
        sys.exit(1)
