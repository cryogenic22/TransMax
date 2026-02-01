from fastapi import BackgroundTasks
from typing import Dict, Any

from app.agents.graph import app as agent_app

class QueueService:
    """
    Handles queuing of background translation jobs.
    Currently uses FastAPI BackgroundTasks (in-memory).
    """
    
    def enqueue_translation(self, state: Dict[str, Any], background_tasks: BackgroundTasks):
        """
        Enqueues the translation agent workflow.
        """
        background_tasks.add_task(self._run_agent, state)
        
    async def _run_agent(self, state: Dict[str, Any]):
        """
        Internal wrapper to run the agent graph.
        """
        try:
            print(f"Starting background job for Request ID: {state.get('request_id')}")
            await agent_app.ainvoke(state)
            print(f"Completed background job for Request ID: {state.get('request_id')}")
        except Exception as e:
            print(f"Error in background job {state.get('request_id')}: {e}")
            # In a real system, we'd update the DB job status to FAILED here if the graph didn't catch it.
