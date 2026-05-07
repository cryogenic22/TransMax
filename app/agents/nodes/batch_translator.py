"""
TransMax Batch Translator Node
Expert-engineered concurrent LLM processing with deterministic quality gates.

Architecture:
1. Segments are batched (5-10 per batch) for optimal LLM throughput
2. Batches are processed concurrently using asyncio.gather()
3. Quality gates run at segment-level immediately after each batch
4. Failed segments are retried with exponential backoff
5. TM exact matches bypass LLM entirely
"""
import asyncio
import logging
import json
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm import get_llm
from app.services.json_parser import RobustParser
from app.services.quality_gate import QualityGateService
from app.services.db_service import DatabaseService
from app.agents.prompts import PromptRegistry
from app.models.database import SegmentStatus
from app.core.constants import SubstitutionType

logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 5  # Segments per LLM call - smaller = faster, more parallelism
MAX_CONCURRENT_BATCHES = 3  # Limit concurrent LLM calls to avoid rate limits
MAX_RETRIES = 2
RETRY_DELAY_BASE = 1.0  # seconds


class BatchTranslator:
    """
    Handles concurrent batch translation with quality gates.
    Designed for pharma-grade deterministic processing.
    """
    
    def __init__(self):
        self._db_service = None
        self._quality_gate = None
        self._llm = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)
    
    @property
    def db_service(self):
        if not self._db_service:
            self._db_service = DatabaseService()
        return self._db_service
    
    @property
    def quality_gate(self):
        if not self._quality_gate:
            self._quality_gate = QualityGateService()
        return self._quality_gate
    
    @property
    def llm(self):
        if not self._llm:
            self._llm = get_llm()
        return self._llm
    
    async def translate_document(
        self, 
        segments: List[Dict[str, Any]], 
        target_language: str,
        constraint_pack: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Main entry point. Translates all segments with concurrent batching.
        
        Returns:
            - Updated segments list with translations
            - Quality report summary
        """
        logger.info(f"Starting batch translation: {len(segments)} segments -> {target_language}")
        
        # Step 1: Separate TM matches from LLM-needed segments
        to_translate, tm_resolved = self._separate_tm_matches(segments)
        logger.info(f"TM Resolved: {len(tm_resolved)}, Need LLM: {len(to_translate)}")
        
        # Step 2: Persist TM matches immediately
        if tm_resolved:
            self.db_service.update_segments_batch(tm_resolved)
            logger.info(f"Persisted {len(tm_resolved)} TM exact matches")
        
        # Step 3: Create batches for LLM translation
        batches = self._create_batches(to_translate, BATCH_SIZE)
        logger.info(f"Created {len(batches)} batches of ~{BATCH_SIZE} segments each")
        
        # Step 4: Process batches concurrently
        all_results = []
        all_errors = []
        
        if batches:
            tasks = [
                self._process_batch_with_retry(
                    batch, 
                    batch_idx, 
                    target_language, 
                    constraint_pack,
                    segments  # Full list for context
                )
                for batch_idx, batch in enumerate(batches)
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for idx, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch {idx} failed: {result}")
                    all_errors.append({"batch": idx, "error": str(result)})
                else:
                    all_results.extend(result)
        
        # Step 5: Persist all LLM translations
        if all_results:
            self.db_service.update_segments_batch(all_results)
            logger.info(f"Persisted {len(all_results)} LLM translations")
        
        # Step 6: Update in-memory segments with results
        result_map = {r['segment_id']: r for r in all_results + tm_resolved}
        for seg in segments:
            if seg['segment_id'] in result_map:
                seg['translated_text'] = result_map[seg['segment_id']].get('translated_text', '')
                seg['gate_results'] = result_map[seg['segment_id']].get('gate_results', {})
        
        # Step 7: Compile quality report
        quality_report = {
            "total_segments": len(segments),
            "tm_resolved": len(tm_resolved),
            "llm_translated": len(all_results),
            "errors": len(all_errors),
            "error_details": all_errors
        }
        
        logger.info(f"Translation complete: {quality_report}")
        return segments, quality_report
    
    def _separate_tm_matches(
        self, 
        segments: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Separates segments that have TM exact matches from those needing LLM."""
        to_translate = []
        tm_updates = []
        
        for seg in segments:
            tm_match = seg.get('tm_match')
            if tm_match and tm_match.get('type') == SubstitutionType.TM_EXACT:
                translation = tm_match['target']
                tm_updates.append({
                    "segment_id": seg['segment_id'],
                    "translated_text": translation,
                    "status": str(SegmentStatus.TRANSLATED),
                    "translation_source": SubstitutionType.TM_EXACT.value,
                    "match_score": 1.0,
                    "gate_results": {"tm_exact": True, "violations": []}
                })
            else:
                to_translate.append(seg)
        
        return to_translate, tm_updates
    
    def _create_batches(
        self, 
        segments: List[Dict[str, Any]], 
        batch_size: int
    ) -> List[List[Dict[str, Any]]]:
        """Splits segments into batches for concurrent processing."""
        return [
            segments[i:i + batch_size] 
            for i in range(0, len(segments), batch_size)
        ]
    
    async def _process_batch_with_retry(
        self,
        batch: List[Dict[str, Any]],
        batch_idx: int,
        target_language: str,
        constraint_pack: Dict[str, Any],
        all_segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Processes a single batch with retry logic and rate limiting."""
        
        async with self._semaphore:  # Limit concurrent LLM calls
            for attempt in range(MAX_RETRIES + 1):
                try:
                    logger.info(f"Batch {batch_idx}: Attempt {attempt + 1}, {len(batch)} segments")
                    
                    # Translate batch
                    results = await self._translate_batch(
                        batch, target_language, constraint_pack, all_segments
                    )
                    
                    # Run quality gates on each result
                    for result in results:
                        seg_data = next(
                            (s for s in batch if s['segment_id'] == result['segment_id']), 
                            None
                        )
                        if seg_data:
                            gate_results = self.quality_gate.run_checks(
                                source_text=seg_data.get('source_text', ''),
                                translated_text=result.get('translated_text', ''),
                                constraint_pack=constraint_pack
                            )
                            result['gate_results'] = gate_results
                    
                    logger.info(f"Batch {batch_idx}: Success, {len(results)} results")
                    return results
                    
                except Exception as e:
                    logger.warning(f"Batch {batch_idx} attempt {attempt + 1} failed: {e}")
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
                    else:
                        raise
        
        return []  # Should not reach here
    
    async def _translate_batch(
        self,
        batch: List[Dict[str, Any]],
        target_language: str,
        constraint_pack: Dict[str, Any],
        all_segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Calls LLM for a single batch and parses results."""
        
        # Prepare input with context
        input_segments = self._prepare_batch_payload(batch, all_segments)
        
        # Build prompt
        messages = self._build_prompt(input_segments, target_language, constraint_pack)
        
        # Call LLM (async)
        response = await self.llm.ainvoke(messages)
        
        # Parse response
        data = RobustParser.parse(response.content)
        
        # Extract translations
        results = []
        draft_segments = data.get('segments', [])
        
        for draft in draft_segments:
            seg_id = draft.get('segment_id') or draft.get('id')
            trans_text = draft.get('target_text') or draft.get('translated_text')
            
            if seg_id and trans_text:
                results.append({
                    "segment_id": seg_id,
                    "translated_text": trans_text,
                    "status": str(SegmentStatus.TRANSLATED),
                    "translation_source": "llm_batch_v2"
                })
        
        return results
    
    def _prepare_batch_payload(
        self,
        batch: List[Dict[str, Any]],
        all_segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prepares segment payload with prev/next context for LLM."""
        seg_map = {s['segment_id']: i for i, s in enumerate(all_segments)}
        input_segments = []
        
        for seg in batch:
            idx = seg_map.get(seg['segment_id'])
            payload = {
                "id": seg["segment_id"],
                "text": seg["source_text"]
            }
            if idx is not None:
                if idx > 0:
                    payload["prev_context"] = all_segments[idx - 1]['source_text'][:200]
                if idx < len(all_segments) - 1:
                    payload["next_context"] = all_segments[idx + 1]['source_text'][:200]
            input_segments.append(payload)
        
        return input_segments
    
    def _build_prompt(
        self,
        input_segments: List[Dict[str, Any]],
        target_language: str,
        constraint_pack: Dict[str, Any]
    ) -> list:
        """Builds LLM prompt messages."""
        prompt = PromptRegistry.load("translator")
        user_content = prompt.user.replace(
            "{{target_language}}", target_language
        ).replace(
            "{{audience}}", "general"
        ).replace(
            "{{domain}}", "pharma"
        ).replace(
            "{{risk_level}}", "high"
        ).replace(
            "{{language_instruction}}", ""
        ).replace(
            "{{constraint_pack_json}}", json.dumps(constraint_pack)
        ).replace(
            "{{segments_json}}", json.dumps(input_segments)
        )

        return [
            SystemMessage(content=prompt.system),
            HumanMessage(content=user_content)
        ]


# Singleton instance
_batch_translator = None

def get_batch_translator() -> BatchTranslator:
    global _batch_translator
    if not _batch_translator:
        _batch_translator = BatchTranslator()
    return _batch_translator


async def batch_translate_node(state: dict) -> dict:
    """
    LangGraph node that uses the BatchTranslator for concurrent processing.
    Drop-in replacement for the old draft_translate node.
    """
    logger.info("=== BATCH TRANSLATE NODE ===")
    
    segments = state.get('segments', [])
    if not segments:
        logger.warning("No segments to translate")
        return state
    
    translator = get_batch_translator()
    
    try:
        updated_segments, quality_report = await translator.translate_document(
            segments=segments,
            target_language=state['target_language'],
            constraint_pack=state.get('constraint_pack', {})
        )
        
        state['segments'] = updated_segments
        state['quality_report'] = quality_report
        
        logger.info(f"Batch translation complete. Report: {quality_report}")
        
    except Exception as e:
        logger.error(f"Batch translation failed: {e}")
        state['error'] = str(e)
    
    return state
