
from langchain_openai import ChatOpenAI
from app.core.config import settings

_llm = None

def get_llm():
    """
    Singleton factory for the LLM instance.
    Uses centralized settings.
    """
    global _llm
    if not _llm:
        if not settings.enable_live_llm_inference:
            from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
            from langchain_core.messages import AIMessage
            
            # Simulated responses for testing
            _llm = GenericFakeChatModel(messages=iter([
                AIMessage(content='{"segments": [{"segment_id": "1", "target_text": "Translated (Mock)"}]}')
            ]))
        else:
            _llm = ChatOpenAI(
                model=settings.default_gpt_model, 
                temperature=0,
                api_key=settings.openai_api_key
            )
    return _llm
