import pytest
from src.pipeline.spam_filter import SpamFilter

@pytest.fixture
def spam_filter():
    return SpamFilter()

def test_clean_review(spam_filter):
    reviews = [{"normalised_text": "this is a very good working app with great features and smooth performance", "rating": 5}]
    res = spam_filter.filter_batch(reviews)
    assert res[0]["quality_flag"] == "clean"

def test_noise_ten_words_or_fewer(spam_filter):
    # Exactly 10 words -> noise
    reviews = [{"normalised_text": "one two three four five six seven eight nine ten", "rating": 5}]
    res = spam_filter.filter_batch(reviews)
    assert res[0]["quality_flag"] == "noise"
    assert "Text too short" in res[0]["quality_reason"]

def test_noise_short_text(spam_filter):
    reviews = [{"normalised_text": "ok", "rating": 5}]
    res = spam_filter.filter_batch(reviews)
    assert res[0]["quality_flag"] == "noise"

def test_noise_emoji_only(spam_filter):
    reviews = [{"normalised_text": "", "emojis": ["😊", "🔥"], "rating": 5}]
    res = spam_filter.filter_batch(reviews)
    assert res[0]["quality_flag"] == "noise"

def test_spam_incentivised(spam_filter):
    reviews = [{"normalised_text": "5 star for reward give me money and extra coins for review", "rating": 5}]
    res = spam_filter.filter_batch(reviews)
    assert res[0]["quality_flag"] == "spam"

def test_mismatch_rating_text(spam_filter):
    reviews = [{"normalised_text": "this is the worst app ever terrible scam completely useless and pathetic service", "rating": 5}]
    res = spam_filter.filter_batch(reviews)
    assert res[0]["quality_flag"] == "mismatch"

def test_duplicate_reviews(spam_filter):
    reviews = [
        {"normalised_text": "this is a very specific and long review about the app"},
        {"normalised_text": "this is a very specific and long review about the app"}
    ]
    res = spam_filter.filter_batch(reviews)
    assert res[0]["quality_flag"] == "clean"
    assert res[1]["quality_flag"] == "spam"

def test_preserves_existing_flag(spam_filter):
    reviews = [{"normalised_text": "hola mundo muy bien", "quality_flag": "excluded_language"}]
    res = spam_filter.filter_batch(reviews)
    assert res[0]["quality_flag"] == "excluded_language"
