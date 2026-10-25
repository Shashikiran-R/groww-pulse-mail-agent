import pytest
from src.pipeline.sentiment import SentimentAnalyser

@pytest.fixture
def analyser():
    emoji_map = {"😡": -0.8, "👍": 0.7}
    return SentimentAnalyser(weights=(0.4, 0.4, 0.2), emoji_map=emoji_map)

def test_sentiment_clean_review(analyser):
    review = {
        "quality_flag": "clean",
        "rating": 5,
        "normalised_text": "this app is amazing and very good",
        "emojis": ["👍"]
    }
    res = analyser.analyse(review)
    assert "sentiment_score" in res
    assert res["sentiment_score"] > 0
    assert res["sentiment_label"] in ["positive", "strongly_positive"]

def test_sentiment_skips_noise(analyser):
    review = {
        "quality_flag": "noise",
        "rating": 1,
        "normalised_text": "bad",
    }
    res = analyser.analyse(review)
    assert "sentiment_score" not in res

def test_sentiment_negative(analyser):
    review = {
        "quality_flag": "clean",
        "rating": 1,
        "normalised_text": "worst terrible app hate it",
        "emojis": ["😡"]
    }
    res = analyser.analyse(review)
    assert res["sentiment_score"] < -0.5
    assert res["sentiment_label"] == "strongly_negative"
