import os
import sys
import asyncio
import json

# Add project root to python path
sys.path.append(os.getcwd())

from app.agents.graph import app as agent_app

async def test_workflow():
    print("Initializing Workflow Test...")
    
    # Mock Input Data
    request_id = "test-req-001"
    
    # A simple pharma source text
    source_content = "The patient should take 10 mg of Aspirin daily. Do not exceed the recommended dose."
    
    initial_state = {
        "request_id": request_id,
        "source_language": "en",
        "target_language": "es",
        "domain": "pharma",
        "audience": "patient",
        "content_blocks": [
            {"block_id": "b1", "content": source_content}
        ],
        "iteration_count": 0
    }
    
    print(f"Invoking Agent Graph with payload:\n{json.dumps(initial_state, indent=2)}")
    print("-" * 50)
    
    try:
        final_state = await agent_app.ainvoke(initial_state)
        
        print("\n" + "-" * 50)
        print("Workflow Completed Successfully!")
        print("-" * 50)
        
        # Verify Key Outputs
        draft = final_state.get('draft_segments', [])
        print(f"Translation Output ({len(draft)} segments):")
        for seg in draft:
            print(f"[{seg['segment_id']}] -> {seg['target_text']}")
            
        report = final_state.get('quality_report', {})
        print(f"\nQuality Gate Decision: {report.get('summary', {}).get('status')}")
        
        if final_state.get("final_decision") == "PASS":
            print("Final Audit Decision: PASS ✅")
        else:
            print(f"Final Audit Decision: {final_state.get('final_decision')} ⚠️")
            
    except Exception as e:
        print(f"Workflow Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_workflow())
