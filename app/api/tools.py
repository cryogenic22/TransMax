from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage

from app.services.quality_gate import get_quality_gate_service
from app.services.llm import get_llm
from app.services.db_service import DatabaseService
from tenacity import retry, stop_after_attempt, wait_exponential
from app.auth.providers import AuthenticatedIdentity
from app.auth.dependencies import get_current_user

import logging
logger = logging.getLogger(__name__)


router = APIRouter()

# --- Request Models ---

class AuditRequest(BaseModel):
    source_text: str
    translated_text: str
    target_language: str
    glossary: Optional[List[Dict[str, str]]] = None

class BackTranslateRequest(BaseModel):
    translated_text: str
    target_language: str # The language of the translated_text
    
class MatrixRequest(BaseModel):
    text: str
    languages: List[str] = ["de", "fr", "es", "it", "ja"]

class UniversalTranslateRequest(BaseModel):
    text: str
    source_language: str
    target_language: str

# --- Endpoints ---

@router.post("/audit")
async def audit_translation(request: AuditRequest, user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    Quality Auditor: Runs deterministic checks (Glossary, Negation, Units).
    """
    gate_service = get_quality_gate_service()
    
    # Construct constraints dict
    # Fetch system rules (Black Book)
    db = DatabaseService()
    system_constraints = db.get_constraints("auto", request.target_language) # Source 'auto' might miss specific pairs, but handles target-based rules
    
    # Merge user glossary with system glossary
    constraints = system_constraints
    if request.glossary:
        constraints["glossary"] = constraints.get("glossary", []) + request.glossary
    
    # Run checks
    violations = gate_service.check_segment(
        request.source_text,
        request.translated_text,
        constraints,
        request.target_language
    )
    
    # Classify result
    severity_rank = {
        "critical": 3,
        "high": 2,
        "medium": 1,
        "low": 0
    }
    
    max_severity = "pass"
    for v in violations:
        current = v.get("severity", "low").lower()
        if severity_rank.get(current, 0) > severity_rank.get(max_severity, -1):
            max_severity = current
            
    return {
        "status": "FAIL" if max_severity in ["critical", "high"] else "PASS",
        "max_severity": max_severity,
        "violations": violations
    }

@router.post("/back-translate")
async def back_translate(request: BackTranslateRequest, user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    Back-Translation Verifier: Translates back to English & calculates drift.
    """
    llm = get_llm()

    # 1. Back Translate to English
    if request.target_language.lower() == "auto":
        system_msg = SystemMessage(content="Translate the following text back into English. Detect the source language automatically. Return ONLY the translation.")
    else:
        system_msg = SystemMessage(content=f"Translate the following {request.target_language} text back into English. Return ONLY the translation.")
    
    user_msg = HumanMessage(content=request.translated_text)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def invoke_llm_with_retry(messages):
        return await llm.ainvoke(messages)

    try:
        response = await invoke_llm_with_retry([system_msg, user_msg])
        back_translation = response.content.strip()
        
        # 2. Note: We don't have the original source here to compare drift against!
        # The user only provided translated_text. 
        # Ideally, we need source_text to compute drift.
        # But if the user just wants to SEE the back translation to judge context, that's fine.
        # IF they provide source, we can compute score.
        # Let's assume for this tool, it's a "Reality Check" tool.
        # We can't compute drift without source.
        
        return {
            "back_translation": back_translation,
            "drift_score": None # Cannot compute without source
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/back-translate/with-source")
async def back_translate_with_source(request: AuditRequest, user: AuthenticatedIdentity = Depends(get_current_user)): # Use AuditRequest as it has both
    """
    Full Verification: Back-translates and computes Semantic Drift against Source.
    """
    llm = get_llm()
    gate_service = get_quality_gate_service()
    
    # 1. Back Translate
    if request.target_language.lower() == "auto":
        system_msg = SystemMessage(content="Translate the following text back into English. Detect the source language automatically. Return ONLY the translation.")
    else:
        system_msg = SystemMessage(content=f"Translate the following {request.target_language} text back into English. Return ONLY the translation.")

    user_msg = HumanMessage(content=request.translated_text)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def invoke_llm_with_retry(messages):
        return await llm.ainvoke(messages)

    try:
        response = await invoke_llm_with_retry([system_msg, user_msg])
        back_translation = response.content.strip()
        
        # 2. Compute Drift
        score = gate_service.calculate_semantic_drift(request.source_text, back_translation)
        
        return {
            "back_translation": back_translation,
            "drift_score": score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/translate/universal")
async def universal_translate(request: UniversalTranslateRequest, user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    Universal Translator: Any-to-Any translation with auto-detection and quality gates.
    """
    from app.services.language_detection import detect_language, get_language_name

    llm = get_llm()

    # Auto-detect source language if "auto" or empty
    source_lang = request.source_language
    if not source_lang or source_lang == "auto":
        detection = detect_language(request.text)
        source_lang = detection.language

    src = get_language_name(source_lang)
    tgt = get_language_name(request.target_language)
    
    # Fetch Constraints (Black Book Rules)
    db = DatabaseService()
    constraints = db.get_constraints(source_lang, request.target_language)
    
    glossary_text = ""
    if constraints.get("glossary"):
        glossary_text = "\n\nCRITICAL GLOSSARY/RULES:\n"
        for term in constraints["glossary"]:
           glossary_text += f"- {term['term']} -> {term['target']}\n"
    
    # Detect if input is HTML (basic check)
    is_html = "<" in request.text and ">" in request.text
    
    if is_html:
        # Keep HTML flow simple for now (no segmentation support yet for HTML)
        system_msg = SystemMessage(content=f"""You are an expert translator. 
Translate the text content inside the HTML tags from {src} to {tgt}.
Do NOT translate HTML tag names, attributes, or structural elements.
Keep the exact HTML structure.{glossary_text}
Return ONLY the translation.""")
    else:
        # Request JSON segments for highlighting support
        system_msg = SystemMessage(content=f"""You are an expert translator.
Translate the following text from {src} to {tgt}.
Maintain professional tone and formatting.{glossary_text}

OUTPUT FORMAT:
Return a JSON object with a "segments" array. 
Each segment should map a coherent sentence or phrase from source to target.
Example:
{{
  "segments": [
    {{ "source": "Hello world.", "target": "Hallo Welt." }}
  ]
}}
Ensure all text is covered.""")
    
    user_msg = HumanMessage(content=request.text)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def invoke_llm_with_retry(messages):
        return await llm.ainvoke(messages)

    try:
        response = await invoke_llm_with_retry([system_msg, user_msg])
        
        # Parse Response
        try:
            from app.services.json_parser import RobustParser
            if is_html:
                # HTML path remains text-based for now
                translated_text = response.content
                segments = [{"source": request.text, "target": translated_text}]
            else:
                data = RobustParser.parse(response.content)
                segments = data.get("segments", [])
                if not segments and "translated_text" in data:
                     # Fallback if model just gave text
                     segments = [{"source": request.text, "target": data["translated_text"]}]
                elif not segments:
                     # Fallback if model failed JSON completely but RobustParser returned something else?
                     # RobustParser usually handles markdown blocks. 
                     # If parsing failed or empty, treat content as text if strict mode wasn't enforced.
                     # But RobustParser.parse usually returns dict.
                     if isinstance(data, dict):
                         # Maybe keys differ?
                         segments = [{"source": request.text, "target": response.content}] # Ultimate fallback
                
                # Reconstruct full text
                translated_text = " ".join([s.get("target", "") for s in segments])
        except Exception as parse_e:
            logger.warning(f"JSON Parse failed, falling back to text: {parse_e}")
            translated_text = response.content
            segments = [{"source": request.text, "target": translated_text}]

        # Calculate Confidence (Best Effort).
        # TMX-TOOLS-CONF-HONEST (A3): on scoring failure we must NOT emit a
        # fabricated "90% / High" verdict — a scoring outage would otherwise
        # render in the UI as a green "Ready for Review". Defaults below are
        # the HONEST "scoring unavailable" state; the try-block overwrites
        # them with real values only on success.
        scoring_available = False
        confidence_score = None
        score_breakdown = {}
        score_band = "Unavailable"
        breakdown_reasoning: list[str] = []  # TMX-QDASH-CONTRACT
        recommendations = []

        try:
            from app.services.quality_gate import get_quality_gate_service
            from app.services.confidence_service import ConfidenceService
            from bs4 import BeautifulSoup
            
            # For scoring, we must strip HTML tags to avoid false positives on tag syntax
            def strip_html(html_str):
                try:
                    return BeautifulSoup(html_str, "html.parser").get_text()
                except Exception:
                    return html_str

            scoring_src = strip_html(request.text) if is_html else request.text
            scoring_tgt = strip_html(translated_text) if is_html else translated_text

            gate_service = get_quality_gate_service()
            violations = gate_service.check_segment(scoring_src, scoring_tgt, constraints, request.target_language)
            
            score_result = ConfidenceService.calculate_score(
                defects=violations,
                source_text=scoring_src,
                process_flags={"reflexion_run": False},
                source_language=source_lang,
                target_language=request.target_language,
            )
            confidence_score = score_result.final_score
            score_breakdown = score_result.components
            score_band = score_result.band
            # TMX-QDASH-CONTRACT: surface the engine's real, human-readable
            # reasoning so the UI renders the actual "why" instead of
            # fabricated dimension bars. The engine already computes this.
            breakdown_reasoning = list(score_result.breakdown_reasoning)
            scoring_available = True

            # TMX-CONF-1: surface concrete issues from ALL violations + the
            # confidence score (not just band=="Low"/Glossary), so the response
            # points the user at real problems instead of reading "all OK".
            from app.services.review_flags import summarize_issues
            summary = summarize_issues(violations, confidence_score, score_band)
            issues = summary["issues"]
            needs_review = summary["needs_review"]
            review_note = summary["note"]
            recommendations = [i["message"] for i in issues]
            if "formula" in scoring_src.lower() or "=" in scoring_src:
                recommendations.append("Source contains formulas/math. Verify precision.")

        except Exception as e:
            # TMX-TOOLS-CONF-HONEST (A3): return the translation, but do NOT
            # fabricate a confidence verdict. Leave confidence=None /
            # band="Unavailable" and force review so the UI shows an honest
            # "quality scoring unavailable" state, never a green 90%.
            logger.warning(f"Scoring failed: {e}")
            review_note = (
                "Quality scoring is unavailable for this translation — "
                "manual review required before use."
            )
            recommendations = [review_note]

        return {
            "translated_text": translated_text,
            "segments": segments,
            "scoring_available": scoring_available,
            "confidence": confidence_score,
            "score_breakdown": score_breakdown,
            "breakdown_reasoning": breakdown_reasoning,
            "score_band": score_band,
            # A scoring outage is always review-worthy; a successful score
            # carries its own needs_review verdict from summarize_issues.
            "needs_review": needs_review if 'needs_review' in locals() else True,
            "issues": issues if 'issues' in locals() else [],
            "review_note": review_note if 'review_note' in locals() else "",
            "recommendations": recommendations if 'recommendations' in locals() else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/matrix")
async def translation_matrix(request: MatrixRequest, user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    Multi-Lingual Matrix: Parallel translation to multiple languages.
    """
    llm = get_llm()
    
    lang_names = {
        'de': 'German', 'fr': 'French', 'es': 'Spanish',
        'it': 'Italian', 'ja': 'Japanese', 'zh': 'Chinese', 'ar': 'Arabic', 'ru': 'Russian'
    }
    
    async def translate_one(lang_code):
        tgt = lang_names.get(lang_code, lang_code)
        system_msg = SystemMessage(content=f"Translate to {tgt}. Return ONLY translation.")
        user_msg = HumanMessage(content=request.text)
        try:
            res = await llm.ainvoke([system_msg, user_msg])
            return lang_code, res.content.strip()
        except Exception:
            return lang_code, "Error"

    # Limit concurrency
    semaphore = asyncio.Semaphore(5)
    
    async def process(code):
        async with semaphore:
            return await translate_one(code)
    
    results = await asyncio.gather(*[process(code) for code in request.languages])
    
    return {
        "results": {code: text for code, text in results}
    }
