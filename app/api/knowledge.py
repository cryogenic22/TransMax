from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, timezone
import csv
import io
import json
import re
import uuid

from app.services.db_service import get_db_service
from app.models.database import DEFAULT_ORG_ID
from app.models.models import TranslationRule, Glossary, GlossaryTerm
from app.auth.providers import AuthenticatedIdentity
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permission

router = APIRouter()

# --- Schemas ---

class FeedbackRequest(BaseModel):
    source_text: str
    target_text: str
    corrected_text: Optional[str] = None
    rating: str  # "positive", "negative"
    comment: Optional[str] = None
    target_language: str


class TranslationRuleSchema(BaseModel):
    rule_id: str
    source_pattern: str
    target_correction: str
    context_tag: str
    confidence_score: float
    status: str
    origin_event_id: Optional[str] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    project_id: Optional[str] = None
    domain: Optional[str] = "general"
    is_regex: bool = False
    is_strict: bool = False
    priority: int = 0
    description: Optional[str] = None
    fire_count: int = 0
    false_positive_count: int = 0
    created_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleCreateSchema(BaseModel):
    source_pattern: str
    target_correction: str
    context_tag: str = "general"
    confidence_score: float = 1.0
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    project_id: Optional[str] = None
    domain: str = "general"
    is_regex: bool = False
    is_strict: bool = False
    priority: int = 0
    description: Optional[str] = None


class RuleUpdateSchema(BaseModel):
    status: Optional[str] = None
    source_pattern: Optional[str] = None
    target_correction: Optional[str] = None
    context_tag: Optional[str] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    project_id: Optional[str] = None
    domain: Optional[str] = None
    is_regex: Optional[bool] = None
    is_strict: Optional[bool] = None
    priority: Optional[int] = None
    description: Optional[str] = None


class RuleTestRequest(BaseModel):
    """Test a rule against sample text without saving."""
    source_pattern: str
    target_correction: str
    is_regex: bool = False
    test_source: str
    test_target: str


class BulkImportResult(BaseModel):
    imported: int
    skipped: int
    errors: List[str]


class GlossarySchema(BaseModel):
    glossary_id: str
    version: str
    is_active: bool
    meta_json: Optional[dict] = None
    term_count: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GlossaryUpdateSchema(BaseModel):
    is_active: Optional[bool] = None
    meta_json: Optional[dict] = None


class GlossaryTermCreateSchema(BaseModel):
    source_text: str
    target_text: str
    is_forbidden: bool = False
    allowed_variants: Optional[list] = None


class GlossaryTermUpdateSchema(BaseModel):
    target_text: Optional[str] = None
    is_forbidden: Optional[bool] = None
    allowed_variants: Optional[list] = None


class GlossaryUploadRequest(BaseModel):
    glossary_id: str
    version: str
    source_language: str = "en"
    target_language: str = "fr"


class RuleAnalytics(BaseModel):
    rule_id: str
    source_pattern: str
    fire_count: int
    false_positive_count: int
    last_fired_at: Optional[datetime] = None
    effectiveness: float  # fire_count / (fire_count + false_positive_count)


# --- Endpoints ---
# IMPORTANT: Static sub-path routes (/rules/test, /rules/export, etc.) MUST be
# defined BEFORE parameterized routes (/rules/{rule_id}) to avoid FastAPI
# matching the static segment as a path parameter.

@router.get("/rules", response_model=List[TranslationRuleSchema])
async def list_rules(
    status: Optional[str] = Query(None, description="Filter by status"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    source_language: Optional[str] = Query(None, description="Filter by source language"),
    target_language: Optional[str] = Query(None, description="Filter by target language"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    is_strict: Optional[bool] = Query(None, description="Filter strict-mode rules"),
    limit: int = 50,
    offset: int = 0,
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """
    List Translation Rules from the Black Book with domain scoping filters.
    """
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        query = session.query(TranslationRule)
        if status:
            query = query.filter(TranslationRule.status == status)
        if domain:
            query = query.filter(TranslationRule.domain == domain)
        if source_language:
            query = query.filter(
                (TranslationRule.source_language == source_language) |
                (TranslationRule.source_language.is_(None))
            )
        if target_language:
            query = query.filter(
                (TranslationRule.target_language == target_language) |
                (TranslationRule.target_language.is_(None))
            )
        if project_id:
            query = query.filter(
                (TranslationRule.project_id == project_id) |
                (TranslationRule.project_id.is_(None))
            )
        if is_strict is not None:
            query = query.filter(TranslationRule.is_strict == is_strict)

        rules = query.order_by(
            TranslationRule.priority.desc(),
            TranslationRule.confidence_score.desc()
        ).offset(offset).limit(limit).all()
        return rules
    finally:
        session.close()


@router.post("/rules", response_model=TranslationRuleSchema)
async def create_rule(
    rule: RuleCreateSchema,
    user: AuthenticatedIdentity = Depends(require_permission(Permission.KNOWLEDGE_MANAGE)),
):
    """Create a new Black Book rule."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        # Validate regex if is_regex
        if rule.is_regex:
            try:
                re.compile(rule.source_pattern)
            except re.error as e:
                raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {e}")

        new_rule = TranslationRule(
            # TMX-3012 will replace with session-context injection.
            organization_id=DEFAULT_ORG_ID,
            source_pattern=rule.source_pattern,
            target_correction=rule.target_correction,
            context_tag=rule.context_tag,
            confidence_score=rule.confidence_score,
            source_language=rule.source_language,
            target_language=rule.target_language,
            project_id=rule.project_id,
            domain=rule.domain,
            is_regex=rule.is_regex,
            is_strict=rule.is_strict,
            priority=rule.priority,
            description=rule.description,
            status="ACTIVE",
            created_by=user.user_id,
        )
        session.add(new_rule)
        session.commit()
        session.refresh(new_rule)
        return new_rule
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# --- Rule Testing Sandbox (static path - must be before /rules/{rule_id}) ---

@router.post("/rules/test")
async def test_rule(
    request: RuleTestRequest,
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """
    Test a rule against sample text without saving.
    Returns whether the rule would fire and what correction would be applied.
    """
    matches = []

    if request.is_regex:
        try:
            pattern = re.compile(request.source_pattern, re.IGNORECASE)
        except re.error as e:
            raise HTTPException(status_code=400, detail=f"Invalid regex: {e}")

        for m in pattern.finditer(request.test_source):
            matches.append({
                "matched_text": m.group(0),
                "start": m.start(),
                "end": m.end(),
            })
        # Check if target contains the correction
        target_has_correction = request.target_correction.lower() in request.test_target.lower()
    else:
        # Literal match
        source_lower = request.test_source.lower()
        pattern_lower = request.source_pattern.lower()
        start = 0
        while True:
            idx = source_lower.find(pattern_lower, start)
            if idx == -1:
                break
            matches.append({
                "matched_text": request.test_source[idx:idx + len(request.source_pattern)],
                "start": idx,
                "end": idx + len(request.source_pattern),
            })
            start = idx + 1
        target_has_correction = request.target_correction.lower() in request.test_target.lower()

    would_fire = len(matches) > 0 and not target_has_correction

    return {
        "would_fire": would_fire,
        "source_matches": matches,
        "target_has_correction": target_has_correction,
        "suggested_action": "VIOLATION" if would_fire else "PASS",
    }


# --- Import / Export (static paths - must be before /rules/{rule_id}) ---

@router.get("/rules/export")
async def export_rules(
    format: str = Query("csv", description="Export format: csv or json"),
    domain: Optional[str] = None,
    status: Optional[str] = Query("ACTIVE"),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """Export Black Book rules as CSV or JSON."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        query = session.query(TranslationRule)
        if status:
            query = query.filter(TranslationRule.status == status)
        if domain:
            query = query.filter(TranslationRule.domain == domain)
        rules = query.order_by(TranslationRule.priority.desc()).all()

        if format == "json":
            data = []
            for r in rules:
                data.append({
                    "source_pattern": r.source_pattern,
                    "target_correction": r.target_correction,
                    "context_tag": r.context_tag,
                    "source_language": r.source_language,
                    "target_language": r.target_language,
                    "domain": r.domain,
                    "is_regex": r.is_regex,
                    "is_strict": r.is_strict,
                    "priority": r.priority,
                    "description": r.description,
                })
            content = json.dumps(data, indent=2)
            return StreamingResponse(
                io.BytesIO(content.encode()),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=blackbook_rules.json"},
            )
        else:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "source_pattern", "target_correction", "context_tag",
                "source_language", "target_language", "domain",
                "is_regex", "is_strict", "priority", "description",
            ])
            for r in rules:
                writer.writerow([
                    r.source_pattern, r.target_correction, r.context_tag,
                    r.source_language or "", r.target_language or "", r.domain or "general",
                    r.is_regex, r.is_strict, r.priority, r.description or "",
                ])
            content = output.getvalue()
            return StreamingResponse(
                io.BytesIO(content.encode()),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=blackbook_rules.csv"},
            )
    finally:
        session.close()


@router.post("/rules/import", response_model=BulkImportResult)
async def import_rules(
    file: UploadFile = File(...),
    user: AuthenticatedIdentity = Depends(require_permission(Permission.KNOWLEDGE_MANAGE)),
):
    """
    Import Black Book rules from CSV or JSON file.
    CSV columns: source_pattern, target_correction, context_tag, source_language,
                 target_language, domain, is_regex, is_strict, priority, description
    """
    db_service = get_db_service()
    session = db_service.get_session()
    imported = 0
    skipped = 0
    errors = []

    try:
        content = await file.read()
        text = content.decode("utf-8")

        if file.filename and file.filename.endswith(".json"):
            rows = json.loads(text)
        else:
            # CSV
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)

        for i, row in enumerate(rows):
            try:
                source_pattern = row.get("source_pattern", "").strip()
                target_correction = row.get("target_correction", "").strip()
                if not source_pattern or not target_correction:
                    skipped += 1
                    continue

                is_regex = str(row.get("is_regex", "false")).lower() in ("true", "1", "yes")
                if is_regex:
                    re.compile(source_pattern)

                new_rule = TranslationRule(
                    # TMX-3012 will replace with session-context injection.
                    organization_id=DEFAULT_ORG_ID,
                    source_pattern=source_pattern,
                    target_correction=target_correction,
                    context_tag=row.get("context_tag", "general"),
                    confidence_score=1.0,
                    source_language=row.get("source_language") or None,
                    target_language=row.get("target_language") or None,
                    domain=row.get("domain", "general"),
                    is_regex=is_regex,
                    is_strict=str(row.get("is_strict", "false")).lower() in ("true", "1", "yes"),
                    priority=int(row.get("priority", 0)),
                    description=row.get("description") or None,
                    status="ACTIVE",
                    created_by=user.user_id,
                )
                session.add(new_rule)
                imported += 1
            except Exception as e:
                errors.append(f"Row {i + 1}: {str(e)}")

        session.commit()
        return BulkImportResult(imported=imported, skipped=skipped, errors=errors)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# --- Rule Analytics (static path - must be before /rules/{rule_id}) ---

@router.get("/rules/analytics", response_model=List[RuleAnalytics])
async def get_rule_analytics(
    domain: Optional[str] = None,
    min_fires: int = 0,
    limit: int = 50,
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """Get analytics for Black Book rules: fire rate, false positives, effectiveness."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        query = session.query(TranslationRule).filter(TranslationRule.status == "ACTIVE")
        if domain:
            query = query.filter(TranslationRule.domain == domain)
        if min_fires > 0:
            query = query.filter(TranslationRule.fire_count >= min_fires)

        rules = query.order_by(TranslationRule.fire_count.desc()).limit(limit).all()

        results = []
        for r in rules:
            total = r.fire_count + r.false_positive_count
            effectiveness = (r.fire_count / total * 100) if total > 0 else 0.0
            results.append(RuleAnalytics(
                rule_id=r.rule_id,
                source_pattern=r.source_pattern,
                fire_count=r.fire_count,
                false_positive_count=r.false_positive_count,
                last_fired_at=r.last_fired_at,
                effectiveness=round(effectiveness, 1),
            ))
        return results
    finally:
        session.close()


# --- Parameterized rule routes (AFTER all static /rules/* routes) ---

@router.patch("/rules/{rule_id}", response_model=TranslationRuleSchema)
async def update_rule(
    rule_id: str,
    update: RuleUpdateSchema,
    user: AuthenticatedIdentity = Depends(require_permission(Permission.KNOWLEDGE_MANAGE)),
):
    """Update a Black Book rule (status, pattern, scoping, etc.)."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        rule = session.query(TranslationRule).filter(TranslationRule.rule_id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        update_data = update.model_dump(exclude_unset=True)

        # Validate regex if changing pattern
        if update_data.get("is_regex") or (rule.is_regex and "source_pattern" in update_data):
            try:
                re.compile(update_data.get("source_pattern", rule.source_pattern))
            except re.error as e:
                raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {e}")

        for key, value in update_data.items():
            setattr(rule, key, value)

        session.commit()
        session.refresh(rule)
        return rule
    except HTTPException:
        raise
    finally:
        session.close()


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    user: AuthenticatedIdentity = Depends(require_permission(Permission.KNOWLEDGE_MANAGE)),
):
    """Delete a Black Book rule."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        rule = session.query(TranslationRule).filter(TranslationRule.rule_id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        session.delete(rule)
        session.commit()
        return {"status": "deleted", "rule_id": rule_id}
    finally:
        session.close()


@router.post("/rules/{rule_id}/report-false-positive")
async def report_false_positive(
    rule_id: str,
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """Report a false positive for a rule (used by reviewers)."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        rule = session.query(TranslationRule).filter(TranslationRule.rule_id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        rule.false_positive_count = (rule.false_positive_count or 0) + 1
        session.commit()
        return {"status": "reported", "rule_id": rule_id, "false_positive_count": rule.false_positive_count}
    finally:
        session.close()


# --- Bulk Glossary Management ---

@router.post("/glossaries/upload")
async def upload_glossary(
    file: UploadFile = File(...),
    glossary_id: str = Query(..., description="Glossary identifier"),
    version: str = Query(..., description="Version string e.g. '1.0.0'"),
    source_language: str = Query("en"),
    target_language: str = Query("fr"),
    user: AuthenticatedIdentity = Depends(require_permission(Permission.KNOWLEDGE_MANAGE)),
):
    """
    Upload a glossary CSV file. Columns: term_id, source_text, target_text, is_forbidden, allowed_variants.
    Creates or updates the glossary version.
    """
    db_service = get_db_service()
    session = db_service.get_session()
    imported = 0
    errors = []

    try:
        content = await file.read()
        text = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        # Upsert: if glossary+version exists, delete old terms first
        existing = session.query(Glossary).filter(
            Glossary.glossary_id == glossary_id,
            Glossary.version == version,
        ).first()

        if existing:
            # Delete old terms to prevent duplicate accumulation
            session.query(GlossaryTerm).filter(
                GlossaryTerm.glossary_id == glossary_id,
                GlossaryTerm.glossary_version == version,
            ).delete()
            existing.meta_json = {"source_language": source_language, "target_language": target_language}
        else:
            glossary = Glossary(
                # TMX-3012 will replace with session-context injection.
                organization_id=DEFAULT_ORG_ID,
                glossary_id=glossary_id,
                version=version,
                is_active=True,
                meta_json={"source_language": source_language, "target_language": target_language},
            )
            session.add(glossary)
            session.flush()

        for i, row in enumerate(reader):
            try:
                source_text = row.get("source_text", "").strip()
                target_text = row.get("target_text", "").strip()
                if not source_text or not target_text:
                    continue

                term = GlossaryTerm(
                    # TMX-3012 will replace with session-context injection.
                    organization_id=DEFAULT_ORG_ID,
                    glossary_id=glossary_id,
                    glossary_version=version,
                    term_id=row.get("term_id", str(uuid.uuid4())),
                    source_text=source_text,
                    target_text=target_text,
                    is_forbidden=str(row.get("is_forbidden", "false")).lower() in ("true", "1"),
                    allowed_variants=json.loads(row.get("allowed_variants", "[]")) if row.get("allowed_variants") else [],
                )
                session.add(term)
                imported += 1
            except Exception as e:
                errors.append(f"Row {i + 1}: {str(e)}")

        session.commit()
        return {"status": "uploaded", "glossary_id": glossary_id, "version": version, "terms_imported": imported, "errors": errors}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/glossaries", response_model=List[GlossarySchema])
async def list_glossaries(user: AuthenticatedIdentity = Depends(get_current_user)):
    """List all glossaries with term counts."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        from sqlalchemy import func
        glossaries = session.query(Glossary).all()
        result = []
        for g in glossaries:
            count = session.query(func.count(GlossaryTerm.id)).filter(
                GlossaryTerm.glossary_id == g.glossary_id,
                GlossaryTerm.glossary_version == g.version,
            ).scalar()
            result.append(GlossarySchema(
                glossary_id=g.glossary_id,
                version=g.version,
                is_active=g.is_active,
                meta_json=g.meta_json,
                term_count=count,
                created_at=g.created_at,
            ))
        return result
    finally:
        session.close()


@router.get("/glossaries/{glossary_id}/{version}/terms")
async def get_glossary_terms(
    glossary_id: str,
    version: str,
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """Get all terms for a specific glossary version."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        terms = session.query(GlossaryTerm).filter(
            GlossaryTerm.glossary_id == glossary_id,
            GlossaryTerm.glossary_version == version,
        ).all()
        return [
            {
                "term_id": t.term_id,
                "source_text": t.source_text,
                "target_text": t.target_text,
                "is_forbidden": t.is_forbidden,
                "allowed_variants": t.allowed_variants,
            }
            for t in terms
        ]
    finally:
        session.close()


# --- Glossary CRUD Endpoints ---

@router.patch("/glossaries/{glossary_id}/{version}")
async def update_glossary(
    glossary_id: str,
    version: str,
    update: GlossaryUpdateSchema,
    user: AuthenticatedIdentity = Depends(require_permission(Permission.KNOWLEDGE_MANAGE)),
):
    """Toggle is_active or update meta_json for a glossary."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        glossary = session.query(Glossary).filter(
            Glossary.glossary_id == glossary_id,
            Glossary.version == version,
        ).first()
        if not glossary:
            raise HTTPException(status_code=404, detail="Glossary not found")

        update_data = update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(glossary, key, value)

        session.commit()
        return {"status": "updated", "glossary_id": glossary_id, "version": version}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/glossaries/{glossary_id}/{version}")
async def delete_glossary(
    glossary_id: str,
    version: str,
    user: AuthenticatedIdentity = Depends(require_permission(Permission.KNOWLEDGE_MANAGE)),
):
    """Delete a glossary and cascade-delete its terms."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        glossary = session.query(Glossary).filter(
            Glossary.glossary_id == glossary_id,
            Glossary.version == version,
        ).first()
        if not glossary:
            raise HTTPException(status_code=404, detail="Glossary not found")

        # Delete terms explicitly (SQLite may not enforce FK CASCADE)
        session.query(GlossaryTerm).filter(
            GlossaryTerm.glossary_id == glossary_id,
            GlossaryTerm.glossary_version == version,
        ).delete()
        session.delete(glossary)
        session.commit()
        return {"status": "deleted", "glossary_id": glossary_id, "version": version}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/glossaries/{glossary_id}/{version}/terms")
async def add_glossary_term(
    glossary_id: str,
    version: str,
    term_data: GlossaryTermCreateSchema,
    user: AuthenticatedIdentity = Depends(require_permission(Permission.KNOWLEDGE_MANAGE)),
):
    """Add a single term to a glossary."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        glossary = session.query(Glossary).filter(
            Glossary.glossary_id == glossary_id,
            Glossary.version == version,
        ).first()
        if not glossary:
            raise HTTPException(status_code=404, detail="Glossary not found")

        term = GlossaryTerm(
            # TMX-3012 will replace with session-context injection.
            organization_id=DEFAULT_ORG_ID,
            glossary_id=glossary_id,
            glossary_version=version,
            term_id=str(uuid.uuid4()),
            source_text=term_data.source_text,
            target_text=term_data.target_text,
            is_forbidden=term_data.is_forbidden,
            allowed_variants=term_data.allowed_variants or [],
        )
        session.add(term)
        session.commit()
        return {
            "term_id": term.term_id,
            "source_text": term.source_text,
            "target_text": term.target_text,
            "is_forbidden": term.is_forbidden,
            "allowed_variants": term.allowed_variants,
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.patch("/glossaries/{glossary_id}/{version}/terms/{term_id}")
async def update_glossary_term(
    glossary_id: str,
    version: str,
    term_id: str,
    update: GlossaryTermUpdateSchema,
    user: AuthenticatedIdentity = Depends(require_permission(Permission.KNOWLEDGE_MANAGE)),
):
    """Edit a single glossary term."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        term = session.query(GlossaryTerm).filter(
            GlossaryTerm.glossary_id == glossary_id,
            GlossaryTerm.glossary_version == version,
            GlossaryTerm.term_id == term_id,
        ).first()
        if not term:
            raise HTTPException(status_code=404, detail="Term not found")

        update_data = update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(term, key, value)

        session.commit()
        return {
            "term_id": term.term_id,
            "source_text": term.source_text,
            "target_text": term.target_text,
            "is_forbidden": term.is_forbidden,
            "allowed_variants": term.allowed_variants,
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/glossaries/{glossary_id}/{version}/terms/{term_id}")
async def delete_glossary_term(
    glossary_id: str,
    version: str,
    term_id: str,
    user: AuthenticatedIdentity = Depends(require_permission(Permission.KNOWLEDGE_MANAGE)),
):
    """Delete a single glossary term."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        term = session.query(GlossaryTerm).filter(
            GlossaryTerm.glossary_id == glossary_id,
            GlossaryTerm.glossary_version == version,
            GlossaryTerm.term_id == term_id,
        ).first()
        if not term:
            raise HTTPException(status_code=404, detail="Term not found")

        session.delete(term)
        session.commit()
        return {"status": "deleted", "term_id": term_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/glossaries/{glossary_id}/{version}/export")
async def export_glossary(
    glossary_id: str,
    version: str,
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """Export glossary terms as CSV download."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        terms = session.query(GlossaryTerm).filter(
            GlossaryTerm.glossary_id == glossary_id,
            GlossaryTerm.glossary_version == version,
        ).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["term_id", "source_text", "target_text", "is_forbidden", "allowed_variants"])
        for t in terms:
            writer.writerow([
                t.term_id,
                t.source_text,
                t.target_text,
                t.is_forbidden,
                json.dumps(t.allowed_variants or []),
            ])

        content = output.getvalue()
        filename = f"{glossary_id}_{version}.csv"
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        session.close()


# --- Feedback ---

@router.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest, user: AuthenticatedIdentity = Depends(get_current_user)):
    """Capture user feedback as a proposed rule (Black Book inbox)."""
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        if feedback.rating == "negative" and feedback.corrected_text:
            new_rule = TranslationRule(
                # TMX-3012 will replace with session-context injection.
                organization_id=DEFAULT_ORG_ID,
                source_pattern=feedback.source_text,
                target_correction=feedback.corrected_text,
                context_tag="feedback_loop",
                confidence_score=1.0,
                target_language=feedback.target_language,
                status="PENDING_APPROVAL",
                origin_event_id=f"feedback_{datetime.now(timezone.utc).timestamp()}",
                created_by=user.user_id,
            )
            session.add(new_rule)
            session.commit()
            return {"status": "rule_created", "rule_id": new_rule.rule_id}

        return {"status": "feedback_recorded"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
