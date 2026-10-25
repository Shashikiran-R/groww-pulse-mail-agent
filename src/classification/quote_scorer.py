"""
Quote Scorer — Multi-criteria selection of the best verbatim quotes.

Selects the best 3 quotes for the weekly pulse report, enforcing
1 quote per top theme for coverage diversity.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class QuoteScorer:
    """
    Selects the best verbatim quotes for the pulse report.

    Scoring criteria (from architecture §3.3.4):
        - Quote candidacy score:  0.3 weight (pre-computed in enrichment)
        - Theme coverage:         0.3 weight (prefer quotes from different themes)
        - Sentiment extremity:    0.2 weight (strongly negative/positive more impactful)
        - Helpfulness:            0.1 weight (thumbs up / community validation)
        - Word count sweet spot:  0.1 weight (20-60 words ideal)

    Constraint: Exactly 1 quote per top theme.
    """

    def __init__(
        self,
        candidacy_weight: float = 0.3,
        theme_coverage_weight: float = 0.3,
        sentiment_weight: float = 0.2,
        helpfulness_weight: float = 0.1,
        word_count_weight: float = 0.1,
    ):
        self.candidacy_weight = candidacy_weight
        self.theme_coverage_weight = theme_coverage_weight
        self.sentiment_weight = sentiment_weight
        self.helpfulness_weight = helpfulness_weight
        self.word_count_weight = word_count_weight

    def _compute_word_count_score(self, word_count: int) -> float:
        """
        Compute word count score — sweet spot is 20-60 words.
        Returns 0-1 score.
        """
        if 20 <= word_count <= 60:
            return 1.0
        elif 15 <= word_count < 20 or 60 < word_count <= 80:
            return 0.7
        elif 10 <= word_count < 15 or 80 < word_count <= 100:
            return 0.4
        else:
            return 0.1

    def _compute_sentiment_extremity(self, sentiment_score: float) -> float:
        """
        Compute sentiment extremity as a 0-1 score.
        More extreme sentiment (positive or negative) scores higher.
        """
        return min(1.0, abs(sentiment_score) * 1.5)

    def _score_review(self, review: dict, theme_match: bool) -> float:
        """
        Compute the overall quote score for a single review.
        """
        candidacy = review.get("quote_candidacy_score", 0.0)
        theme_cov = 1.0 if theme_match else 0.0
        sentiment_ext = self._compute_sentiment_extremity(
            review.get("sentiment_score", 0.0)
        )
        helpfulness = review.get("helpfulness", 0.0)
        word_count = review.get("word_count", 0)
        wc_score = self._compute_word_count_score(word_count)

        total = (
            self.candidacy_weight * candidacy
            + self.theme_coverage_weight * theme_cov
            + self.sentiment_weight * sentiment_ext
            + self.helpfulness_weight * helpfulness
            + self.word_count_weight * wc_score
        )

        return total

    def select_quotes(
        self,
        reviews: list[dict],
        top_themes: list[dict],
        num_quotes: int = 3,
    ) -> list[dict]:
        """
        Select the best verbatim quotes.

        Constraint: 1 quote per top theme to ensure coverage diversity.

        Args:
            reviews: List of classified review dicts.
            top_themes: Ranked list of theme dicts (from ThemeClusterer.rank_themes).
            num_quotes: Number of quotes to select (default 3).

        Returns:
            List of review dicts marked with selected_quote=True,
            containing the original_text for verbatim quoting.
        """
        if not top_themes or not reviews:
            return []

        # Get the top N theme names
        target_themes = [t["theme"] for t in top_themes[:num_quotes]]

        logger.info(f"Selecting {num_quotes} quotes for themes: {target_themes}")

        selected_quotes = []
        used_review_ids = set()

        for theme_name in target_themes:
            # Get all reviews for this theme
            theme_reviews = [
                r for r in reviews
                if r.get("theme") == theme_name
                and r.get("review_id") not in used_review_ids
                and r.get("quality_flag") == "clean"
            ]

            if not theme_reviews:
                logger.warning(f"No reviews available for theme '{theme_name}'.")
                continue

            # Score each review for this theme
            scored = []
            for r in theme_reviews:
                # Must have some text to be quotable
                quote_text = r.get("original_text") or r.get("text", "")
                if not quote_text or len(quote_text.strip()) < 10:
                    continue

                score = self._score_review(r, theme_match=True)
                scored.append((score, r))

            if not scored:
                logger.warning(f"No quotable reviews for theme '{theme_name}'.")
                continue

            # Sort by score descending
            scored.sort(key=lambda x: x[0], reverse=True)

            # Select the best review for this theme
            best_score, best_review = scored[0]
            best_review["selected_quote"] = True
            best_review["quote_score"] = round(best_score, 4)
            selected_quotes.append(best_review)
            used_review_ids.add(best_review.get("review_id"))

            logger.info(
                f"  Theme '{theme_name}': selected review "
                f"'{best_review.get('review_id', '?')}' "
                f"(score={best_score:.3f}, "
                f"words={best_review.get('word_count', 0)}, "
                f"sentiment={best_review.get('sentiment_label', '?')})"
            )

        # If we didn't get enough quotes, fill from remaining reviews
        if len(selected_quotes) < num_quotes:
            remaining = [
                r for r in reviews
                if r.get("review_id") not in used_review_ids
                and r.get("quality_flag") == "clean"
            ]

            for r in remaining:
                if len(selected_quotes) >= num_quotes:
                    break

                quote_text = r.get("original_text") or r.get("text", "")
                if not quote_text or len(quote_text.strip()) < 10:
                    continue

                score = self._score_review(r, theme_match=False)
                r["selected_quote"] = True
                r["quote_score"] = round(score, 4)
                selected_quotes.append(r)
                used_review_ids.add(r.get("review_id"))

            if len(selected_quotes) < num_quotes:
                logger.warning(
                    f"Could only select {len(selected_quotes)}/{num_quotes} quotes."
                )

        logger.info(f"Selected {len(selected_quotes)} quotes total.")
        return selected_quotes
