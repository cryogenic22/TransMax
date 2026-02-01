import pytest
from app.services.language_packs.japanese import JapanesePack

def test_japanese_tokenizer_integration():
    """
    TMX-033: Verify Janome integration and token-based matching.
    """
    pack = JapanesePack()
    
    # Check Tokenizer is loaded
    assert pack.tokenizer is not None
    
    # Test True Positive
    # "薬を飲まないでください" (Please do not drink the medicine)
    text_tp = "薬を飲まないでください"
    violations = pack.check_variants(text_tp)
    assert len(violations) == 1
    assert "飲まない" in violations[0]['message']
    
    # Test False Positive Resistance (Concept check)
    # Ideally find a word that contains the characters but is different token.
    # Ex: "飲み" (Drink stem) is okay? (Not forbidden).
    text_ok = "薬を飲みます"
    violations = pack.check_variants(text_ok)
    assert len(violations) == 0

    # Test False Positive: "食べない" (Don't eat) vs "食べ" (Eat stem)
    text_tp_2 = "ご飯を食べない"
    assert len(pack.check_variants(text_tp_2)) == 1
    
    text_ok_2 = "ご飯を食べます"
    assert len(pack.check_variants(text_ok_2)) == 0

if __name__ == "__main__":
    test_japanese_tokenizer_integration()
    print("PASS test_japanese_tokenizer_integration")
