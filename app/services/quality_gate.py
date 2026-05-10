
import threading
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from app.core.defect_taxonomy import TaxonomyService, Defect, DefectSeverity, DefectCategory
import re

class QualityGateService:
    """
    Deterministically checks segments against constraints.
    Returns list of Defect objects (v3.0) serialized as dicts.

    Thread-safety (TMX-3053 / audit C-08): both the singleton ``__new__`` /
    ``__init__`` guards and the lazy ``_lang_packs`` cache are protected by
    ``_singleton_lock`` (class-level) and ``_lang_pack_lock`` (instance-level).
    The classic double-checked-locking pattern is used: a fast no-lock check
    on the hot path, then re-check under the lock before doing the work.
    """
    _instance = None
    _initialized = False
    _singleton_lock = threading.Lock()

    def __new__(cls):
        # Double-checked locking: fast path avoids contending the lock once
        # the singleton is constructed; slow path holds the lock to guarantee
        # exactly-one allocation under concurrent first-touch.
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super(QualityGateService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Same double-checked-locking shape for the init body. Without the
        # lock, two threads can both observe `_initialized=False`, both run
        # the body, and a partially-initialised instance can leak to the
        # second thread's caller.
        if self._initialized:
            return
        with type(self)._singleton_lock:
            if self._initialized:
                return
            self._populate_initial_state()
            self._initialized = True

    def _populate_initial_state(self) -> None:
        """
        Initialise instance state. Extracted as a hookable method so
        thread-safety tests can count exactly-once invocation without
        having to patch ``__init__`` (which would destroy the guard the
        test is meant to verify).
        """
        self._lang_pack_lock = threading.Lock()
        self._lang_packs = {}
    
    def calculate_semantic_drift(self, source_text: str, back_translation: str) -> float:
        """
        Calculates semantic similarity between Source and Back-Translation.
        Returns a score 0-100 (100 = Identical Meaning).
        Uses OpenAI Embeddings (Cosine Similarity).
        """
        from langchain_openai import OpenAIEmbeddings
        from app.core.config import settings
        import numpy as np
        
        if not settings.openai_api_key:
            return 0.0
            
        try:
            embeddings_model = OpenAIEmbeddings(api_key=settings.openai_api_key)
            # Embed both
            # TODO: Batch this? For now, simple pair.
            vecs = embeddings_model.embed_documents([source_text, back_translation])
            v1 = np.array(vecs[0])
            v2 = np.array(vecs[1])
            
            # Cosine Similarity
            dot = np.dot(v1, v2)
            norm_a = np.linalg.norm(v1)
            norm_b = np.linalg.norm(v2)
            similarity = dot / (norm_a * norm_b)
            
            # Convert to 0-100 score
            # Score = Similarity * 100
            score = max(0.0, min(100.0, similarity * 100))
            return float(score)
            
        except Exception as e:
            print(f"Drift Calc Failed: {e}")
            return 0.0

    def check_segment(self, source_text: str, target_text: str, constraints: Dict[str, Any], target_lang: str, source_lang: str = "en", profile_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Runs all deterministic checks and returns a list of violation dicts (serialized Defects).
        Accepts source_lang for source-side language pack validation.
        """
        defects: List[Defect] = []

        # --- Source-side Language Pack Checks ---
        source_pack = self._lang_packs.get(source_lang)
        if not source_pack and source_lang != "en":
            source_pack = self._load_lang_pack(source_lang)

        # --- Language Pack Integration (TMX-033) ---
        lang_pack = self._lang_packs.get(target_lang)
        
        if not lang_pack:
            lang_pack = self._load_lang_pack(target_lang)
            
        if lang_pack:
            # Specialized Language Checks
            pack_violations = []
            pack_violations.extend(lang_pack.check_negation(source_text, target_text))
            pack_violations.extend(lang_pack.check_numbers(source_text, target_text))
            pack_violations.extend(lang_pack.check_punctuation(target_text))
            pack_violations.extend(lang_pack.check_variants(target_text))
            
            # Map pack violations to Defect objects
            for v in pack_violations:
                v_type = v.get('type')
                cat = DefectCategory.FORMATTING # Default
                
                if v_type == "negation_flip": 
                    cat = DefectCategory.NEGATION_FLIP
                elif v_type == "number_mismatch": 
                    cat = DefectCategory.NUMERIC_MISMATCH
                elif v_type == "punctuation_mismatch" or v_type == "cjk_punctuation": 
                    cat = DefectCategory.FORMATTING
                elif v_type == "variant_improper": 
                    cat = DefectCategory.TERMINOLOGY
                
                defects.append(self._create_defect(cat, v.get('message')))
        
        else:
            # --- Fallback / Default Generic Checks ---
            
            # 1. Unit Verification (Critical)
            if "mg" in source_text and "mg" not in target_text:
                 defects.append(self._create_defect(
                     DefectCategory.UNIT_MISMATCH, 
                     f"Unit mismatch: 'mg' missing in target."
                 ))
            
            # 4. GCHK-006: Ghost-Number Check (Critical)
            # Replaces simple heuristic with strict set counting
            # Count of numeric tokens in source must match target (unless DNT exception)
            
            # Simple Strict Tokenizer for Critical Numbers
            # Matches integers and decimals: 10, 5.5, 0.5
            num_pattern = r'\b\d+(?:[\.,]\d+)?\b'
            
            src_nums = re.findall(num_pattern, source_text)
            tgt_nums = re.findall(num_pattern, target_text)
            
            # Convert to sets for "presence" check (GCHK-006 says "count" but presence is distinct check)
            # GCHK-006 Spec: "Integer count differs... indicative of dropped numbers"
            # We check if every number in Source exists in Target.
            
            missing_nums = []
            for num in src_nums:
                # Normalize num for search (dot vs comma)
                norm_num_regex = re.escape(num).replace(r'\.', r'[.,]')
                if not re.search(rf"\b{norm_num_regex}\b", target_text):
                    missing_nums.append(num)
            
            if missing_nums:
                 defects.append(self._create_defect(
                     DefectCategory.NUMERIC_MISMATCH,
                     f"[GCHK-006] Ghost Number / Omission: Critical numbers missing in target: {missing_nums}"
                 ))

        # --- Structure Checks (TMX-035) ---
        table_defects = self.check_tables(source_text, target_text)
        defects.extend(table_defects)


        # --- Universal Checks (Run for all languages) ---
        
        # 2. Glossary Check (Major)
        glossary_terms = constraints.get('glossary', [])
        for term in glossary_terms:
            src = term.get('source_text') or term.get('source')
            tgt = term.get('target_text') or term.get('target')
            if src and tgt and src in source_text and tgt not in target_text:
                defects.append(self._create_defect(
                    DefectCategory.TERMINOLOGY,
                    f"Glossary term missing: '{src}' -> '{tgt}'"
                ))
        
        # 2b. Forbidden Terms Check (Critical)
        forbidden_terms = constraints.get('forbidden_terms', [])
        for ft in forbidden_terms:
            forbidden_word = ft.get('term', '')
            if forbidden_word and forbidden_word.lower() in target_text.lower():
                defects.append(self._create_defect(
                    DefectCategory.TERMINOLOGY,
                    f"Forbidden term detected in translation: '{forbidden_word}'"
                ))

        # 3. PII Check (Major/Critical) - Fail-Safe Integrity
        # Check 1: Unresolved Tokens
        if "[[PII" in target_text or "<EMAIL" in target_text or "<PHONE" in target_text: 
             defects.append(self._create_defect(
                 DefectCategory.PII_LEAK,
                 "Integrity: Unresolved PII redaction token found."
             ))
             
        # Check 2: Raw PII Leakage (Using Privacy Shield Logic)
        from app.services.pii_service import default_pii_service
        # We run the mask logic on TARGET text. If it finds anything, it means PII leaked.
        _, leaked_pii = default_pii_service.mask(target_text)
        if leaked_pii:
            # We found patterns that look like sensitive data
            # Filter out potential false positives? 
            # For strict safety, we flag it.
            leaked_types = set([item['type'] for item in leaked_pii])
            defects.append(self._create_defect(
                DefectCategory.PII_LEAK,
                f"Privacy Shield: Potential PII leakage detected in target: {leaked_types}"
            ))

        # 4. Symbol & Unit Integrity (TMX-036 Universal)
        defects.extend(self.check_unit_integrity(source_text, target_text))

        # 5. Complexity Soft-Mark (User Request)
        # Identifies segments with formulas, heavy markup using LaTeX or table pipes
        complexity_defect = self.check_complexity(source_text)
        if complexity_defect:
            defects.append(complexity_defect)

        # --- Analytical Archetype Checks (REQ-RES) ---
        # Note: In Sprint 1 we implemented ProfileResolver. In full implementation, 
        # 'constraints' dict would contain 'archetype' key or we read from JobProfile.
        # For now, we allow explicit 'check_analytical_anchors' flag or deduce from constraints.
        
        # 6. Placeholder Integrity (Universal)
        defects.extend(self.check_placeholders(source_text, target_text))

        # 7. Frequency Gate (Pharma abbreviation matching)
        defects.extend(self.check_frequency(source_text, target_text))

        # 8. Regulatory Profile Checks (if profile_id is provided)
        if profile_id:
            defects.extend(self.check_date_formatting(target_text, profile_id))
            defects.extend(self.check_mandatory_headers(target_text, profile_id))

        if constraints.get('archetype') == 'ANALYTICAL' or constraints.get('check_analytical_anchors'):
             from app.services.analytical_check import AnalyticalCheckService
             analytical_service = AnalyticalCheckService()
             
             # REQ-RES-01: Scale Anchors
             defects.extend(analytical_service.check_anchors(source_text, target_text, target_lang))
             
             # REQ-RES-02: Sentiment Drift
             defects.extend(analytical_service.check_sentiment(source_text, target_text, target_lang))

        # Serialize for graph state (StateGraph expects dicts)
        return [
            {
                "category": d.category.value,
                "severity": d.severity.value,
                "message": d.message,
                "segment_id": d.segment_id
            }
            for d in defects
        ]

    def check_complexity(self, source: str) -> Optional[Defect]:
        """
        Soft-mark high complexity segments for human review.
        Triggers if:
        - Latex math ($...$, \[...\])
        - Heavy HTML/XML tags (> 3 tags)
        - Complex Markdown tables (> 2 columns)
        """
        # 1. LaTeX Math
        if re.search(r'(\$|\\\[|\\\(|\\begin\{equation\})', source):
            return self._create_defect(
                DefectCategory.COMPLEXITY_WARNING,
                "Complexity: LaTeX/Math formula detected. Soft mark for human review."
            )
            
        # 2. Complex Tables (Visual check done in check_tables, this is for review trigger)
        # If it has pipes but didn't fail strict table structure, we might still want review if it's large
        if source.count('|') > 4:
            return self._create_defect(
                DefectCategory.COMPLEXITY_WARNING,
                "Complexity: Complex table structure detected. Soft mark for human review."
            )

        # 3. Code Blocks
        if "```" in source:
             return self._create_defect(
                DefectCategory.COMPLEXITY_WARNING,
                "Complexity: Code block detected. Soft mark for human review."
            )

        return None

    def check_unit_integrity(self, source: str, target: str) -> List[Defect]:
        """
        TMX-036: Universal check for scientific symbols and units.
        Ensures preservation of:
        - Symbols: ° (degree), % (percent), <, >, ≤, ≥
        - Units: mg, g, kg, mcg, µg, ml, L, mol
        """
        defects = []
        
        # 1. Critical Symbols
        symbols = ['°', '%', '‰', '§', '<', '>', '≤', '≥', '±']
        for sym in symbols:
            # Count occurrences
            if source.count(sym) > target.count(sym):
                 defects.append(self._create_defect(
                     DefectCategory.FORMATTING,
                     f"Critical Symbol Missing: '{sym}' found in source ({source.count(sym)}) but missing/reduced in target ({target.count(sym)})."
                 ))
        
        # 2. Dosage Unit Integrity (Regex)
        # Matches number + optional space + unit (word boundary)
        # e.g. 5 mg, 5mg, 5.5ml
        unit_pattern = r'(\d+(?:[\.,]\d+)?)\s*(mg|g|kg|mcg|µg|ml|L|mol|mmol)\b'
        
        source_units = re.findall(unit_pattern, source, re.IGNORECASE)
        # source_units is list of tuples: [('5', 'mg'), ('25', 'g')]
        
        # Normalize target for search
        target_lower = target.lower()
        
        for val, unit in source_units:
            # Construct a loose regex to find this specific value+unit pair in target
            # Try to match the exact pair
            # We allow flexible spacing and flexible separator (. or ,)
            # But the unit text must be present.
            
            # Simple check: Is the unit present at all?
            # Better check: Is the value+unit pair present?
            
            # Note: 5mg -> 5 mg is OK. 5mg -> 5g is NOT.
            
            # Search for the value (allowing . <-> , swap)
            val_regex = re.escape(val).replace(r'\.', r'[.,]')
            unit_regex = re.escape(unit)
            
            # Pattern: value + optional space + unit
            full_pattern = rf"{val_regex}\s*{unit_regex}"
            
            if not re.search(full_pattern, target_lower):
                 # Fallback: maybe value matches but unit changed?
                 # If we find value but not unit, it's a unit mismatch.
                 # If we find neither, it's likely omitted (Numeric Mismatch covers this separately).
                 # We focus on Unit Mismatch here.
                 
                 # Check if value exists near a DIFFERENT unit? (Hard to do reliability without NLP)
                 
                 # Conservative check: Just look for the pair.
                 defects.append(self._create_defect(
                     DefectCategory.UNIT_MISMATCH,
                     f"Dosage Integrity/Unit Mismatch: '{val}{unit}' not found exactly in target."
                 ))

        return defects



    def evaluate_verdict(self, violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        The Iron Gavel (Epic 1).
        Deterministically decides the Job Status based on violation counts.
        """
        critical_count = sum(1 for v in violations if v['severity'] == DefectSeverity.CRITICAL.value)
        major_count = sum(1 for v in violations if v['severity'] == DefectSeverity.MAJOR.value)
        minor_count = sum(1 for v in violations if v['severity'] == DefectSeverity.MINOR.value)
        
        status = "PASS"
        reason = "Quality Standards Met"
        
        if critical_count > 0:
            status = "BLOCKED"
            reason = f"Blocking: {critical_count} Critical Safety Defects detected."
        elif major_count > 0:
            status = "REVIEW_REQUIRED"
            reason = f"Review: {major_count} Major Defects detected."
        
        return {
            "status": status,
            "reason": reason,
            "metrics": {
                "critical": critical_count,
                "major": major_count,
                "minor": minor_count
            }
        }

    def compare_scorecards(self, old_metrics: Dict[str, int], new_metrics: Dict[str, int]) -> str:
        """
        The Safety Net (Epic 2).
        Returns 'IMPROVED', 'DEGRADED', or 'NEUTRAL'.
        Rule: If Critical/Major increases, it is DEGRADED (Safety Regression).
        """
        if new_metrics['critical'] > old_metrics['critical']:
            return "DEGRADED"
        if new_metrics['major'] > old_metrics['major']:
            return "DEGRADED"
            
        if new_metrics['critical'] < old_metrics['critical']:
            return "IMPROVED"
        if new_metrics['major'] < old_metrics['major']:
            return "IMPROVED"
        if new_metrics['minor'] < old_metrics['minor']:
            return "IMPROVED"
            
        return "NEUTRAL"
    
    def _load_lang_pack(self, lang_code: str):
        """
        Load and cache a language pack by language code.

        Thread-safety (TMX-3053 / audit C-08): the lazy cache write is
        protected by ``_lang_pack_lock`` using double-checked locking. The
        fast path is a lock-free dict read (CPython dict reads of a single
        key are atomic under the GIL); the slow path serialises load work
        so two threads never both call ``LanguagePackFactory.get_pack`` for
        the same language.
        """
        cached = self._lang_packs.get(lang_code)
        if cached is not None:
            return cached

        with self._lang_pack_lock:
            cached = self._lang_packs.get(lang_code)
            if cached is not None:
                return cached

            pack = None
            try:
                from app.services.language_packs.factory import LanguagePackFactory
                pack = LanguagePackFactory.get_pack(lang_code)
            except Exception:
                # Fallback to known packs
                if lang_code == 'ja':
                    from app.services.language_packs.japanese import JapanesePack
                    pack = JapanesePack()
                elif lang_code == 'ar':
                    from app.services.language_packs.arabic import ArabicPack
                    pack = ArabicPack()

            if pack:
                self._lang_packs[lang_code] = pack
            return pack

    def _create_defect(self, category: DefectCategory, message: str) -> Defect:
        """Helper to create rated defect"""
        # Auto-classify severity based on rules/message if needed, or use category default
        # For now, we use the Service to confirm severity
        severity = TaxonomyService.classify_violation(category.value, message)
        return Defect(category=category, severity=severity, message=message)

    def can_finalize(self, job_id: str) -> bool:
        """
        TMX-GOV-02: Governance Gate.
        Returns True if the job is allowed to transition to FINALIZED/APPROVED.
        Blocks if Safety Critical defects exist or Review is pending without Ack.
        """
        from app.services.db_service import DatabaseService
        from app.models.models import QualityScorecard, AuditRecord, AuditLogEntry
        
        db = DatabaseService()
        session = db.get_session()
        try:
            # 1. Check Scorecard Status
            scorecard = session.query(QualityScorecard).filter_by(job_id=job_id).first()
            if not scorecard:
                # No scorecard? Conservative block.
                return False
                
            if scorecard.status == "BLOCKED":
                return False # Critical Defects must be fixed (iteration required)
                
            if scorecard.status == "REVIEW_REQUIRED":
                # 2. Check for Reviewer Acknowledgement in Audit Chain
                # Find Audit Trail for this job
                audit_record = session.query(AuditRecord).filter_by(job_id=job_id).first()
                if not audit_record:
                    return False
                    
                # Look for REVIEW_ACKNOWLEDGED event
                # We check AuditLogEntry for this audit_id
                ack_event = session.query(AuditLogEntry).filter_by(
                    audit_id=audit_record.audit_id,
                    event_type="REVIEW_ACKNOWLEDGED"
                ).first()
                
                if ack_event:
                    # Review exists -> Allowed
                    return True
                else:
                    # Review pending -> Block
                    return False
            
            # PASS status -> Allowed
            return True
            
        except Exception as e:
            print(f"Governance Check Failed: {e}")
            return False
        finally:
            session.close()

    def check_tables(self, source_text: str, target_text: str) -> List[Defect]:
        """
        TMX-035: Markdown Table Structure Preservation.
        """
        def count_tables(text):
            lines = text.strip().split('\n')
            count = 0
            in_table = False
            for line in lines:
                if line.strip().startswith('|'):
                    if not in_table:
                        count += 1
                        in_table = True
                else:
                    in_table = False
            return count

        def get_table_structure(text):
            structures = []
            lines = text.strip().split('\n')
            current_rows = 0
            current_cols = []
            in_table = False
            
            for line in lines:
                if line.strip().startswith('|'):
                    in_table = True
                    current_rows += 1
                    cols = line.count('|') - 1
                    if cols > 0:
                        current_cols.append(cols)
                else:
                    if in_table:
                        structures.append({'rows': current_rows, 'cols': current_cols})
                        current_rows = 0
                        current_cols = []
                        in_table = False
            
            if in_table:
                 structures.append({'rows': current_rows, 'cols': current_cols})
            return structures

        defects = []
        
        # 1. Table Count
        src_tables = count_tables(source_text)
        tgt_tables = count_tables(target_text)
        
        if src_tables != tgt_tables:
            defects.append(self._create_defect(
                DefectCategory.TABLE_CORRUPTION,
                f"Table count mismatch: Source has {src_tables}, Target has {tgt_tables}."
            ))
            return defects 
            
        if src_tables == 0:
            return []

        # 2. Structure Detail
        src_struct = get_table_structure(source_text)
        tgt_struct = get_table_structure(target_text)
        
        for i, (s, t) in enumerate(zip(src_struct, tgt_struct)):
            if s['rows'] != t['rows']:
                 defects.append(self._create_defect(
                    DefectCategory.TABLE_CORRUPTION,
                    f"Table {i+1} Row Mismatch: {s['rows']} vs {t['rows']}."
                ))
            elif s['cols'] and t['cols'] and s['cols'][0] != t['cols'][0]:
                 defects.append(self._create_defect(
                    DefectCategory.TABLE_CORRUPTION,
                    f"Table {i+1} Column Structure Mismatch (Header): {s['cols'][0]} vs {t['cols'][0]}."
                ))
                
        return defects

    def check_placeholders(self, source_text: str, target_text: str) -> List[Defect]:
        """
        TMX-034: Verify strict placeholder preservation ({{var}}, [n]).
        """
        defects = []

        # Extract placeholders: {{...}} and [n]
        ph_pattern = r'\{\{[^}]+\}\}|\[\d+\]'
        src_placeholders = re.findall(ph_pattern, source_text)
        tgt_placeholders = re.findall(ph_pattern, target_text)

        src_set = set(src_placeholders)
        tgt_set = set(tgt_placeholders)

        missing = src_set - tgt_set
        hallucinated = tgt_set - src_set

        for ph in missing:
            defects.append(self._create_defect(
                DefectCategory.PLACEHOLDER_CORRUPTION,
                f"Placeholder missing in target: {ph}"
            ))
        for ph in hallucinated:
            defects.append(self._create_defect(
                DefectCategory.PLACEHOLDER_CORRUPTION,
                f"Placeholder hallucinated in target: {ph}"
            ))

        return defects

    def check_frequency(self, source_text: str, target_text: str) -> List[Defect]:
        """
        TMX-031: Canonical Frequency Matching (BID, QD, TID, QID).
        Frequency-pattern data lives in `quality_gate_frequencies.py` (TMX-3411).
        """
        from app.services.quality_gate_frequencies import (
            FREQ_MAP, FREQ_PATTERNS, fold_for_lookup,
        )
        defects = []

        def extract_freq(text):
            text_lower = fold_for_lookup(text.lower())
            found = []
            # Check longer patterns first
            for pattern, freq in sorted(FREQ_PATTERNS.items(), key=lambda x: -len(x[0])):
                if pattern in text_lower:
                    found.append((pattern, freq))
                    text_lower = text_lower.replace(pattern, '', 1)
            # Then check abbreviations (word boundary)
            for abbr, freq in FREQ_MAP.items():
                if re.search(rf'\b{re.escape(abbr)}\b', text_lower):
                    found.append((abbr, freq))
            return found

        src_freqs = extract_freq(source_text)
        tgt_freqs = extract_freq(target_text)

        if not src_freqs and not tgt_freqs:
            return []

        # Check for mismatches
        src_values = [f[1] for f in src_freqs]
        tgt_values = [f[1] for f in tgt_freqs]

        if src_freqs and not tgt_freqs:
            for name, val in src_freqs:
                defects.append(self._create_defect(
                    DefectCategory.FREQUENCY_MISMATCH,
                    f"Expected {name} ({val}/day) but no frequency found in target."
                ))
        elif not src_freqs and tgt_freqs:
            for name, val in tgt_freqs:
                defects.append(self._create_defect(
                    DefectCategory.FREQUENCY_MISMATCH,
                    f"Extra frequency in target: {name} ({val}/day) with no source frequency."
                ))
        elif src_freqs and tgt_freqs:
            # Compare canonical values
            if sorted(src_values) != sorted(tgt_values):
                for name, val in src_freqs:
                    if val not in tgt_values:
                        defects.append(self._create_defect(
                            DefectCategory.FREQUENCY_MISMATCH,
                            f"Expected {name} ({val}/day) but not matched in target."
                        ))
                for name, val in tgt_freqs:
                    if val not in src_values:
                        defects.append(self._create_defect(
                            DefectCategory.FREQUENCY_MISMATCH,
                            f"Extra frequency in target: {name} ({val}/day)."
                        ))

        return defects

    def check_date_formatting(self, text: str, profile_id: str) -> List[Defect]:
        """
        Regulatory Profile: Validate date formats match authority requirements.
        """
        from app.core.regulatory_profiles import get_profile
        defects = []

        profile = get_profile(profile_id)
        if not profile or not profile.get('date_format'):
            return []

        expected_fmt = profile['date_format']

        # Find date-like patterns in text
        date_pattern = r'\b(\d{1,4})[/.](\d{1,2})[/.](\d{1,4})\b'
        matches = re.finditer(date_pattern, text)

        for m in matches:
            p1, p2, p3 = int(m.group(1)), int(m.group(2)), int(m.group(3))

            if expected_fmt == "DD/MM/YYYY":
                # p1=day (1-31), p2=month (1-12), p3=year
                if not (1 <= p1 <= 31 and 1 <= p2 <= 12):
                    defects.append(self._create_defect(
                        DefectCategory.FORMATTING_ERROR,
                        f"Date '{m.group(0)}' does not match required format {expected_fmt}."
                    ))
            elif expected_fmt == "MM/DD/YYYY":
                # p1=month (1-12), p2=day (1-31), p3=year
                if not (1 <= p1 <= 12 and 1 <= p2 <= 31):
                    defects.append(self._create_defect(
                        DefectCategory.FORMATTING_ERROR,
                        f"Date '{m.group(0)}' does not match required format {expected_fmt}."
                    ))
            elif expected_fmt == "YYYY/MM/DD":
                if not (p1 > 1900 and 1 <= p2 <= 12 and 1 <= p3 <= 31):
                    defects.append(self._create_defect(
                        DefectCategory.FORMATTING_ERROR,
                        f"Date '{m.group(0)}' does not match required format {expected_fmt}."
                    ))

        return defects

    def check_mandatory_headers(self, text: str, profile_id: str) -> List[Defect]:
        """
        Regulatory Profile: Validate mandatory section headers.
        """
        from app.core.regulatory_profiles import get_profile
        defects = []

        profile = get_profile(profile_id)
        if not profile:
            return []

        mandatory = profile.get('mandatory_headings', [])
        if not mandatory:
            return []

        # Detect if this text looks like a numbered header
        header_pattern = r'^\d+\.\s*[A-Z\s\(\)]+$'
        if not re.match(header_pattern, text.strip()):
            return []

        # It looks like a header - check if it matches any mandatory heading
        text_stripped = text.strip()
        if text_stripped not in mandatory:
            defects.append(self._create_defect(
                DefectCategory.STRUCTURE_ERROR,
                f"Non-standard header detected: '{text_stripped}'. Check required format for {profile_id}."
            ))

        return defects

_gate_service_instance: Optional[QualityGateService] = None
_accessor_lock = threading.Lock()

def get_quality_gate_service() -> QualityGateService:
    """
    Singleton Accessor for QualityGateService.

    Thread-safety (TMX-3053 / audit C-08): module-level cache uses
    double-checked locking. The class-level ``__new__`` already guarantees
    exactly-one ``QualityGateService`` instance even if the accessor races,
    but locking here keeps the module-cache coherent (no torn writes
    visible to other threads under the Python memory model) and avoids
    the `not <falsy-instance>` ambiguity that the original `if not _x`
    guard exhibited.
    """
    global _gate_service_instance
    if _gate_service_instance is not None:
        return _gate_service_instance
    with _accessor_lock:
        if _gate_service_instance is None:
            _gate_service_instance = QualityGateService()
        return _gate_service_instance
