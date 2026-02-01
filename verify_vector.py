import os
import sys

# Add project root to python path
sys.path.append(os.getcwd())

from app.services.db_service import DatabaseService

def test_vector_integration():
    print("Initializing Database Service...")
    service = DatabaseService()
    
    print("Running Vector Search Check (Live OpenAI Call)...")
    # This acts as a smoke test for:
    # 1. DB Connection
    # 2. pgvector extension existence
    # 3. OpenAI API Key validity (Embedding)
    # 4. Parsing logic
    
    constraints = service.get_constraints(
        source_lang="en", 
        target_lang="es", 
        query_text="The patient needs 10mg of medication."
    )
    
    print("Success! Constraints fetched:")
    print(constraints)
    
    if "tm_matches" in constraints:
        print(f"TM Matches Found: {len(constraints['tm_matches'])}")
    else:
        print("Error: tm_matches key missing")


if __name__ == "__main__":
    test_vector_integration()
