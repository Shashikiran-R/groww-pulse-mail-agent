"""
Tests for QuoteScorer — multi-criteria quote selection.
"""

import pytest
from src.classification.quote_scorer import QuoteScorer


# ── Fixtures ──────────────────────────────────────────────────────────────

def _make_review(
    review_id: str,
    text: str,
    theme: str = "App Performance / Bugs",
    rating: int = 2,
    quality_flag: str = "clean",
    sentiment_label: str = "negative",
    sentiment_score: float = -0.5,
    helpfulness: float = 0.5,
    word_count: int = 25,
    quote_candidacy_score: float = 0.6,
    **kwargs,
) -> dict:
    """Create a mock classified review dict."""
    r = {
        "review_id": review_id,
        "text": text,
        "normalised_text": text.lower(),
        "original_text": text,
        "cleaned_text": text,
        "title": kwargs.get("title", ""),
        "rating": rating,
        "quality_flag": quality_flag,
        "theme": theme,
        "sub_theme": kwargs.get("sub_theme", ""),
        "confidence": kwargs.get("confidence", 0.9),
        "sentiment_label": sentiment_label,
        "sentiment_score": sentiment_score,
        "helpfulness": helpfulness,
        "word_count": word_count,
        "quote_candidacy_score": quote_candidacy_score,
        "days_since_review": kwargs.get("days_since_review", 5),
    }
    r.update(kwargs)
    return r


MOCK_TOP_THEMES = [
    {
        "theme": "Onboarding / KYC",
        "count": 50,
        "weighted_score": 5.0,
        "sentiment_breakdown": {"negative": 70, "positive": 10, "neutral": 20},
    },
    {
        "theme": "Payments / UPI",
        "count": 35,
        "weighted_score": 3.5,
        "sentiment_breakdown": {"negative": 60, "positive": 20, "neutral": 20},
    },
    {
        "theme": "App Performance / Bugs",
        "count": 30,
        "weighted_score": 3.0,
        "sentiment_breakdown": {"negative": 80, "positive": 5, "neutral": 15},
    },
]


MOCK_REVIEWS = [
    # KYC reviews
    _make_review("kyc_1", "KYC verification took 10 days and I still cannot trade. This is completely unacceptable.", theme="Onboarding / KYC", sentiment_score=-0.8, helpfulness=0.9, word_count=18, quote_candidacy_score=0.8),
    _make_review("kyc_2", "Document upload keeps failing for PAN card", theme="Onboarding / KYC", sentiment_score=-0.4, helpfulness=0.3, word_count=8, quote_candidacy_score=0.3),
    _make_review("kyc_3", "eKYC process is too slow, took 5 attempts to complete Aadhaar verification", theme="Onboarding / KYC", sentiment_score=-0.6, helpfulness=0.5, word_count=14, quote_candidacy_score=0.6),

    # UPI reviews
    _make_review("upi_1", "UPI payment failed three times today. Money was debited from my bank but not credited to Groww wallet. Very frustrating experience.", theme="Payments / UPI", sentiment_score=-0.7, helpfulness=0.8, word_count=25, quote_candidacy_score=0.7),
    _make_review("upi_2", "SIP auto-pay stopped working since last month update", theme="Payments / UPI", sentiment_score=-0.5, helpfulness=0.4, word_count=9, quote_candidacy_score=0.4),

    # App Performance reviews
    _make_review("perf_1", "App crashes every single time I try to check my portfolio. The latest update completely broke the app and I cannot do any trading.", theme="App Performance / Bugs", sentiment_score=-0.9, helpfulness=0.7, word_count=28, quote_candidacy_score=0.9),
    _make_review("perf_2", "Very slow loading times on the dashboard", theme="App Performance / Bugs", sentiment_score=-0.3, helpfulness=0.2, word_count=7, quote_candidacy_score=0.3),
]


# ── Quote Selection ───────────────────────────────────────────────────────

class TestQuoteSelection:

    def test_selects_one_quote_per_theme(self):
        """Exactly 1 quote per top theme is selected."""
        scorer = QuoteScorer()
        quotes = scorer.select_quotes(MOCK_REVIEWS, MOCK_TOP_THEMES, num_quotes=3)

        assert len(quotes) == 3

        quote_themes = [q["theme"] for q in quotes]
        assert len(set(quote_themes)) == 3, "Each quote should be from a different theme"

        for theme_info in MOCK_TOP_THEMES:
            assert theme_info["theme"] in quote_themes

    def test_selected_quotes_have_marker(self):
        """Selected quotes are marked with selected_quote=True."""
        scorer = QuoteScorer()
        quotes = scorer.select_quotes(MOCK_REVIEWS, MOCK_TOP_THEMES, num_quotes=3)

        for q in quotes:
            assert q.get("selected_quote") is True
            assert "quote_score" in q

    def test_prefers_higher_scoring_reviews(self):
        """For each theme, the highest-scoring review is selected."""
        scorer = QuoteScorer()
        quotes = scorer.select_quotes(MOCK_REVIEWS, MOCK_TOP_THEMES, num_quotes=3)

        # For KYC: kyc_1 should win (highest candidacy, helpfulness, sentiment)
        kyc_quote = next(q for q in quotes if q["theme"] == "Onboarding / KYC")
        assert kyc_quote["review_id"] == "kyc_1"

        # For App Performance: perf_1 should win
        perf_quote = next(q for q in quotes if q["theme"] == "App Performance / Bugs")
        assert perf_quote["review_id"] == "perf_1"

    def test_handles_empty_theme(self):
        """Gracefully handles themes with no available reviews."""
        scorer = QuoteScorer()

        # Only KYC reviews, but top themes include all 3
        kyc_only_reviews = [r for r in MOCK_REVIEWS if r["theme"] == "Onboarding / KYC"]
        quotes = scorer.select_quotes(kyc_only_reviews, MOCK_TOP_THEMES, num_quotes=3)

        # Should select what's available (1 KYC quote)
        assert len(quotes) >= 1
        assert quotes[0]["theme"] == "Onboarding / KYC"


# ── Scoring Logic ─────────────────────────────────────────────────────────

class TestScoringLogic:

    def test_word_count_sweet_spot(self):
        """Word count score is highest for 20-60 words."""
        scorer = QuoteScorer()

        assert scorer._compute_word_count_score(30) == 1.0   # Sweet spot
        assert scorer._compute_word_count_score(50) == 1.0   # Sweet spot
        assert scorer._compute_word_count_score(15) == 0.7   # Near sweet spot
        assert scorer._compute_word_count_score(75) == 0.7   # Near sweet spot
        assert scorer._compute_word_count_score(5) == 0.1    # Too short
        assert scorer._compute_word_count_score(150) == 0.1  # Too long

    def test_sentiment_extremity(self):
        """More extreme sentiment scores higher."""
        scorer = QuoteScorer()

        assert scorer._compute_sentiment_extremity(-0.9) > scorer._compute_sentiment_extremity(-0.3)
        assert scorer._compute_sentiment_extremity(0.9) > scorer._compute_sentiment_extremity(0.3)
        assert scorer._compute_sentiment_extremity(-0.9) == scorer._compute_sentiment_extremity(0.9)
        assert scorer._compute_sentiment_extremity(0.0) == 0.0

    def test_score_review_combines_criteria(self):
        """Overall score combines all criteria with correct weights."""
        scorer = QuoteScorer()

        review = _make_review(
            "s1", "Test review text",
            quote_candidacy_score=0.8,
            sentiment_score=-0.6,
            helpfulness=0.5,
            word_count=30,
        )

        score_with_theme = scorer._score_review(review, theme_match=True)
        score_without_theme = scorer._score_review(review, theme_match=False)

        # Theme match adds 0.3 weight
        assert score_with_theme > score_without_theme
        assert abs(score_with_theme - score_without_theme - 0.3) < 0.01


# ── Edge Cases ────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_no_reviews(self):
        """Returns empty list when no reviews provided."""
        scorer = QuoteScorer()
        quotes = scorer.select_quotes([], MOCK_TOP_THEMES, num_quotes=3)
        assert quotes == []

    def test_no_themes(self):
        """Returns empty list when no top themes provided."""
        scorer = QuoteScorer()
        quotes = scorer.select_quotes(MOCK_REVIEWS, [], num_quotes=3)
        assert quotes == []

    def test_skips_non_clean_reviews(self):
        """Non-clean reviews are not selected as quotes."""
        scorer = QuoteScorer()

        reviews = [
            _make_review("spam_1", "Great app 5 stars reward", theme="Onboarding / KYC", quality_flag="spam"),
            _make_review("clean_1", "KYC verification very slow", theme="Onboarding / KYC", quality_flag="clean"),
        ]

        top_themes = [{"theme": "Onboarding / KYC", "count": 2, "weighted_score": 1.0, "sentiment_breakdown": {}}]
        quotes = scorer.select_quotes(reviews, top_themes, num_quotes=1)

        assert len(quotes) == 1
        assert quotes[0]["review_id"] == "clean_1"

    def test_skips_short_text_reviews(self):
        """Reviews with very short text are not quotable."""
        scorer = QuoteScorer()

        reviews = [
            _make_review("short_1", "Bad", theme="Onboarding / KYC"),  # Too short (<10 chars)
            _make_review("good_1", "KYC process is very slow and frustrating experience", theme="Onboarding / KYC"),
        ]

        top_themes = [{"theme": "Onboarding / KYC", "count": 2, "weighted_score": 1.0, "sentiment_breakdown": {}}]
        quotes = scorer.select_quotes(reviews, top_themes, num_quotes=1)

        assert len(quotes) == 1
        assert quotes[0]["review_id"] == "good_1"

    def test_quotes_preserve_original_text(self):
        """Selected quotes contain original_text for verbatim quoting."""
        scorer = QuoteScorer()
        quotes = scorer.select_quotes(MOCK_REVIEWS, MOCK_TOP_THEMES, num_quotes=3)

        for q in quotes:
            assert "original_text" in q
            assert len(q["original_text"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
