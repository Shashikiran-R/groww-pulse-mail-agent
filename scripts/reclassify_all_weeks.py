from __future__ import annotations

import sys
import json
import logging
from collections import defaultdict
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classification.clusterer import ThemeClusterer, classify_heuristic
from src.classification.quote_scorer import QuoteScorer
from src.generation.pulse_generator import PulseGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("reclassify_all_weeks")


def get_prev_week(week_str: str) -> str | None:
    try:
        parts = week_str.split("-W")
        year = int(parts[0])
        w = int(parts[1])
        if w > 1:
            return f"{year}-W{w-1:02d}"
        else:
            return f"{year-1}-W52"
    except Exception:
        return None


def main():
    start_week = 20
    end_week = 40
    target_weeks = [f"2026-W{w:02d}" for w in range(start_week, end_week + 1)]

    logger.info(f"Re-classifying reviews for {len(target_weeks)} weeks ({target_weeks[0]} to {target_weeks[-1]})...")

    # Initialize fresh clusterer without stale cache
    clusterer = ThemeClusterer()
    clusterer._cache = {}

    quote_scorer = QuoteScorer()
    pulse_generator = PulseGenerator()

    overall_theme_counts = defaultdict(int)
    total_reviews = 0

    ranked_cache = {}

    for week in target_weeks:
        enriched_path = Path(f"data/enriched/enriched_{week}.json")
        if not enriched_path.exists():
            logger.warning(f"File {enriched_path} not found! Skipping...")
            continue

        with open(enriched_path, "r", encoding="utf-8") as f:
            reviews = json.load(f)

        clean_reviews = [
            r for r in reviews
            if r.get("quality_flag") == "clean" and len(r.get("normalised_text", r.get("text", "")).split()) > 10
        ]

        if not clean_reviews:
            logger.warning(f"No clean reviews > 10 words for {week}")
            continue

        # Classify using ThemeClusterer (hybrid ML + LLM)
        classified_reviews = clusterer.classify(clean_reviews)

        # Count themes
        for r in classified_reviews:
            overall_theme_counts[r.get("theme", "Other")] += 1
            total_reviews += 1

        # Save classified file
        classified_path = Path(f"data/classified/classified_{week}.json")
        clusterer.save_classified(classified_reviews, week=week)

        # Save enriched file with updated theme fields
        with open(enriched_path, "w", encoding="utf-8") as f:
            json.dump(classified_reviews, f, indent=2, ensure_ascii=False)

        # Generate Pulse Report for this week
        top_themes = clusterer.rank_themes(classified_reviews)
        ranked_cache[week] = top_themes

        selected_quotes = quote_scorer.select_quotes(
            reviews=classified_reviews,
            top_themes=top_themes,
            num_quotes=3,
        )

        prev_week = get_prev_week(week)
        prev_themes = ranked_cache.get(prev_week)

        pulse_output = pulse_generator.generate(
            top_themes=top_themes[:3],
            selected_quotes=selected_quotes,
            week=week,
            previous_themes=prev_themes,
        )

        logger.info(
            f"[{week}] Classified {len(classified_reviews)} reviews | "
            f"Top 3: {[t['theme'] for t in top_themes[:3]]} | "
            f"Pulse valid: {pulse_output.is_valid}"
        )

    logger.info("=" * 60)
    logger.info(f"TOTAL REVIEWS CLASSIFIED ACROSS {len(target_weeks)} WEEKS: {total_reviews}")
    logger.info("THEME BREAKDOWN:")
    for theme, count in sorted(overall_theme_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / total_reviews * 100) if total_reviews else 0.0
        logger.info(f"  {theme:<35}: {count:5d} ({pct:5.1f}%)")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
