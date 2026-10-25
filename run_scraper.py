from src.config import config
from src.ingestion.scraper import ReviewScraper
import logging

if __name__ == '__main__':
    scraper = ReviewScraper(
        app_id=config.APP_ID,
        lookback_weeks=1,  # Short lookback for testing
        app_store_id=config.APP_STORE_APP_ID,
        app_store_name=config.APP_STORE_APP_NAME,
        app_store_country=config.APP_STORE_COUNTRY
    )
    reviews = scraper.scrape()
    saved_paths = scraper.save(reviews)
    print(f"Saved {len(reviews)} reviews to {saved_paths}")
