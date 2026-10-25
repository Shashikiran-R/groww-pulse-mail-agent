from datetime import datetime, timezone, timedelta
from src.ingestion.scraper import ReviewScraper
from src.config import config

scraper = ReviewScraper(
    app_id=config.APP_ID, 
    lookback_weeks=12,
    app_store_id=config.APP_STORE_APP_ID,
    app_store_name=config.APP_STORE_APP_NAME,
    app_store_country=config.APP_STORE_COUNTRY
)

existing = scraper._get_existing_review_ids()
print(f"Existing IDs: {len(existing)}")

now = datetime.now(timezone.utc)
cutoff_date = now - timedelta(weeks=12)
print(f"Cutoff: {cutoff_date}")

import requests
url = f"https://itunes.apple.com/in/rss/customerreviews/page=1/id=1404871703/sortby=mostrecent/json"
data = requests.get(url).json()
entries = data.get('feed', {}).get('entry', [])
for i, raw_review in enumerate(entries[:5]):
    mapped = scraper._map_appstore_review(raw_review)
    print(f"\nEntry {i}")
    print(f"Mapped ID: {mapped['review_id']}")
    print(f"Mapped Date: {mapped['date']}")
    dt_str = mapped.get("date")
    if dt_str:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        print(f"Parsed DT: {dt}, < cutoff? {dt < cutoff_date}")
    
    print(f"In existing? {mapped['review_id'] in existing}")
