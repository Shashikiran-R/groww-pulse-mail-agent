import pytest
from src.pipeline.language_filter import LanguageFilter

@pytest.fixture
def lang_filter():
    return LanguageFilter(confidence_threshold=0.8)

def test_english_review(lang_filter):
    review = {"normalised_text": "this is a great application"}
    res = lang_filter.filter(review)
    assert res["detected_language"] == "en"
    assert "quality_flag" not in res

def test_hinglish_review(lang_filter):
    review = {"normalised_text": "bahut badhiya app hai", "is_hinglish": True}
    res = lang_filter.filter(review)
    # the detected language might be hr or hi, but is_hinglish=True allows it
    assert "quality_flag" not in res

def test_non_english_high_confidence(lang_filter):
    review = {"normalised_text": "esta es una muy buena aplicación que me gusta mucho"}
    res = lang_filter.filter(review)
    assert res["detected_language"] == "es"
    assert res["quality_flag"] == "excluded_language"

def test_short_text_defaults_to_english(lang_filter):
    review = {"normalised_text": "very nice"}
    res = lang_filter.filter(review)
    assert res["detected_language"] == "en"
    assert res["language_confidence"] == 1.0
    assert "quality_flag" not in res
