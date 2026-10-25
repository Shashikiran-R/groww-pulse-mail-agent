from datetime import datetime, timezone
import re

class ReviewEnricher:
    def enrich_batch(self, reviews: list[dict]) -> list[dict]:
        now = datetime.now(timezone.utc)
        
        # For helpfulness normalisation
        max_thumbs_up = 0
        for review in reviews:
            thumbs = review.get("thumbs_up", 0) or 0
            if thumbs > max_thumbs_up:
                max_thumbs_up = thumbs
                
        for review in reviews:
            # 5.6 Week assignment & 5.12 Review age
            date_str = review.get("date")
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str)
                    iso_year, iso_week, _ = dt.isocalendar()
                    review["week"] = f"{iso_year}-W{iso_week:02d}"
                    days_since = (now - dt).days
                    review["days_since_review"] = max(0, days_since)
                except ValueError:
                    review["week"] = None
                    review["days_since_review"] = 0
            else:
                review["week"] = None
                review["days_since_review"] = 0
                
            # 5.7 Word count
            text = review.get("normalised_text", "")
            word_count = len(text.split())
            review["word_count"] = word_count
            
            # 5.8 Has title
            title = review.get("title")
            review["has_title"] = bool(title and str(title).strip())
            
            # 5.9 Developer reply
            reply = review.get("reply_text")
            review["has_developer_reply"] = bool(reply and str(reply).strip())
            
            # 5.10 Version bucketing
            app_version = review.get("app_version")
            if app_version:
                m = re.match(r'^(\d+\.\d+)', str(app_version))
                if m:
                    review["version_bucket"] = f"{m.group(1)}.x"
                else:
                    review["version_bucket"] = str(app_version)
            else:
                review["version_bucket"] = None
                
            # 5.11 Helpfulness normalisation
            thumbs = review.get("thumbs_up", 0) or 0
            if max_thumbs_up > 0:
                helpfulness = thumbs / max_thumbs_up
            else:
                helpfulness = 0.0
            review["helpfulness"] = helpfulness
            
            # 5.13 Quote candidacy score
            word_count_score = 1.0 if 15 <= word_count <= 80 else 0.0
            sentiment_extremity = abs(review.get("sentiment_score", 0.0))
            helpfulness_score = 1.0 if helpfulness > 0.3 else 0.0
            
            quote_score = (0.4 * word_count_score) + (0.4 * sentiment_extremity) + (0.2 * helpfulness_score)
            review["quote_candidacy_score"] = min(1.0, max(0.0, quote_score))
            
        return reviews
