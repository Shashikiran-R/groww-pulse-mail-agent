"""
Batch processor to backfill all pipeline stages for weeks 2026-W20 through 2026-W40.

For each week:
1. Loads raw reviews from data/raw/reviews_{week}.json
2. Runs DataPipeline to clean, normalise, filter spam/noise (retaining only > 10 words), enrich, and score sentiment
3. Runs ThemeClusterer to classify clean reviews into taxonomy themes using Groq (openai/gpt-oss-120b)
4. Saves:
   - data/cleaned/cleaned_{week}.json
   - data/enriched/enriched_{week}.json
   - data/classified/classified_{week}.json
"""

import sys
import json
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import config
from src.pipeline.pipeline import DataPipeline
from src.classification.clusterer import ThemeClusterer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("process_all_weeks")

def main():
    start_week = 20
    end_week = 40
    target_weeks = [f"2026-W{w:02d}" for w in range(start_week, end_week + 1)]

    logger.info(f"Targeting {len(target_weeks)} weeks from {target_weeks[0]} to {target_weeks[-1]}")

    pipeline = DataPipeline(config)
    clusterer = ThemeClusterer()

    summary = []

    for week in target_weeks:
        raw_path = Path(f"data/raw/reviews_{week}.json")
        if not raw_path.exists():
            logger.warning(f"Raw file {raw_path} not found! Skipping...")
            continue

        classified_path = Path(f"data/classified/classified_{week}.json")
        enriched_path = Path(f"data/enriched/enriched_{week}.json")
        cleaned_path = Path(f"data/cleaned/cleaned_{week}.json")

        # If already processed with valid > 10 words, skip
        if classified_path.exists() and enriched_path.exists() and cleaned_path.exists():
            try:
                with open(classified_path, "r", encoding="utf-8") as f:
                    existing_classified = json.load(f)
                if existing_classified and all(len(r.get("normalised_text", "").split()) > 10 for r in existing_classified):
                    logger.info(f"Week {week} already processed ({len(existing_classified)} clean reviews > 10 words). Skipping.")
                    summary.append({
                        "week": week,
                        "raw": 0,
                        "clean": len(existing_classified),
                        "classified": len(existing_classified),
                    })
                    continue
            except Exception:
                pass

        logger.info(f"=== Processing {week} ===")
        with open(raw_path, "r", encoding="utf-8") as f:
            raw_reviews = json.load(f)

        # Stage 1-6: Data Pipeline
        clean_reviews = pipeline.run(raw_reviews)

        # Stage 7: Theme Classification
        classified_reviews = []
        if clean_reviews:
            classified_reviews = clusterer.classify(clean_reviews)
            clusterer.save_classified(classified_reviews, week=week)

            # Also update enriched file with classified theme metadata
            enriched_path = Path(f"data/enriched/enriched_{week}.json")
            with open(enriched_path, "w", encoding="utf-8") as f:
                json.dump(classified_reviews, f, indent=2, ensure_ascii=False)

        summary.append({
            "week": week,
            "raw": len(raw_reviews),
            "clean": len(clean_reviews),
            "classified": len(classified_reviews),
        })

    logger.info("=== BATCH PROCESSING SUMMARY ===")
    for s in summary:
        logger.info(f"Week {s['week']}: Raw={s['raw']}, Clean (>10 words)={s['clean']}, Classified={s['classified']}")

    logger.info("Batch processing completed successfully.")

if __name__ == "__main__":
    main()
