import json
import logging
from pathlib import Path
from collections import defaultdict
from src.pipeline.cleaner import TextCleaner
from src.pipeline.normaliser import TextNormaliser
from src.pipeline.language_filter import LanguageFilter
from src.pipeline.spam_filter import SpamFilter
from src.pipeline.sentiment import SentimentAnalyser
from src.pipeline.enrichment import ReviewEnricher

logger = logging.getLogger(__name__)

class DataPipeline:
    def __init__(self, config):
        self.config = config
        self.cleaner = TextCleaner()
        self.normaliser = TextNormaliser(config.ABBREVIATIONS)
        self.lang_filter = LanguageFilter(config.LANGUAGE_CONFIDENCE_THRESHOLD)
        min_words = getattr(config, 'MIN_REVIEW_WORDS', 10)
        self.spam_filter = SpamFilter(config.MIN_REVIEW_LENGTH, config.SPAM_SIMILARITY_THRESHOLD, min_words=min_words)
        self.sentiment_analyser = SentimentAnalyser(config.SENTIMENT_WEIGHTS, getattr(config, 'EMOJI_SENTIMENT_MAP', {}))
        self.enricher = ReviewEnricher()
        
    def run(self, raw_reviews: list[dict]) -> list[dict]:
        logger.info(f"Pipeline started with {len(raw_reviews)} raw reviews.")
        
        stage_3_reviews = []
        for review in raw_reviews:
            r1 = self.cleaner.clean(review)
            r2 = self.normaliser.normalise(r1)
            if r2:
                r3 = self.lang_filter.filter(r2)
                stage_3_reviews.append(r3)
                
        stage_4_reviews = self.spam_filter.filter_batch(stage_3_reviews)
        enriched_reviews = self.enricher.enrich_batch(stage_4_reviews)
        
        final_reviews = []
        for review in enriched_reviews:
            final_review = self.sentiment_analyser.analyse(review)
            final_reviews.append(final_review)
            
        self._save_outputs(final_reviews)
        
        clean_reviews = [r for r in final_reviews if r.get("quality_flag") == "clean"]
        logger.info(f"Pipeline completed. Yielded {len(clean_reviews)} clean enriched reviews.")
        
        return clean_reviews
        
    def _save_outputs(self, reviews: list[dict]):
        cleaned_dir = Path("data/cleaned")
        enriched_dir = Path("data/enriched")
        cleaned_dir.mkdir(parents=True, exist_ok=True)
        enriched_dir.mkdir(parents=True, exist_ok=True)
        
        by_week = defaultdict(list)
        for r in reviews:
            week = r.get("week") or "unknown_week"
            by_week[week].append(r)
            
        for week, week_reviews in by_week.items():
            cleaned_path = cleaned_dir / f"cleaned_{week}.json"
            with open(cleaned_path, "w", encoding="utf-8") as f:
                json.dump(week_reviews, f, indent=2, ensure_ascii=False)
                
            clean_enriched = [r for r in week_reviews if r.get("quality_flag") == "clean"]
            if clean_enriched:
                enriched_path = enriched_dir / f"enriched_{week}.json"
                with open(enriched_path, "w", encoding="utf-8") as f:
                    json.dump(clean_enriched, f, indent=2, ensure_ascii=False)
