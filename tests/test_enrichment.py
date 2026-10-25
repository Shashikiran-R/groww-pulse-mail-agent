import pytest
from datetime import datetime, timezone
from src.pipeline.enrichment import ReviewEnricher

@pytest.fixture
def enricher():
    return ReviewEnricher()

def test_enrichment_week_and_age(enricher):
    reviews = [{"date": "2026-09-15T10:00:00+00:00", "thumbs_up": 10, "normalised_text": "this is a test review with many words in it"}]
    res = enricher.enrich_batch(reviews)
    assert res[0]["week"] == "2026-W38"
    assert "days_since_review" in res[0]
    assert res[0]["word_count"] == 10

def test_enrichment_version_bucketing(enricher):
    reviews = [{"app_version": "6.2.1-beta"}]
    res = enricher.enrich_batch(reviews)
    assert res[0]["version_bucket"] == "6.2.x"

def test_enrichment_helpfulness(enricher):
    reviews = [
        {"thumbs_up": 10},
        {"thumbs_up": 2},
        {"thumbs_up": 0}
    ]
    res = enricher.enrich_batch(reviews)
    assert res[0]["helpfulness"] == 1.0
    assert res[1]["helpfulness"] == 0.2
    assert res[2]["helpfulness"] == 0.0

def test_enrichment_quote_score(enricher):
    reviews = [{
        "normalised_text": "word " * 20, # 20 words
        "sentiment_score": -0.8,
        "thumbs_up": 100
    }]
    # max thumbs up will be 100
    res = enricher.enrich_batch(reviews)
    # word_count_score = 1.0 (20 is in [15,80])
    # sentiment_extremity = 0.8
    # helpfulness_score = 1.0 (1.0 > 0.3)
    # score = 0.4*1 + 0.4*0.8 + 0.2*1 = 0.4 + 0.32 + 0.2 = 0.92
    assert res[0]["quote_candidacy_score"] == pytest.approx(0.92)
