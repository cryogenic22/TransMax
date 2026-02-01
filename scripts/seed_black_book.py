
import sys
import os
import logging
from uuid import uuid4

# Adjust path to find app module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# FORCE LOCAL TEST DB - MUST MATCH VERIFICATION SCRIPT
os.environ["DATABASE_URL"] = "sqlite:///./test_transmax.db"

from app.services.db_service import get_db_service
from app.models.models import TranslationRule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DistilSeed")

def seed_black_book():
    """
    Populates the active_repository (TranslationRule) with trusted Agency Knowledge.
    """
    db = get_db_service().get_session()
    
    # Trusted Rules based on EMA/PMDA/FDA Standards
    SEED_RULES = [
        # 1. EMA (European Medicines Agency) Standards
        {
            "source_pattern": "Patient Information Leaflet",
            "target_correction": "Notice (FR)", 
            "context_tag": "EMA_REGULATORY",
            "explanation": "Standard QRD Template v10 term for 'PIL' in French.",
            "confidence": 1.0
        },
        {
            "source_pattern": "side effects",
            "target_correction": "effets indésirables",
            "context_tag": "EMA_SAFETY",
            "explanation": "Preferred Term. 'Effets secondaires' is deprected in regulatory contexts.",
            "confidence": 1.0
        },
        {
            "source_pattern": "Keep out of the sight and reach of children",
            "target_correction": "Tenir hors de la vue et de la portée des enfants",
            "context_tag": "EMA_MANDATORY",
            "explanation": "Mandatory safety warning phrase (QRD Template).",
            "confidence": 1.0
        },

        # 2. PMDA (Japan) - assuming target context En->Ja logic, but stored for reference
        # (TransMax currently showcasing En->Fr, but we seed structure for Global)
        {
            "source_pattern": "Clinical Study",
            "target_correction": "Etude Clinique", # Keeping French scope for demo
            "context_tag": "ICH_GCP",
            "explanation": "Standard GCP terminology.",
            "confidence": 0.95
        },

        # 3. Dosage & Safety (Universal)
        {
            "source_pattern": "Do not chew",
            "target_correction": "Ne pas croquer",
            "context_tag": "SAFETY_INSTRUCTION",
            "explanation": "Precise medical instruction for solid forms.",
            "confidence": 0.98
        },
        {
            "source_pattern": "infusion",
            "target_correction": "perfusion",
            "context_tag": "MED_TERM",
            "explanation": "Distinction: 'Infusion' (herbal) vs 'Perfusion' (IV).",
            "confidence": 0.99
        },
        
        # 4. Typography / Formatting (French)
        {
            "source_pattern": "%",
            "target_correction": " %",
            "context_tag": "TYPOGRAPHY",
            "explanation": "French requires non-breaking space before percent sign.",
            "confidence": 0.90
        }
    ]

    logger.info("--- Seeding Black Book Knowledge ---")
    
    for rule_data in SEED_RULES:
        # Check if exists (idempotency)
        exists = db.query(TranslationRule).filter(
            TranslationRule.source_pattern == rule_data["source_pattern"],
            TranslationRule.status == "ACTIVE"
        ).first()

        if exists:
            logger.info(f"Skipping existing rule: {rule_data['source_pattern']}")
            continue

        rule = TranslationRule(
            rule_id=str(uuid4()),
            source_pattern=rule_data["source_pattern"],
            target_correction=rule_data["target_correction"],
            context_tag=rule_data["context_tag"],
            confidence_score=rule_data["confidence"],
            status="ACTIVE", # Direct to Active for Seeded Data
            origin_event_id="SEED_INIT_V1"
        )
        db.add(rule)
        logger.info(f"Seeded Rule: {rule_data['source_pattern']} -> {rule_data['target_correction']}")

    try:
        db.commit()
        logger.info("Seeding Complete. Knowledge Graph updated.")
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_black_book()
