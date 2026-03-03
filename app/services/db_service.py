from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any, Optional, List
import json
import uuid
import logging
from datetime import datetime

from app.models.database import engine, SessionLocal, Base, Document, DocumentStatus, Segment
from app.models.models import TranslationJobQueue, AuditRecord, Glossary, GlossaryTerm, TMSegment, QualityScorecard
from app.core.constants import SubstitutionType

logger = logging.getLogger(__name__)

class DatabaseService:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        # Determine if we should create tables (auto-migration for prototype)
        # In production this should be handled by Alembic
        try:
            Base.metadata.create_all(bind=engine)
            # Enable pgvector extension if not exists (Postgres only)
            if engine.dialect.name == 'postgresql':
                with engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()
            logger.info("Database initialized successfully.")
        except Exception as e:
            print(f"Warning: DB Initialization failed: {e}")
        
        self._initialized = True

    def get_session(self) -> Session:
        return SessionLocal()


    def create_job(self, request_data: Dict[str, Any]) -> str:
        db = self.get_session()
        try:
            job_id = str(uuid.uuid4())
            job = TranslationJobQueue(
                job_id=job_id,
                request_id=request_data.get("request_id"),
                source_language=request_data.get("source_language"),
                target_language=request_data.get("target_language"),
                domain=request_data.get("domain", "general"),
                audience=request_data.get("audience", "general"),
                request_json=request_data,
                status="PENDING"
            )
            db.add(job)
            db.commit()
            return job_id
        except Exception as e:
            db.rollback()
            print(f"Error creating job: {e}")
            raise e
        finally:
            db.close()

    def get_constraints(self, source_lang: str, target_lang: str, query_text: str = "", glossary_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches glossary terms and TM matches. 
        Uses OpenAIEmbeddings to vector search the TranslationMemory.
        """
        from langchain_openai import OpenAIEmbeddings
        from app.core.config import settings
        
        db = self.get_session()
        constraints = {
            "glossary": [],
            "forbidden_terms": [],
            "tm_matches": []
        }
        
        try:
            # 1. Fetch Glossary
            if glossary_id:
                # Get latest active version
                glossary = db.query(Glossary).filter(
                    Glossary.glossary_id == glossary_id,
                    Glossary.is_active == True
                ).order_by(Glossary.version.desc()).first()
                
                if glossary:
                    terms = db.query(GlossaryTerm).filter(
                        GlossaryTerm.glossary_id == glossary.glossary_id,
                        GlossaryTerm.glossary_version == glossary.version
                    ).all()
                    
                    for term in terms:
                        t_dict = {
                            "term_id": term.term_id,
                            "source": term.source_text,
                            "target": term.target_text,
                            "allowed_variants": term.allowed_variants or [],
                            "reason": "Glossary constraint"
                        }
                        
                        if term.is_forbidden:
                             t_dict["term"] = term.source_text # Forbidden terms are usually source terms to avoid in target, or target terms to block?
                             # Usually Forbidden Terms are "Don't use X word in Target".
                             # So if is_forbidden is True, the 'target_text' might be the forbidden word, or 'source_text' is the word to not translate to X?
                             # Let's assume GlossaryTerm definition: Source=Context, Target=ForbiddenWord.
                             # Or Source=ForbiddenWord.
                             # Let's look at standards. Forbidden list usually: "Do not use 'Drink'". 
                             # If term.is_forbidden, we treat term.target_text (or source if target is empty) as the Forbidden Term in Target.
                             
                             # Let's assume standard: source="Take", target="Drink", is_forbidden=True => "Drink" is forbidden for "Take".
                             # Or just a global blocklist?
                             # For now, let's assume valid target_text is the forbidden string.
                             forbidden_word = term.target_text if term.target_text else term.source_text
                             
                             constraints["forbidden_terms"].append({
                                 "term": forbidden_word,
                                 "severity": "critical",
                                 "reason": "Forbidden by Glossary"
                             })
                        else:
                             constraints["glossary"].append(t_dict)
            
            # 2. Fetch Active Translation Rules (Black Book)
            # TMX-045: These are learned or curated agency rules (not just glossary terms)
            from app.models.models import TranslationRule
            active_rules = db.query(TranslationRule).filter(
                TranslationRule.status == "ACTIVE"
            ).all()

            for rule in active_rules:
                constraints["glossary"].append({
                    "term": rule.source_pattern,
                    "target": rule.target_correction,
                    "reason": f"Agency Rule ({rule.context_tag}): {rule.rule_id}",
                    "confidence": rule.confidence_score
                })
            
            # 2. Fetch TM Matches (Vector Search)
            if query_text and settings.openai_api_key:
                try:
                    embeddings_model = OpenAIEmbeddings(api_key=settings.openai_api_key)
                    query_vec = embeddings_model.embed_query(query_text)
                    
                    # Search using Cosine Distance (<-> operator in pgvector abstract)
                    # We use l2_distance or cosine_distance. SQLAlchemy pgvector helper is l2_distance by default usually
                    # But distinct operator is recommended. Let's use order_by(TMSegment.embedding.l2_distance(query_vec))
                    
                    matches = db.query(TMSegment).filter(
                        TMSegment.source_language == source_lang,
                        TMSegment.target_language == target_lang,
                        TMSegment.embedding.l2_distance(query_vec) < 0.5 # Threshold
                    ).order_by(TMSegment.embedding.l2_distance(query_vec)).limit(3).all()
                    
                    for match in matches:
                        constraints["tm_matches"].append({
                            "source": match.source_text,
                            "target": match.translated_text,
                            "score": 0.9 # Placeholder, actual distance not easily retrievable in ORM without selection
                        })
                except Exception as ve:
                    print(f"Vector search warning: {ve}")
            
            return constraints
            
        except Exception as e:
            print(f"Error fetching constraints: {e}")
            return constraints # Fail safe
        finally:
            db.close()

    def find_best_match(self, source_text: str, source_lang: str, target_lang: str) -> Optional[Dict[str, Any]]:
        """
        Finds the best TM match.
        Priority 1: Exact String Match (Score 1.0)
        Priority 2: High Semantic Similarity (Score > 0.95)
        """
        from app.models.models import TMSegment
        
        db = self.get_session()
        try:
            # 1. Exact Match Check (Strict Hash)
            # Normalization: Lowercase? Strip whitespace? 
            # Regulatory Standard: Exact characters usually required, but whitespace normalization is safe.
            # We keep it simple: Strip leading/trailing.
            import hashlib
            normalized_text = source_text.strip()
            # SHA256 Hash
            content_hash = hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()
            
            # Query by Hash AND Version (Sprint 6)
            exact_match = db.query(TMSegment).filter(
                TMSegment.source_content_hash == content_hash,
                TMSegment.source_language == source_lang,
                TMSegment.target_language == target_lang,
                TMSegment.segmentation_version == "v1", # Hardcoded for now, or config
                TMSegment.normalization_version == "v1"
            ).first()
            
            if exact_match:
                return {
                    "source": exact_match.source_text,
                    "target": exact_match.target_text,
                    "score": 1.0,
                    "type": SubstitutionType.TM_EXACT.value
                }

            # 2. Vector Search (If configured and key exists)
            from app.core.config import settings
            from app.core.constants import SubstitutionType
            
            if settings.openai_api_key:
                try:
                    from langchain_openai import OpenAIEmbeddings
                    embeddings_model = OpenAIEmbeddings(api_key=settings.openai_api_key)
                    # Embed Query
                    query_vec = embeddings_model.embed_query(normalized_text)
                    
                    # Search
                    # Threshold: 0.15 distance (approx 85% similarity for cosine)
                    # Using l2_distance as default proxy or cosine_distance if using explicit operator
                    # pgvector l2_distance: <->
                    # pgvector cosine_distance: <=>
                    # We'll use l2_distance for robustness unless cosine index is explicit.
                    
                    match = db.query(TMSegment).filter(
                        TMSegment.source_language == source_lang,
                        TMSegment.target_language == target_lang,
                        TMSegment.embedding.cosine_distance(query_vec) < 0.1 # Very strict fuzzy (0.9 similarity)
                    ).order_by(TMSegment.embedding.cosine_distance(query_vec)).first()
                    
                    if match:
                         # Calculate similarity score (inverse of distance)
                         # Cosine distance range 0..2. (0=identical).
                         # Simple similarity = 1 - distance
                         dist = 0.0 # How to get distance from query? 
                         # SQLAlchemy doesn't return calculated calc unless selected.
                         # We'll just assume it met threshold.
                         
                         return {
                            "source": match.source_text,
                            "target": match.target_text,
                            "score": 0.9, # Placeholder or calc
                            "type": "TM_FUZZY" 
                         }
                except ImportError:
                    logger.warning("langchain_openai not installed, skipping vector search.")
                except Exception as ve:
                    logger.warning(f"Vector search failed: {ve}")

            return None
            
        except Exception as e:
            print(f"Error finding TM match: {e}")
            return None
        finally:
            db.close()

    def create_glossary(self, glossary_id: str, version: str, meta: Dict[str, Any] = None):
        """Creates a new glossary version."""
        db = self.get_session()
        try:
            glossary = Glossary(
                glossary_id=glossary_id,
                version=version,
                is_active=True,
                meta_json=meta or {}
            )
            db.merge(glossary) # Upsert
            db.commit()
            logger.info(f"Created Glossary {glossary_id} v{version}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating glossary: {e}")
            raise e
        finally:
            db.close()

    def add_glossary_term(self, glossary_id: str, version: str, term_data: Dict[str, Any]):
        """Adds a term to a glossary."""
        db = self.get_session()
        try:
            # Generate ID if missing
            term_id = term_data.get("term_id") or str(uuid.uuid4())
            
            term = GlossaryTerm(
                glossary_id=glossary_id,
                glossary_version=version,
                term_id=term_id,
                source_text=term_data["source_text"],
                target_text=term_data["target_text"],
                is_forbidden=term_data.get("is_forbidden", False),
                allowed_variants=term_data.get("allowed_variants", []),
                metadata_json=term_data.get("metadata", {})
            )
            db.add(term)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error adding glossary term: {e}")
            raise e
        finally:
            db.close()

    def add_tm_segment(self, source: str, target: str, source_lang: str, target_lang: str, tm_id: str = "default") -> str:
        """
        Adds a TM segment with embedding and hash.
        Returns segment_hash.
        """
        import hashlib
        from langchain_openai import OpenAIEmbeddings
        from app.core.config import settings

        db = self.get_session()
        try:
            normalized_source = source.strip()
            content_hash = hashlib.sha256(normalized_source.encode('utf-8')).hexdigest()
            segment_hash = str(uuid.uuid4())
            
            # Generate Embedding
            embedding = None
            if settings.openai_api_key:
                try:
                    embeddings_model = OpenAIEmbeddings(api_key=settings.openai_api_key)
                    embedding = embeddings_model.embed_query(normalized_source)
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for TM: {e}")
            
            tm_segment = TMSegment(
                tm_id=tm_id,
                segment_hash=segment_hash,
                source_content_hash=content_hash,
                source_text=normalized_source,
                target_text=target,
                source_language=source_lang,
                target_language=target_lang,
                embedding=embedding,
                meta_json={"created_by": "system_ops"}
            )
            
            db.merge(tm_segment) # Upsert on segment_hash? No, segment_hash is UUID. content_hash duplications allowed?
            # Ideally verify content_hash uniqueness per language pair in DB. 
            # For now, we allow duplicates (versions) but usually we check.
            
            db.commit()
            return segment_hash
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error adding TM segment: {e}")
            raise e
        finally:
            db.close()

    def save_audit_log(self, job_id: str, state: Dict[str, Any], audit_id: str):

        db = self.get_session()
        try:
            # Update Job
            job = db.query(TranslationJobQueue).filter(TranslationJobQueue.job_id == job_id).first()
            if job:
                job.status = "COMPLETED"
                job.state_json = json.loads(json.dumps(state, default=str)) 
                job.audit_trail_id = audit_id
            
            # Create Audit Record
            # Extract enriched data
            violations = state.get("quality_report", {}).get("violations", [])
            versions = state.get("versions", {"model": "default", "prompts": "v1"})
            refinement_count = state.get("iteration_count", 0)
            
            enrichment_data = {
                "versions": versions,
                "violation_count": len(violations),
                "violations_summary": [v.get('message') for v in violations],
                "refinement_iterations": refinement_count
            }
            
            # TMX-020: Construct Full Payload for Tamper Evidence
            audit_payload = {
                "audit_id": audit_id,
                "job_id": job_id,
                "final_decision": state.get("final_decision", "UNKNOWN"),
                "scores_json": state.get("quality_report", {}),
                "events_json": [enrichment_data],
                "versions": versions,
                "timestamp": str(datetime.utcnow())
            }
            
            # TMX-021: Canonical Serialization & Hashing
            # Use sort_keys=True for deterministic hashing
            full_payload_json = json.dumps(audit_payload, sort_keys=True)
            import hashlib
            hash_sig = hashlib.sha256(full_payload_json.encode()).hexdigest()
            
            audit = AuditRecord(
                audit_id=audit_id,
                job_id=job_id,
                final_decision=state.get("final_decision", "UNKNOWN"),
                scores_json=state.get("quality_report", {}),
                events_json=[enrichment_data],
                
                # Versions
                model_version=versions.get("model"),
                prompt_version=versions.get("prompts"),
                glossary_version=versions.get("glossary", "v1"),
                language_pack_version=versions.get("lang_pack", "v1"),
                policy_version=versions.get("policy", "v1.0"),
                
                # Integrity
                full_payload=json.loads(full_payload_json), # Store as JSON object
                hash_signature=hash_sig
            )
            
            db.add(audit)
            db.commit()
            
        except Exception as e:
            db.rollback()
            print(f"Error saving audit log: {e}")
        finally:
            db.close()

    def verify_audit_integrity(self, audit_id: str) -> Dict[str, bool]:
        """
        TMX-021: Verify cryptographic integrity of an audit record.
        Returns:
            {
                "hash_valid": bool,
                "index_integrity": bool,
                "details": str
            }
        """
        import hashlib
        from app.models.models import AuditRecord
        
        db = self.get_session()
        try:
            record = db.query(AuditRecord).filter(AuditRecord.audit_id == audit_id).first()
            if not record:
                return {"hash_valid": False, "index_integrity": False, "details": "Record not found"}
            
            # 1. Verify Hash Signature
            # Sort keys for canonical representation
            reconstructed_json = json.dumps(record.full_payload, sort_keys=True)
            calculated_hash = hashlib.sha256(reconstructed_json.encode()).hexdigest()
            
            hash_valid = (calculated_hash == record.hash_signature)
            
            # 2. Verify Index Integrity (Anti-Drift)
            # Ensure searchable columns match the signed payload
            payload = record.full_payload
            
            # Check Final Decision
            # Payload field might be missing if older version, handled gracefully?
            # TMX-021 implies strict schema.
            p_decision = payload.get("final_decision")
            index_integrity = True
            details = []
            
            if record.final_decision != p_decision:
                index_integrity = False
                details.append(f"Decision mismatch: DB={record.final_decision}, Payload={p_decision}")
                
            # Check Job ID
            p_job = payload.get("job_id")
            if record.job_id != p_job:
                index_integrity = False
                details.append(f"Job ID mismatch: DB={record.job_id}, Payload={p_job}")
            
            # Check Scores (JSON comparison)
            # Depending on DB, loaded JSON might differ in formatting? 
            # But comparison of dicts should be fine.
            if record.scores_json != payload.get("scores_json"):
                 # Deep compare
                 if json.dumps(record.scores_json, sort_keys=True) != json.dumps(payload.get("scores_json"), sort_keys=True):
                     index_integrity = False
                     details.append("Scores mismatch")

            return {
                "hash_valid": hash_valid,
                "index_integrity": index_integrity,
                "details": "; ".join(details) if details else "Integrity Verified"
            }
            
        except Exception as e:
            logger.error(f"Integrity check failed: {e}")
            return {"hash_valid": False, "index_integrity": False, "details": str(e)}
        finally:
            db.close()

    def process_learning_loop(self, doc_id: str):
        """
        TMX-043: Ingest approved document segments into Translation Memory.
        """
        from app.models.database import Segment, Document
        
        db = self.get_session()
        try:
            # 1. Verify Doc Status (optional, we assume triggered correctly)
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                logger.warning(f"Learning Loop: Doc {doc_id} not found.")
                return

            # 2. Fetch Segments
            segments = db.query(Segment).filter(Segment.document_id == doc_id).all()
            
            count = 0
            for seg in segments:
                if seg.source_text and seg.translated_text:
                    # Ingest
                    # Uses default logic (OpenAI Key check inside add_tm_segment)
                    self.add_tm_segment(
                        seg.source_text, 
                        seg.translated_text, 
                        doc.source_language, 
                        doc.target_language,
                        tm_id="default"
                    )
                    count += 1
            
            logger.info(f"Learning Loop: Ingested {count} segments for Doc {doc_id}")
            
        except Exception as e:
            logger.error(f"Learning Loop Failed: {e}")
        finally:
            db.close()

    def generate_audit_certificate(self, doc_id: str) -> str:
        """
        TMX-022: Generate a text-based Audit Certificate.
        """
        from app.models.database import Document, Segment
        from app.models.models import AuditRecord
        from app.core.config import settings
        
        db = self.get_session()
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                return "Error: Document not found."
            
            # Find associated Job/Audit Logs
            # We assume we can find them via some link? 
            # Or we just dump Segment History?
            # TMX-022 refers to "Audit Trail".
            # Currently `save_audit_log` uses `job_id`.
            # Documents trigger Jobs. But Models might not link Doc -> Job strongly yet?
            # `TranslationJobQueue` (viewed earlier snippet 1637 doesn't show link).
            # But usually we link via Request ID or similar.
            # Let's verify `Document` calls `translate_document`.
            # `translate_document` in `api/documents.py` just queues task.
            
            # Fallback: Certificate of Segments (Change Log) + Doc Metadata
            # Real Audit Record link requires Job ID storage on Doc.
            # We'll export the Document Metadata and Segment History as "Audit Certificate" for now.
            
            lines = [
                "TRANSMAX CERTIFICATE OF TRANSLATION",
                "===================================",
                f"Document ID: {doc.id}",
                f"Filename: {doc.name}",
                f"Date: {datetime.utcnow().isoformat()}",
                f"Source: {doc.source_language} -> Target: {doc.target_language}",
                "",
                "--- SEGMENT AUDIT TRAIL ---"
            ]
            
            segments = db.query(Segment).filter(Segment.document_id == doc.id).order_by(Segment.order_index).all()
            for seg in segments:
                lines.append(f"[{seg.order_index}] {seg.source_text[:50]}... -> {seg.translated_text[:50]}...")
                # We could add ChangeLogs here if we join tables.
            
            lines.append("")
            lines.append("--- END OF CERTIFICATE ---")
            lines.append(f"Generated by TransMax v{settings.app_version}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Certificate generation failed: {e}")
            return f"Error generating certificate: {e}"
        finally:
            db.close()
    def update_segments_batch(self, updates: List[Dict[str, Any]]):
        """
        Updates multiple segments in one transaction.
        Supports partial updates (e.g., only specific columns).
        Required: 'segment_id' in each dict.
        """
        from app.models.database import Segment
        if not updates:
            return
            
        db = self.get_session()
        try:
             # Use iterative update for safety (avoids bulk binding issues on SQLite)
             from app.models.database import Segment, SegmentStatus
             
             for u in updates:
                 seg_id = u.get('segment_id') or u.get('id')
                 if not seg_id: 
                     continue
                     
                 seg = db.query(Segment).filter(Segment.id == seg_id).first()
                 if seg:
                     if 'translated_text' in u:
                         seg.translated_text = u['translated_text']
                     if 'translation_source' in u:
                         seg.translation_source = u['translation_source']
                     if 'match_score' in u:
                         seg.match_score = u['match_score']
                     if 'status' in u:
                         # Handle Enum mapping
                         val = u['status']
                         if isinstance(val, str):
                             try:
                                 seg.status = SegmentStatus(val.lower())
                             except ValueError:
                                 pass
                         else:
                             seg.status = val
                             
                     if 'reverse_translation' in u:
                         seg.reverse_translation = u['reverse_translation']
                         
             db.commit()
             
        except Exception as e:
            logger.error(f"Batch Update Failed: {e}")
            if updates:
               logger.error(f"Sample update keys: {updates[0].keys()}")
            import traceback
            logger.error(traceback.format_exc())
            db.rollback()
            raise e
        finally:
            db.close()

    def log_segment_change(self, segment_id: str, original: str, new: str, reason: str, user_id: str = "system", user_name: str = "SystemUser"):
        """
        TMX-062: Log manual segment changes.
        """
        from app.models.database import ChangeLog, Segment, SegmentStatus
        
        db = self.get_session()
        try:
            # Create Log
            log = ChangeLog(
                segment_id=segment_id,
                original_text=original,
                new_text=new,
                reason=reason,
                user_id=user_id,
                user_name=user_name
            )
            db.add(log)
            # Commit log first
            db.commit()
            
            # Update Segment explicitly? 
            # The API might handle the segment update. 
            # Requirement said "Modify update_segment... call logic".
            # So this method just LOGS. It doesn't update the segment state.
            # But the API updates segment state.
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error logging segment change: {e}")
            # Don't raise, audit failure shouldn't block ops?
            # TMX Policy says Audit is Critical.
            raise e
        finally:
            db.close()

    def save_quality_scorecard(self, job_id: str, scorecard_data: Dict[str, Any], defects: List[Dict[str, Any]]):
        """
        TMX-030: Saves the immutable Quality Scorecard for a job.
        defects: List of serialized Defect dicts.
        """
        from app.models.models import QualityScorecard, ScorecardEntry
        from app.core.defect_taxonomy import DefectSeverity
        
        db = self.get_session()
        try:
            # 1. Calculate Aggregates
            critical_count = sum(1 for d in defects if d['severity'] == DefectSeverity.CRITICAL.value)
            major_count = sum(1 for d in defects if d['severity'] == DefectSeverity.MAJOR.value)
            minor_count = sum(1 for d in defects if d['severity'] == DefectSeverity.MINOR.value)
            
            # 2. Create Scorecard
            scorecard = QualityScorecard(
                scorecard_id=str(uuid.uuid4()),
                job_id=job_id,
                critical_defect_count=critical_count,
                major_defect_count=major_count,
                minor_defect_count=minor_count,
                semantic_drift_score=scorecard_data.get('drift_score'),
                gate_pass_rate=scorecard_data.get('pass_rate'),
                status=scorecard_data.get('status', 'REV_REQ')
            )
            db.add(scorecard)
            
            # 3. Create Entries
            for d in defects:
                entry = ScorecardEntry(
                    entry_id=str(uuid.uuid4()),
                    scorecard_id=scorecard.scorecard_id,
                    segment_id=d.get('segment_id'),
                    category=d.get('category', 'UNKNOWN'),
                    severity=d.get('severity', 'MAJOR'),
                    message=d.get('message', '')
                )
                db.add(entry)
                
            db.commit()
            logger.info(f"Persisted Quality Scorecard for Job {job_id}")
            return scorecard.scorecard_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save scorecard: {e}")
            raise e
        finally:
            db.close()

    def get_document_status(self, doc_id: str) -> str:
        """
        Fetches the current status of a document.
        """
        session = self.get_session()
        try:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                return "UNKNOWN"
            # Handle Enum or String
            return doc.status.value if hasattr(doc.status, "value") else str(doc.status)
        finally:
            session.close()

    def update_document_status(self, doc_id: str, status: str) -> None:
        """
        Updates the status of a document.
        """
        session = self.get_session()
        try:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if doc:
                # Ensure we store the string value
                if hasattr(status, "value"):
                     doc.status = status.value
                else:
                     doc.status = str(status).lower() # Fallback
                
                session.commit()
        except Exception as e:
            logger.error(f"DEBUG: doc_id={doc_id}, status={status}, type={type(status)}")
            import traceback
            logger.error(traceback.format_exc())
            session.rollback()
            logger.error(f"Failed to update document status: {e}")
            raise
        finally:
            session.close()

    def get_segments_for_doc(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Fetches all segments for a document, ordered by index.
        Returns list of dicts suitable for the graph state.
        """
        session = self.get_session()
        try:
            segments = session.query(Segment).filter(Segment.document_id == doc_id).order_by(Segment.order_index).all()
            return [
                {
                    "segment_id": seg.id,
                    "doc_id": seg.document_id,
                    "source_text": seg.source_text,
                    "translated_text": seg.translated_text,
                    "order_index": seg.order_index,
                    "status": seg.status.value if hasattr(seg.status, "value") else str(seg.status) if seg.status else "PENDING",
                    "reverse_translation": seg.reverse_translation
                }
                for seg in segments
            ]
        finally:
            session.close()

    def update_quality_scorecard_metric(self, job_id: str, metric_name: str, value: Any) -> None:
        """
        Updates a specific metric in the Quality Scorecard.
        """
        session = self.get_session()
        try:
            scorecard = session.query(QualityScorecard).filter(QualityScorecard.job_id == job_id).first()
            if scorecard:
                if metric_name == "drift_score":
                    scorecard.semantic_drift_score = value
                    session.commit()
                    logger.info(f"Updated scorecard metric {metric_name} for Job {job_id}")
                else:
                    logger.warning(f"Metric {metric_name} not supported for direct update.")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update scorecard metric: {e}")
            raise
        finally:
            session.close()

_db_service_instance = None

def get_db_service() -> DatabaseService:
    """
    Singleton Accessor for DatabaseService.
    Prevents multiple initializations and circular imports.
    """
    global _db_service_instance
    if not _db_service_instance:
        _db_service_instance = DatabaseService()
    return _db_service_instance
