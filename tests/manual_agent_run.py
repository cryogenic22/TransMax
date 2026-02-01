import asyncio
import uuid
from app.agents.graph import workflow
from app.services.db_service import DatabaseService

async def run_test():
    print("Initializing Test...")
    
    # Mock constraints to avoid vector DB dependency if not populated
    # But wait, db_service.get_constraints is called in the node.
    # If vector table is empty, it returns empty list. That's fine.
    
    input_state = {
        "request_id": str(uuid.uuid4()),
        "source_language": "en",
        "target_language": "fr",
        "domain": "clinical",
        "audience": "patient",
        "content_blocks": [
            {"block_id": "b1", "content": "Possible side effects include headache and nausea.", "type": "paragraph"},
            {"block_id": "b2", "content": "Keep out of reach of children.", "type": "warning"}
        ],
        "segments": [],
        "constraint_pack": {},
        "draft_segments": [],
        "quality_report": {},
        "iteration_count": 0,
        "final_decision": "PENDING",
        "audit_trail_id": str(uuid.uuid4()),
        "error": None
    }
    
    print(f"Invoking Agent for Request: {input_state['request_id']}")
    
    app = workflow.compile()
    
    final_state = await app.ainvoke(input_state)
    
    print("\n\n=== FINAL OUTPUT ===")
    print(f"Decision: {final_state.get('final_decision')}")
    print(f"Quality Report: {final_state.get('quality_report')}")
    print("\nTranslations:")
    for seg in final_state.get('draft_segments', []):
        print(f"[{seg.get('segment_id')}] {seg.get('source_text')} -> {seg.get('target_text')}")
        
    if final_state.get('error'):
        print(f"\nERROR: {final_state['error']}")

if __name__ == "__main__":
    asyncio.run(run_test())
