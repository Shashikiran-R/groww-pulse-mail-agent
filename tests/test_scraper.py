import pytest
from unittest.mock import patch
from src.ingestion.scraper import ReviewScraper
from datetime import datetime, timezone, timedelta
import json

@pytest.fixture
def scraper(tmp_path):
    s = ReviewScraper(app_id="com.example.app", lookback_weeks=1, rate_limit_delay=0)
    s.raw_data_dir = tmp_path
    return s

def test_map_review(scraper):
    raw_review = {
        "reviewId": "test_id",
        "userName": "Test User",
        "score": 4,
        "content": "Great app",
        "at": datetime(2026, 10, 4, 12, 0, 0),
        "thumbsUpCount": 10,
        "appVersion": "1.0",
        "replyContent": "Thanks!",
        "repliedAt": datetime(2026, 10, 5, 12, 0, 0)
    }
    
    mapped = scraper._map_review(raw_review)
    assert mapped["review_id"] == "test_id"
    assert mapped["author"] == "Test User"
    assert mapped["rating"] == 4
    assert mapped["title"] is None
    assert mapped["text"] == "Great app"
    assert mapped["date"] == "2026-10-04T12:00:00Z"
    assert mapped["thumbs_up"] == 10
    assert mapped["app_version"] == "1.0"
    assert mapped["reply_text"] == "Thanks!"
    assert mapped["reply_date"] == "2026-10-05T12:00:00Z"

@patch('src.ingestion.scraper.reviews')
def test_scrape_deduplication(mock_reviews, scraper):
    now = datetime.now(timezone.utc)
    mock_reviews.return_value = (
        [
            {"reviewId": "id1", "at": now, "score": 5, "content": "this is review one with more than ten words for testing deduplication properly"},
            {"reviewId": "id2", "at": now, "score": 4, "content": "this is review two with more than ten words for testing deduplication properly"},
        ],
        None
    )
    
    # Pre-populate existing id2
    with open(scraper.raw_data_dir / "reviews_2026-W40.json", "w") as f:
        json.dump([{"review_id": "id2"}], f)
        
    fetched = scraper.scrape()
    assert len(fetched) == 1
    assert fetched[0]["review_id"] == "id1"

@patch('src.ingestion.scraper.reviews')
def test_scrape_filters_short_reviews(mock_reviews, scraper):
    now = datetime.now(timezone.utc)
    mock_reviews.return_value = (
        [
            {"reviewId": "short_1", "at": now, "score": 5, "content": "short review only four words"},
            {"reviewId": "long_1", "at": now, "score": 5, "content": "this is a sufficiently long review with more than ten words inside it"},
        ],
        None
    )
    fetched = scraper.scrape()
    assert len(fetched) == 1
    assert fetched[0]["review_id"] == "long_1"

def test_save(scraper):
    reviews_to_save = [
        {"review_id": "id1", "date": "2026-09-30T10:00:00Z"},
        {"review_id": "id2", "date": "2026-10-01T10:00:00Z"}
    ]
    paths = scraper.save(reviews_to_save)
    assert len(paths) == 1
    assert paths[0].name == "reviews_2026-W40.json"
    
    with open(paths[0], "r") as f:
        saved_data = json.load(f)
        assert len(saved_data) == 2
