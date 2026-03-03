"""
One-time cleanup script: removes test artifact glossaries (test_gloss_ops_*) and their terms.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.database import SessionLocal
from app.models.models import Glossary, GlossaryTerm

def main():
    session = SessionLocal()
    try:
        # Find test glossaries
        test_glossaries = session.query(Glossary).filter(
            Glossary.glossary_id.like("test_gloss_ops_%")
        ).all()

        if not test_glossaries:
            print("No test glossaries found. Nothing to clean.")
            return

        print(f"Found {len(test_glossaries)} test glossaries to delete:")
        for g in test_glossaries:
            print(f"  - {g.glossary_id} v{g.version}")

        # Delete terms first, then glossaries
        deleted_terms = 0
        for g in test_glossaries:
            count = session.query(GlossaryTerm).filter(
                GlossaryTerm.glossary_id == g.glossary_id,
                GlossaryTerm.glossary_version == g.version,
            ).delete()
            deleted_terms += count
            session.delete(g)

        session.commit()
        print(f"Deleted {len(test_glossaries)} glossaries and {deleted_terms} terms.")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()
