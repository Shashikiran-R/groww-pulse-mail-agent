import json
import time
import logging
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from google_play_scraper import reviews, Sort

logger = logging.getLogger(__name__)

class ReviewScraper:
    def __init__(self, app_id: str, lookback_weeks: int = 12, rate_limit_delay: float = 1.0, 
                 app_store_id: int = None, app_store_name: str = None, app_store_country: str = 'in',
                 min_words: int = 10):
        """Initialise with target app ID, lookback window, and minimum word count."""
        self.app_id = app_id
        self.app_store_id = app_store_id
        self.app_store_name = app_store_name
        self.app_store_country = app_store_country
        self.lookback_weeks = lookback_weeks
        self.rate_limit_delay = rate_limit_delay
        self.min_words = min_words
        self.raw_data_dir = Path("data/raw")
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)

    def _get_existing_review_ids(self) -> set:
        existing_ids = set()
        for file_path in self.raw_data_dir.glob("reviews_*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for review in data:
                        if "review_id" in review:
                            existing_ids.add(review["review_id"])
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")
        return existing_ids

    def _map_review(self, raw: dict) -> dict:
        return {
            "review_id": raw.get("reviewId"),
            "author": raw.get("userName"),
            "rating": raw.get("score"),
            "title": None,  # Play Store reviews don't have a title
            "text": raw.get("content"),
            "date": raw.get("at").isoformat() + "Z" if raw.get("at") else None,
            "thumbs_up": raw.get("thumbsUpCount", 0),
            "app_version": raw.get("appVersion"),
            "reply_text": raw.get("replyContent"),
            "reply_date": raw.get("repliedAt").isoformat() + "Z" if raw.get("repliedAt") else None,
            "source": "playstore"
        }

    def _map_appstore_review(self, raw: dict) -> dict:
        # Parse updated date
        dt_str = raw.get("updated", {}).get("label")
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
            except Exception:
                dt = None
        else:
            dt = None
            
        review_id = raw.get("id", {}).get("label")
        
        return {
            "review_id": f"as:{review_id}",
            "author": raw.get("author", {}).get("name", {}).get("label"),
            "rating": int(raw.get("im:rating", {}).get("label", 0)),
            "title": raw.get("title", {}).get("label"),
            "text": raw.get("content", {}).get("label"),
            "date": dt.isoformat().replace("+00:00", "Z") if dt else None,
            "thumbs_up": 0,
            "app_version": raw.get("im:version", {}).get("label"),
            "reply_text": None,
            "reply_date": None,
            "source": "appstore"
        }

    def scrape(self) -> list[dict]:
        """
        Fetch all reviews within the lookback window.
        Returns list of raw review dicts matching the schema.
        Handles pagination via continuation_token.
        Deduplicates against existing data/raw/ files.
        """
        existing_ids = self._get_existing_review_ids()
        fetched_reviews = []
        
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(weeks=self.lookback_weeks)
        
        continuation_token = None
        
        logger.info(f"Starting scrape for {self.app_id}, cutoff date: {cutoff_date.isoformat()}")
        
        while True:
            result, continuation_token = reviews(
                self.app_id,
                continuation_token=continuation_token,
                count=200,
                sort=Sort.NEWEST
            )
            
            if not result:
                break
                
            batch_reviews = []
            reached_cutoff = False
            
            for raw_review in result:
                review_date = raw_review.get("at")
                if review_date:
                    # Make aware if naive
                    if review_date.tzinfo is None:
                        review_date = review_date.replace(tzinfo=timezone.utc)
                    if review_date < cutoff_date:
                        reached_cutoff = True
                        break
                        
                review_id = raw_review.get("reviewId")
                content = raw_review.get("content") or ""
                if self.min_words and len(content.split()) <= self.min_words:
                    continue
                if review_id not in existing_ids:
                    mapped = self._map_review(raw_review)
                    batch_reviews.append(mapped)
                    existing_ids.add(review_id)
            
            fetched_reviews.extend(batch_reviews)
            logger.info(f"Fetched {len(batch_reviews)} new reviews in this batch. Total fetched: {len(fetched_reviews)}")
            
            if len(batch_reviews) == 0:
                consecutive_empty = getattr(self, "_consec_empty", 0) + 1
                self._consec_empty = consecutive_empty
                if consecutive_empty >= 3:
                    logger.info("Encountered 3 consecutive empty/duplicate batches. Ending Play Store pagination.")
                    break
            else:
                self._consec_empty = 0

            if reached_cutoff or not continuation_token:
                break
                
            time.sleep(self.rate_limit_delay)
            
        logger.info(f"Play Store scrape completed. Total new reviews: {len(fetched_reviews)}")
        
        # Scrape App Store reviews via iTunes RSS Feed
        if self.app_store_id and self.app_store_country:
            logger.info(f"Starting App Store scrape for ID {self.app_store_id}")
            app_store_reviews_fetched = 0
            
            for page in range(1, 11): # Apple limits to 10 pages for JSON RSS
                url = f"https://itunes.apple.com/{self.app_store_country}/rss/customerreviews/page={page}/id={self.app_store_id}/sortby=mostrecent/json"
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code != 200:
                        logger.warning(f"App Store scrape returned status {response.status_code} on page {page}")
                        break
                        
                    data = response.json()
                    entries = data.get('feed', {}).get('entry', [])
                    if not entries:
                        break
                        
                    reached_cutoff = False
                    for raw_review in entries:
                        mapped = self._map_appstore_review(raw_review)
                        dt_str = mapped.get("date")
                        if dt_str:
                            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                            if dt < cutoff_date:
                                reached_cutoff = True
                                continue
                                
                        text = mapped.get("text") or ""
                        if self.min_words and len(text.split()) <= self.min_words:
                            continue
                        if mapped["review_id"] not in existing_ids:
                            fetched_reviews.append(mapped)
                            existing_ids.add(mapped["review_id"])
                            app_store_reviews_fetched += 1
                            
                    if reached_cutoff:
                        logger.info(f"Reached cutoff date on page {page}")
                        break
                        
                    time.sleep(self.rate_limit_delay)
                except Exception as e:
                    logger.error(f"Error scraping App Store on page {page}: {e}")
                    break
                    
            logger.info(f"App Store scrape completed. Total new reviews: {app_store_reviews_fetched}")
        return fetched_reviews

    def save(self, reviews: list[dict]) -> list[Path]:
        """
        Persist reviews to data/raw/reviews_{week}.json.
        Returns list of paths to the saved files.
        """
        grouped_reviews = {}
        
        for review in reviews:
            # Parse date string to get ISO week
            date_str = review.get("date")
            if date_str:
                # Replace 'Z' with '+00:00' to parse ISO string correctly
                date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                iso_calendar = date_obj.isocalendar()
                year = iso_calendar[0]
                week = iso_calendar[1]
                week_str = f"{year}-W{week:02d}"
            else:
                week_str = "unknown_week"
                
            if week_str not in grouped_reviews:
                grouped_reviews[week_str] = []
            grouped_reviews[week_str].append(review)
            
        saved_paths = []
        for week_str, week_reviews in grouped_reviews.items():
            file_path = self.raw_data_dir / f"reviews_{week_str}.json"
            
            existing_week_reviews = []
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        existing_week_reviews = json.load(f)
                except Exception as e:
                    logger.error(f"Error reading existing file {file_path}: {e}")
            
            all_week_reviews = existing_week_reviews + week_reviews
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(all_week_reviews, f, indent=2, ensure_ascii=False)
                
            saved_paths.append(file_path)
            logger.info(f"Saved {len(week_reviews)} new reviews to {file_path}")
            
        return saved_paths
