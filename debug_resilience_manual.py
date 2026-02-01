import asyncio
from app.services.resilience import ResilienceService
import openai
from unittest.mock import MagicMock

class MockLLM:
    def __init__(self):
        self.calls = 0
    async def invoke(self, messages):
        self.calls += 1
        print(f"Call {self.calls}")
        if self.calls < 3:
             # Mock a response object that has 'request' attribute if needed, or just standard init
             # OpenAI exceptions usually take (message, response, body)
             # We rely on tenacity to just catch likely type check
             raise openai.RateLimitError(message="Rate limit hit", response=MagicMock(), body=None)
        return "success"

async def main():
    mock = MockLLM()
    try:
        print("Starting manual resilience test...")
        res = await ResilienceService.resilient_llm_call(mock.invoke, [])
        print(f"Final Result: {res}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
