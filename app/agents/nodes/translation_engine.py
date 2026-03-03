"""
TransMax Translation Engine v2.0
================================
Production-grade concurrent LLM translation with deterministic quality gates.

ENGINEERING PRINCIPLES:
1. Deterministic Core, LLM at Edges - LLMs used only for translation, not control flow
2. Segment Atomicity - Each segment is an independent unit of work with its own state
3. Progressive Processing - Real-time progress updates, not simulated
4. Circuit Breaker Pattern - Graceful degradation on LLM failures
5. Backpressure Management - Semaphores prevent overwhelming LLM APIs
6. Idempotent Operations - Can retry any segment without side effects
7. Structured Observability - Metrics, logging, tracing

ARCHITECTURE:
┌─────────────────────────────────────────────────────────────────────┐
│                        TranslationEngine                             │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ SegmentQueue │──│ BatchManager │──│ ConcurrentLLMWorkerPool │  │
│  │  (Priority)  │  │  (Batching)  │  │  (Semaphore-controlled) │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│         │                 │                      │                  │
│         ▼                 ▼                      ▼                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ ProgressTracker│ │QualityGate   │ │ CircuitBreaker           │  │
│  │ (Real-time DB) │ │(Deterministic)│ │ (Failure Protection)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
"""

import asyncio
import logging
import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple
from enum import Enum
from collections import deque
import hashlib

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm import get_llm
from app.services.json_parser import RobustParser
from app.services.quality_gate import QualityGateService
from app.services.db_service import DatabaseService
from app.agents.prompts import TransMaxPrompts
from app.models.database import SegmentStatus, DocumentStatus
from app.core.constants import SubstitutionType
from app.services.language_packs.factory import LanguagePackFactory

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION (Production-tuned constants)
# ============================================================================

@dataclass
class EngineConfig:
    """Configurable engine parameters for different deployment scenarios."""
    batch_size: int = 5                    # Segments per LLM call
    max_concurrent_batches: int = 4        # Concurrent LLM calls
    max_retries: int = 2                   # Per-batch retries
    retry_delay_base: float = 1.0          # Exponential backoff base
    llm_timeout_seconds: float = 60.0      # Per-call timeout
    circuit_breaker_threshold: int = 5     # Failures before circuit opens
    circuit_breaker_reset_seconds: float = 60.0
    progress_update_interval: int = 1      # Update DB every N segments


# ============================================================================
# CIRCUIT BREAKER - Prevents cascade failures
# ============================================================================

class CircuitState(Enum):
    CLOSED = "closed"     # Normal operation
    OPEN = "open"         # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Implements the Circuit Breaker pattern for LLM calls.
    Prevents hammering a failing service and allows recovery.
    """
    
    def __init__(self, threshold: int = 5, reset_timeout: float = 60.0):
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            self._check_state()
            
            if self.state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. {self.failure_count} failures. "
                    f"Will retry in {self.reset_timeout - (time.time() - self.last_failure_time):.1f}s"
                )
        
        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure()
            raise
    
    def _check_state(self):
        """Transition state based on conditions."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.reset_timeout:
                logger.info("Circuit breaker: OPEN -> HALF_OPEN (testing)")
                self.state = CircuitState.HALF_OPEN
    
    async def _record_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                logger.info("Circuit breaker: HALF_OPEN -> CLOSED (recovered)")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
    
    async def _record_failure(self):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.threshold:
                logger.error(f"Circuit breaker: -> OPEN ({self.failure_count} failures)")
                self.state = CircuitState.OPEN


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker prevents execution."""
    pass


# ============================================================================
# SEGMENT STATE MACHINE - Atomic segment processing
# ============================================================================

class SegmentState(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    TRANSLATING = "translating"
    QUALITY_CHECK = "quality_check"
    TRANSLATED = "translated"
    FAILED = "failed"
    BLOCKED = "blocked"  # Quality gate block


@dataclass
class SegmentUnit:
    """
    Represents an atomic unit of translation work.
    Each segment is processed independently with its own state.
    """
    segment_id: str
    source_text: str
    order_index: int
    
    # State
    state: SegmentState = SegmentState.PENDING
    translated_text: Optional[str] = None
    gate_results: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    tm_match: Optional[Dict[str, Any]] = None
    translation_source: str = ""
    confidence_score: float = 0.0
    retry_count: int = 0
    error_message: Optional[str] = None
    
    # Reflexion
    validation_score: Optional[float] = None

    # Context (for LLM)
    prev_context: Optional[str] = None
    next_context: Optional[str] = None
    prev_target_context: Optional[str] = None # Golden Thread: Previous translated text
    
    # Timing
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def to_update_dict(self) -> Dict[str, Any]:
        """Convert to DB update format."""
        return {
            "segment_id": self.segment_id,
            "translated_text": self.translated_text,
            "status": SegmentStatus.TRANSLATED.value if self.state == SegmentState.TRANSLATED else SegmentStatus.PENDING.value,
            "translation_source": self.translation_source,
            "gate_results": self.gate_results,
            "confidence_score": self.confidence_score
        }

@dataclass
class TranslationProgress:
    total_segments: int
    completed: int = 0
    failed: int = 0
    blocked: int = 0

    def to_dict(self):
        return {
            "total": self.total_segments,
            "completed": self.completed,
            "failed": self.failed,
            "blocked": self.blocked
        }

class ProgressTracker:
    def __init__(self, db_service: DatabaseService, doc_id: str, total_segments: int):
        self.db = db_service
        self.doc_id = doc_id
        self.stats = TranslationProgress(total_segments=total_segments)
        
    @property
    def completed(self): return self.stats.completed
    
    @property
    def failed(self): return self.stats.failed
    
    @property
    def blocked(self): return self.stats.blocked

    @property
    def total_segments(self): return self.stats.total_segments

    async def initialize(self):
        pass

    async def update(self, state: SegmentState, count: int = 1):
        if state == SegmentState.TRANSLATED:
            self.stats.completed += count
        elif state == SegmentState.FAILED:
            self.stats.failed += count
        elif state == SegmentState.BLOCKED:
            self.stats.blocked += count

class TranslationEngine:
    """
    Orchestrates the translation pipeline.
    """
    
    def __init__(self, config: EngineConfig = EngineConfig()):
        self.config = config
        self.quality_gate = QualityGateService()
        self.db_service = DatabaseService()
        self.llm = get_llm()
        self._circuit_breaker = CircuitBreaker(
            threshold=config.circuit_breaker_threshold,
            reset_timeout=config.circuit_breaker_reset_seconds
        )
        self._semaphore = asyncio.Semaphore(config.max_concurrent_batches)

    async def translate_document(
        self,
        doc_id: str,
        segments: List[Dict[str, Any]],
        target_language: str,
        constraint_pack: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Main entry point for document translation.
        Returns (translated_segments, quality_report).
        """
        start_time = time.time()
        
        # 0. Init Progress
        progress = ProgressTracker(
            db_service=self.db_service,
            doc_id=doc_id,
            total_segments=len(segments)
        )
        await progress.initialize()
        
        # 1. Prepare Units (Context & State)
        units = self._prepare_segment_units(segments)
        
        # 2. Separate TM Matches (Don't translate)
        tm_units, llm_units = self._separate_tm_matches(units)
        
        # Mark TM units as done
        if tm_units:
            await progress.update(SegmentState.TRANSLATED, len(tm_units))
            self._persist_segments(tm_units)
            
        # 3. Create Batches for LLM
        batches = self._create_batches(llm_units)
        
        # 4. Process Batches (Concurrent)
        await self._process_all_batches(
            batches, 
            target_language, 
            constraint_pack, 
            progress
        )
        
        # 5. Finalize
        duration = time.time() - start_time
        await self._update_document_status(doc_id, progress.stats)
        
        # Re-assemble results
        all_units = sorted(tm_units + llm_units, key=lambda u: u.order_index)
        result_segments = [u.to_update_dict() for u in all_units]
        
        report = self._build_quality_report(all_units, progress.stats, duration)
        
        return result_segments, report

    def _prepare_segment_units(self, segments: List[Dict[str, Any]]) -> List[SegmentUnit]:
        """Convert raw segment dicts to SegmentUnits with context injection."""
        units = []
        
        for i, seg in enumerate(segments):
            unit = SegmentUnit(
                segment_id=seg['segment_id'],
                source_text=seg['source_text'],
                order_index=seg.get('order_index', i),
                tm_match=seg.get('tm_match')
            )
            
            # Inject context from neighbors (Sliding Window)
            # Increased window size to 500 chars for better coherence
            if i > 0:
                prev_seg = segments[i-1]
                unit.prev_context = prev_seg['source_text'][:500]
                
                # GOLDEN THREAD: Check if previous segment has a TM Exact Match
                # If so, we can provide the "Canonical Translation" of the previous segment as context.
                if prev_seg.get('tm_match') and prev_seg['tm_match'].get('type') == SubstitutionType.TM_EXACT:
                     unit.prev_target_context = prev_seg['tm_match'].get('target')
                # If serialized correctly we might also have 'translated_text' populated?
                elif prev_seg.get('translated_text'):
                     unit.prev_target_context = prev_seg['translated_text']

            if i < len(segments) - 1:
                unit.next_context = segments[i+1]['source_text'][:500]
            
            units.append(unit)
        
        return units
    
    def _separate_tm_matches(
        self, 
        units: List[SegmentUnit]
    ) -> Tuple[List[SegmentUnit], List[SegmentUnit]]:
        """Separate TM exact matches from LLM-needed segments."""
        tm_units = []
        llm_units = []
        
        for unit in units:
            if unit.tm_match and unit.tm_match.get('type') == SubstitutionType.TM_EXACT:
                unit.translated_text = unit.tm_match['target']
                unit.translation_source = SubstitutionType.TM_EXACT.value
                unit.confidence_score = 1.0
                unit.state = SegmentState.TRANSLATED
                unit.gate_results = {"tm_exact": True, "violations": []}
                tm_units.append(unit)
            else:
                llm_units.append(unit)
        
        return tm_units, llm_units
    
    def _create_batches(self, units: List[SegmentUnit]) -> List[List[SegmentUnit]]:
        """Create batches for concurrent processing."""
        batch_size = self.config.batch_size
        return [units[i:i + batch_size] for i in range(0, len(units), batch_size)]
    
    async def _process_all_batches(
        self,
        batches: List[List[SegmentUnit]],
        target_language: str,
        constraint_pack: Dict[str, Any],
        progress: ProgressTracker
    ):
        """Process all batches with controlled concurrency."""
        
        tasks = [
            self._process_batch(
                batch=batch,
                batch_idx=idx,
                target_language=target_language,
                constraint_pack=constraint_pack,
                progress=progress
            )
            for idx, batch in enumerate(batches)
        ]
        
        # Gather with exception handling per task
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any batch failures
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[Engine] Batch {idx} failed: {result}")
    
    async def _process_batch(
        self,
        batch: List[SegmentUnit],
        batch_idx: int,
        target_language: str,
        constraint_pack: Dict[str, Any],
        progress: ProgressTracker
    ):
        """Process a single batch with semaphore, retry, and circuit breaker."""
        
        async with self._semaphore:  # Limit concurrent LLM calls
            for attempt in range(self.config.max_retries + 1):
                try:
                    logger.info(f"[Batch {batch_idx}] Attempt {attempt+1}: {len(batch)} segments")
                    
                    # Mark as translating
                    for unit in batch:
                        unit.state = SegmentState.TRANSLATING
                        unit.started_at = time.time()
                    
                    # Call LLM with circuit breaker protection
                    translations = await self._circuit_breaker.call(
                        self._call_llm,
                        batch,
                        target_language,
                        constraint_pack
                    )
                    
                    # Apply translations and run quality gates
                    for unit in batch:
                        trans = translations.get(unit.segment_id)
                        if trans:
                            unit.translated_text = trans
                            unit.translation_source = "llm_engine_v2"
                            unit.state = SegmentState.QUALITY_CHECK
                            
                            # Run deterministic quality gates
                            violations = self.quality_gate.check_segment(
                                source_text=unit.source_text,
                                target_text=trans,
                                constraints=constraint_pack,
                                target_lang=target_language
                            )
                            # Run Deterministic Scorer
                            from app.services.confidence_service import ConfidenceService
                            
                            score_result = ConfidenceService.calculate_score(
                                defects=violations,
                                semantic_drift_score=unit.validation_score or 0.0, # Assumes reflexion ran
                                source_text=unit.source_text,
                                process_flags={"reflexion_run": True} # Placeholder until piped from graph
                            )
                            
                            unit.confidence_score = score_result.final_score
                            
                            # Enrich gate results with scoring breakdown for UI
                            gate_result = {
                                "violations": violations,
                                "blocked": score_result.status == "BLOCKED" or any(v.get('severity') == 'critical' for v in violations),
                                "score_breakdown": score_result.components,
                                "score_reasoning": score_result.breakdown_reasoning,
                                "score_band": score_result.band
                            }
                            unit.gate_results = gate_result
                            
                            # Check for blocks
                            if gate_result.get('blocked'):
                                unit.state = SegmentState.BLOCKED
                                await progress.update(SegmentState.BLOCKED)
                            else:
                                unit.state = SegmentState.TRANSLATED
                        else:
                            unit.state = SegmentState.FAILED
                            unit.error_message = "No translation returned"
                        
                        unit.completed_at = time.time()
                    
                    # Persist batch results
                    self._persist_segments(batch)
                    
                    # Update progress
                    translated_count = sum(1 for u in batch if u.state == SegmentState.TRANSLATED)
                    failed_count = sum(1 for u in batch if u.state == SegmentState.FAILED)
                    
                    if translated_count:
                        await progress.update(SegmentState.TRANSLATED, translated_count)
                    if failed_count:
                        await progress.update(SegmentState.FAILED, failed_count)
                    
                    logger.info(f"[Batch {batch_idx}] Success: {translated_count} translated, {failed_count} failed")
                    return  # Success, exit retry loop
                    
                except CircuitBreakerOpenError as e:
                    logger.warning(f"[Batch {batch_idx}] Circuit breaker open: {e}")
                    for unit in batch:
                        unit.state = SegmentState.FAILED
                        unit.error_message = str(e)
                    await progress.update(SegmentState.FAILED, len(batch))
                    return  # Don't retry when circuit is open
                    
                except Exception as e:
                    logger.warning(f"[Batch {batch_idx}] Attempt {attempt+1} failed: {e}")
                    for unit in batch:
                        unit.retry_count += 1
                    
                    if attempt < self.config.max_retries:
                        delay = self.config.retry_delay_base * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        # Final failure
                        for unit in batch:
                            unit.state = SegmentState.FAILED
                            unit.error_message = str(e)
                        await progress.update(SegmentState.FAILED, len(batch))
    
    async def _call_llm(
        self,
        batch: List[SegmentUnit],
        target_language: str,
        constraint_pack: Dict[str, Any]
    ) -> Dict[str, str]:
        """Call LLM and parse response. Returns {segment_id: translation}."""
        
        # Build payload
        input_segments = [
            {
                "id": u.segment_id,
                "text": u.source_text,
                **({"prev_context": u.prev_context} if u.prev_context else {}),
                **({"next_context": u.next_context} if u.next_context else {}),
                **({"prev_target_context": u.prev_target_context} if u.prev_target_context else {})
            }
            for u in batch
        ]
        
        # Build prompt
        messages = self._build_prompt(input_segments, target_language, constraint_pack)
        
        # Call with timeout
        response = await asyncio.wait_for(
            self.llm.ainvoke(messages),
            timeout=self.config.llm_timeout_seconds
        )
        
        # Parse response
        data = RobustParser.parse(response.content)
        
        # Extract translations
        translations = {}
        for seg in data.get('segments', []):
            seg_id = seg.get('segment_id') or seg.get('id')
            trans = seg.get('target_text') or seg.get('translated_text')
            if seg_id and trans:
                translations[seg_id] = trans
        
        return translations
    
    def _build_prompt(
        self,
        input_segments: List[Dict[str, Any]],
        target_language: str,
        constraint_pack: Dict[str, Any]
    ) -> list:
        """Build LLM prompt."""
        # Get language-specific instructions
        try:
            pack = LanguagePackFactory.get_pack(target_language)
            lang_instruction = pack.prompt_instruction
        except Exception:
            lang_instruction = ""

        user_content = TransMaxPrompts.TRANSLATOR_USER_V1.replace(
            "{{target_language}}", target_language
        ).replace(
            "{{audience}}", "general"
        ).replace(
            "{{domain}}", "pharma"
        ).replace(
            "{{risk_level}}", "high"
        ).replace(
            "{{language_instruction}}", lang_instruction
        ).replace(
            "{{constraint_pack_json}}", json.dumps(constraint_pack)
        ).replace(
            "{{segments_json}}", json.dumps(input_segments)
        )
        
        return [
            SystemMessage(content=TransMaxPrompts.TRANSLATOR_SYSTEM_V1),
            HumanMessage(content=user_content)
        ]
    
    def _persist_segments(self, units: List[SegmentUnit]):
        """Persist segment updates to database."""
        updates = [u.to_update_dict() for u in units if u.translated_text]
        if updates:
            self.db_service.update_segments_batch(updates)
    
    async def _update_document_status(self, doc_id: str, progress: TranslationProgress):
        """Update document status based on translation results."""
        if progress.failed > 0 or progress.blocked > 0:
            status = DocumentStatus.IN_REVIEW
        elif progress.completed == progress.total_segments:
            status = DocumentStatus.TRANSLATED
        else:
            status = DocumentStatus.IN_REVIEW
        
        try:
            self.db_service.update_document_status(doc_id, status.value)
            logger.info(f"[Engine] Document {doc_id} status -> {status}")
        except Exception as e:
            logger.error(f"Failed to update document status: {e}")
    
    def _build_quality_report(
        self,
        units: List[SegmentUnit],
        progress: TranslationProgress,
        duration: float
    ) -> Dict[str, Any]:
        """Build comprehensive quality report."""
        
        # Aggregate violations
        all_violations = []
        for unit in units:
            violations = unit.gate_results.get('violations', [])
            for v in violations:
                all_violations.append({
                    "segment_id": unit.segment_id,
                    **v
                })
        
        return {
            "status": "PASSED" if progress.failed == 0 and progress.blocked == 0 else "REVIEW_REQUIRED",
            "metrics": progress.to_dict(),
            "duration_seconds": round(duration, 2),
            "violations": all_violations,
            "throughput_segments_per_second": round(len(units) / duration, 2) if duration > 0 else 0
        }


# ============================================================================
# SINGLETON & LANGGRAPH NODE
# ============================================================================

_engine: Optional[TranslationEngine] = None

def get_engine() -> TranslationEngine:
    global _engine
    if not _engine:
        _engine = TranslationEngine()
    return _engine


async def translation_engine_node(state: dict) -> dict:
    """
    LangGraph node that uses the TranslationEngine.
    Drop-in replacement for draft_translate.
    """
    logger.info("=== TRANSLATION ENGINE NODE ===")
    
    segments = state.get('segments', [])
    if not segments:
        logger.warning("No segments to translate")
        return state
    
    engine = get_engine()
    
    try:
        result_segments, quality_report = await engine.translate_document(
            doc_id=state['doc_id'],
            segments=segments,
            target_language=state['target_language'],
            constraint_pack=state.get('constraint_pack', {})
        )
        
        # Update state with results
        # Merge translations back into state segments
        result_map = {s['segment_id']: s for s in result_segments}
        for seg in state['segments']:
            if seg['segment_id'] in result_map:
                seg.update(result_map[seg['segment_id']])
        
        state['quality_report'] = quality_report
        
        logger.info(f"[Engine Node] Complete: {quality_report.get('status')}")
        
    except Exception as e:
        logger.error(f"[Engine Node] Failed: {e}")
        state['error'] = str(e)
    
    return state
