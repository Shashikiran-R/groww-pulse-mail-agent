from __future__ import annotations

import sys
import json
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classification.clusterer import ThemeClusterer
from src.classification.quote_scorer import QuoteScorer
from src.generation.pulse_generator import PulseGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("generate_all_pulses")

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

    clusterer = ThemeClusterer()
    quote_scorer = QuoteScorer()
    pulse_generator = PulseGenerator()

    # Pre-load previous themes cache
    ranked_cache = {}

    for week in target_weeks:
        cf_path = Path(f"data/classified/classified_{week}.json")
        if not cf_path.exists():
            logger.warning(f"Classified file {cf_path} not found! Skipping...")
            continue

        with open(cf_path, "r", encoding="utf-8") as f:
            classified_reviews = json.load(f)

        top_themes = clusterer.rank_themes(classified_reviews)
        ranked_cache[week] = top_themes

        selected_quotes = quote_scorer.select_quotes(
            reviews=classified_reviews,
            top_themes=top_themes,
            num_quotes=3,
        )

        prev_week = get_prev_week(week)
        prev_themes = ranked_cache.get(prev_week)
        if not prev_themes and prev_week:
            prev_cf_path = Path(f"data/classified/classified_{prev_week}.json")
            if prev_cf_path.exists():
                try:
                    with open(prev_cf_path, "r", encoding="utf-8") as f:
                        prev_reviews = json.load(f)
                    prev_themes = clusterer.rank_themes(prev_reviews)
                except Exception:
                    prev_themes = None

        logger.info(f"Generating Pulse report for {week} (Themes: {len(top_themes)}, Quotes: {len(selected_quotes)})...")
        pulse_output = pulse_generator.generate(
            top_themes=top_themes[:3],
            selected_quotes=selected_quotes,
            week=week,
            previous_themes=prev_themes,
        )
        logger.info(f"Successfully generated pulse for {week}: valid={pulse_output.is_valid}")

    logger.info("All pulse reports generated successfully!")

if __name__ == "__main__":
    main()
