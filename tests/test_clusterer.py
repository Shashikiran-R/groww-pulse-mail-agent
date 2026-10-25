"""
Tests for ThemeClusterer — LLM classification, theme ranking, and caching.

All LLM calls are mocked to avoid real API usage in tests.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.classification.clusterer import ThemeClusterer, _build_classification_prompt
from src.classification.taxonomy import THEME_TAXONOMY, VALID_THEMES, get_taxonomy_text


# ── Fixtures ──────────────────────────────────────────────────────────────

def _make_review(
    review_id: str,
    text: str,
    rating: int = 3,
    quality_flag: str = "clean",
    sentiment_label: str = "neutral",
    sentiment_score: float = 0.0,
    days_since_review: int = 5,
    helpfulness: float = 0.5,
    week: str = "2026-W40",
    **kwargs,
) -> dict:
    """Create a mock enriched review dict."""
    r = {
        "review_id": review_id,
        "text": text,
        "normalised_text": text.lower(),
        "original_text": text,
        "cleaned_text": text,
        "title": kwargs.get("title", ""),
        "rating": rating,
        "quality_flag": quality_flag,
        "sentiment_label": sentiment_label,
        "sentiment_score": sentiment_score,
        "days_since_review": days_since_review,
        "helpfulness": helpfulness,
        "week": week,
        "word_count": len(text.split()),
        "quote_candidacy_score": 0.5,
    }
    r.update(kwargs)
    return r


MOCK_REVIEWS = [
    _make_review("r1", "KYC process took 5 days very frustrating", rating=1, sentiment_label="strongly_negative", sentiment_score=-0.8, days_since_review=3, helpfulness=0.7),
    _make_review("r2", "UPI payment failed 3 times money debited", rating=2, sentiment_label="negative", sentiment_score=-0.5, days_since_review=5, helpfulness=0.4),
    _make_review("r3", "App crashes every time I open portfolio", rating=1, sentiment_label="strongly_negative", sentiment_score=-0.9, days_since_review=2, helpfulness=0.8),
    _make_review("r4", "Good app for mutual fund investing", rating=5, sentiment_label="strongly_positive", sentiment_score=0.7, days_since_review=10, helpfulness=0.2),
    _make_review("r5", "Withdrawal stuck for 7 days very bad", rating=1, sentiment_label="strongly_negative", sentiment_score=-0.8, days_since_review=4, helpfulness=0.6),
    _make_review("r6", "Tax report not showing capital gains", rating=2, sentiment_label="negative", sentiment_score=-0.4, days_since_review=8, helpfulness=0.3),
]

MOCK_LLM_RESPONSE = json.dumps([
    {"review_id": "r1", "theme": "Onboarding / KYC", "sub_theme": "KYC verification delays", "confidence": 0.95},
    {"review_id": "r2", "theme": "Payments / UPI", "sub_theme": "UPI failures", "confidence": 0.90},
    {"review_id": "r3", "theme": "App Performance / Bugs", "sub_theme": "Crashes", "confidence": 0.93},
    {"review_id": "r4", "theme": "Other", "sub_theme": "General satisfaction", "confidence": 0.70},
    {"review_id": "r5", "theme": "Withdrawals / Redemptions", "sub_theme": "Withdrawal delays", "confidence": 0.92},
    {"review_id": "r6", "theme": "Statements / Tax Reports", "sub_theme": "Capital gains report", "confidence": 0.85},
])


# ── Prompt Construction ──────────────────────────────────────────────────

class TestPromptConstruction:

    def test_classification_prompt_contains_taxonomy(self):
        """Prompt includes all 5 themes from the taxonomy."""
        system_prompt, _ = _build_classification_prompt(MOCK_REVIEWS[:2])
        for theme in THEME_TAXONOMY:
            assert theme in system_prompt

    def test_classification_prompt_contains_review_ids(self):
        """User prompt includes all review IDs from the batch."""
        _, user_prompt = _build_classification_prompt(MOCK_REVIEWS[:3])
        assert "r1" in user_prompt
        assert "r2" in user_prompt
        assert "r3" in user_prompt

    def test_classification_prompt_requests_json(self):
        """System prompt requests JSON array output."""
        system_prompt, _ = _build_classification_prompt(MOCK_REVIEWS[:1])
        assert "JSON array" in system_prompt

    def test_taxonomy_text_format(self):
        """Taxonomy text has numbered entries."""
        text = get_taxonomy_text()
        assert "1. Onboarding / KYC" in text
        assert "5. App Performance / Bugs" in text


# ── Classification ────────────────────────────────────────────────────────

class TestClassification:

    @patch("src.classification.clusterer.genai")
    def test_classify_assigns_themes(self, mock_genai):
        """All reviews get theme, sub_theme, and confidence after classification."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = MOCK_LLM_RESPONSE
        mock_client.models.generate_content.return_value = mock_response

        clusterer = ThemeClusterer(api_key="test-key", batch_size=10)
        reviews = [r.copy() for r in MOCK_REVIEWS]
        classified = clusterer.classify(reviews)

        for r in classified:
            assert "theme" in r, f"Review {r['review_id']} missing theme"
            assert "sub_theme" in r, f"Review {r['review_id']} missing sub_theme"
            assert "confidence" in r, f"Review {r['review_id']} missing confidence"
            assert r["theme"] in VALID_THEMES, f"Invalid theme: {r['theme']}"

    @patch("src.classification.clusterer.genai")
    def test_classify_skips_non_clean_reviews(self, mock_genai):
        """Reviews with quality_flag != 'clean' are not classified."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_client.models.generate_content.return_value = mock_response

        clusterer = ThemeClusterer(api_key="test-key", batch_size=10)

        reviews = [
            _make_review("x1", "spam review", quality_flag="spam"),
            _make_review("x2", "noise review", quality_flag="noise"),
        ]
        classified = clusterer.classify(reviews)
        assert len(classified) == 0

    @patch("src.classification.clusterer.genai")
    def test_classify_handles_malformed_json(self, mock_genai):
        """Malformed JSON from LLM is repaired via json_repair."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        # Malformed JSON (missing closing bracket)
        mock_response = MagicMock()
        mock_response.text = '[{"review_id": "r1", "theme": "Onboarding / KYC", "sub_theme": "KYC", "confidence": 0.9}]'
        mock_client.models.generate_content.return_value = mock_response

        clusterer = ThemeClusterer(api_key="test-key", batch_size=10)
        reviews = [_make_review("r1", "KYC issue")]
        classified = clusterer.classify(reviews)

        assert len(classified) == 1
        assert classified[0]["theme"] == "Onboarding / KYC"

    @patch("src.classification.clusterer.genai")
    def test_classify_unknown_theme_maps_to_other(self, mock_genai):
        """Unknown themes from LLM are mapped to 'Other'."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"review_id": "r1", "theme": "Random Theme", "sub_theme": "xyz", "confidence": 0.8}
        ])
        mock_client.models.generate_content.return_value = mock_response

        clusterer = ThemeClusterer(api_key="test-key", batch_size=10)
        reviews = [_make_review("r1", "Some review")]
        classified = clusterer.classify(reviews)

        assert classified[0]["theme"] == "Other"


# ── Theme Ranking ─────────────────────────────────────────────────────────

class TestThemeRanking:

    @patch("src.classification.clusterer.genai")
    def test_rank_themes_returns_sorted(self, mock_genai):
        """Themes are sorted by weighted_score descending."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        clusterer = ThemeClusterer(api_key="test-key")

        reviews = [
            _make_review("a1", "KYC problem", theme="Onboarding / KYC", sentiment_label="strongly_negative", sentiment_score=-0.8, days_since_review=2, helpfulness=0.9),
            _make_review("a2", "KYC delayed", theme="Onboarding / KYC", sentiment_label="negative", sentiment_score=-0.5, days_since_review=3, helpfulness=0.5),
            _make_review("a3", "App crash", theme="App Performance / Bugs", sentiment_label="negative", sentiment_score=-0.5, days_since_review=10, helpfulness=0.3),
        ]

        ranked = clusterer.rank_themes(reviews)

        assert len(ranked) == 2
        # "Onboarding / KYC" should rank higher due to recency and severity
        assert ranked[0]["theme"] == "Onboarding / KYC"
        assert ranked[0]["count"] == 2
        assert ranked[1]["theme"] == "App Performance / Bugs"
        assert ranked[1]["count"] == 1

    @patch("src.classification.clusterer.genai")
    def test_rank_themes_includes_sentiment_breakdown(self, mock_genai):
        """Each ranked theme has sentiment_breakdown with negative/positive/neutral."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        clusterer = ThemeClusterer(api_key="test-key")

        reviews = [
            _make_review("b1", "Bad UPI", theme="Payments / UPI", sentiment_label="negative"),
            _make_review("b2", "UPI ok", theme="Payments / UPI", sentiment_label="neutral"),
            _make_review("b3", "Good UPI", theme="Payments / UPI", sentiment_label="positive"),
        ]

        ranked = clusterer.rank_themes(reviews)

        assert len(ranked) == 1
        breakdown = ranked[0]["sentiment_breakdown"]
        assert "negative" in breakdown
        assert "positive" in breakdown
        assert "neutral" in breakdown
        # 1 negative, 1 neutral, 1 positive out of 3 = ~33.3% each
        assert abs(breakdown["negative"] - 33.3) < 1.0
        assert abs(breakdown["positive"] - 33.3) < 1.0
        assert abs(breakdown["neutral"] - 33.3) < 1.0

    @patch("src.classification.clusterer.genai")
    def test_rank_themes_weighted_score_formula(self, mock_genai):
        """Weighted score uses recency × sentiment_weight × helpfulness."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        clusterer = ThemeClusterer(api_key="test-key")

        reviews = [
            _make_review(
                "c1", "Test review",
                theme="Onboarding / KYC",
                sentiment_label="strongly_negative",
                days_since_review=5,
                helpfulness=0.8,
            ),
        ]

        ranked = clusterer.rank_themes(reviews)

        # Expected: (1/5) × 2.0 × 0.8 = 0.32
        expected_score = (1.0 / 5) * 2.0 * 0.8
        assert abs(ranked[0]["weighted_score"] - expected_score) < 0.01


# ── Batching ──────────────────────────────────────────────────────────────

class TestBatching:

    @patch("src.classification.clusterer.genai")
    def test_batching_splits_correctly(self, mock_genai):
        """Reviews are split into correct batch sizes."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        # Create 7 reviews, batch size 3 → should be 3 batches
        reviews = [
            _make_review(f"batch_{i}", f"Review text {i}")
            for i in range(7)
        ]

        # Return matching classifications for each batch call
        def side_effect(*args, **kwargs):
            response = MagicMock()
            # Parse the user prompt to find review IDs
            contents = args[0] if args else kwargs.get("contents", "")
            # Return empty array — we just want to verify batching works
            response.text = "[]"
            return response

        mock_client.models.generate_content.side_effect = side_effect

        clusterer = ThemeClusterer(api_key="test-key", batch_size=3)
        clusterer.classify(reviews)

        # Should have made 3 LLM calls (3+3+1 reviews)
        assert mock_client.models.generate_content.call_count == 3


# ── Caching ───────────────────────────────────────────────────────────────

class TestCaching:

    @patch("src.classification.clusterer.genai")
    def test_cached_reviews_not_reclassified(self, mock_genai):
        """Reviews already in cache are not sent to the LLM."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        clusterer = ThemeClusterer(api_key="test-key", batch_size=10)

        # Pre-populate cache
        clusterer._cache["cached_1"] = {
            "theme": "Payments / UPI",
            "sub_theme": "UPI failures",
            "confidence": 0.9,
        }

        reviews = [
            _make_review("cached_1", "UPI payment failed"),  # In cache
            _make_review("new_1", "New review about KYC"),    # Not in cache
        ]

        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"review_id": "new_1", "theme": "Onboarding / KYC", "sub_theme": "KYC", "confidence": 0.85}
        ])
        mock_client.models.generate_content.return_value = mock_response

        classified = clusterer.classify(reviews)

        # Cached review should have its cached values
        cached_r = next(r for r in classified if r["review_id"] == "cached_1")
        assert cached_r["theme"] == "Payments / UPI"
        assert cached_r["confidence"] == 0.9

        # Only 1 LLM call (for the new review)
        assert mock_client.models.generate_content.call_count == 1


# ── Groq Provider Tests ───────────────────────────────────────────────────

class TestGroqProvider:

    @patch("src.classification.clusterer.groq")
    def test_groq_classify_success(self, mock_groq):
        """Groq returns JSON object with classifications array and reviews get classified."""
        mock_client = MagicMock()
        mock_groq.Groq.return_value = mock_client

        mock_completion = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps({
            "classifications": [
                {"review_id": "r1", "theme": "Onboarding / KYC", "sub_theme": "KYC verification delays", "confidence": 0.95},
                {"review_id": "r2", "theme": "Payments / UPI", "sub_theme": "UPI failures", "confidence": 0.90},
            ]
        })
        mock_completion.choices = [MagicMock(message=mock_message)]
        mock_client.chat.completions.create.return_value = mock_completion

        clusterer = ThemeClusterer(api_key="gsk_test123", provider="groq", model="openai/gpt-oss-120b", batch_size=10)
        reviews = [
            _make_review("r1", "KYC took 5 days"),
            _make_review("r2", "UPI failed 3 times"),
        ]

        classified = clusterer.classify(reviews)

        assert len(classified) == 2
        assert classified[0]["theme"] == "Onboarding / KYC"
        assert classified[0]["sub_theme"] == "KYC verification delays"
        assert classified[0]["confidence"] == 0.95
        assert classified[0]["selected_quote"] is False
        assert classified[1]["theme"] == "Payments / UPI"

        # Verify groq client was called with expected model and json_object format
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "openai/gpt-oss-120b"
        assert call_kwargs["response_format"] == {"type": "json_object"}

    @patch("src.classification.clusterer.groq")
    def test_groq_reclassification_on_low_confidence(self, mock_groq):
        """Low confidence reviews trigger a second-pass reclassification."""
        mock_client = MagicMock()
        mock_groq.Groq.return_value = mock_client

        # First pass returns low confidence for r1
        first_pass = MagicMock()
        first_pass.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "classifications": [
                {"review_id": "r1", "theme": "Other", "sub_theme": "Unclear", "confidence": 0.4}
            ]
        })))]

        # Second pass returns higher confidence with context
        second_pass = MagicMock()
        second_pass.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "classifications": [
                {"review_id": "r1", "theme": "Onboarding / KYC", "sub_theme": "KYC delays", "confidence": 0.88}
            ]
        })))]

        mock_client.chat.completions.create.side_effect = [first_pass, second_pass]

        clusterer = ThemeClusterer(api_key="gsk_test", provider="groq", confidence_threshold=0.6)
        reviews = [_make_review("r1", "Verification is taking so long", title="KYC problem")]

        classified = clusterer.classify(reviews)

        assert len(classified) == 1
        assert classified[0]["theme"] == "Onboarding / KYC"
        assert classified[0]["confidence"] == 0.88
        assert mock_client.chat.completions.create.call_count == 2


# ── Storage Tests ─────────────────────────────────────────────────────────

class TestStorage:

    def test_save_classified_writes_json(self, tmp_path):
        """save_classified persists reviews grouped by week."""
        with patch("src.classification.clusterer.CACHE_DIR", tmp_path):
            clusterer = ThemeClusterer(api_key="test-key")
            reviews = [
                _make_review("r1", "KYC delay", theme="Onboarding / KYC", week="2026-W40"),
                _make_review("r2", "UPI error", theme="Payments / UPI", week="2026-W40"),
            ]

            saved_path = clusterer.save_classified(reviews, week="2026-W40")
            assert saved_path.exists()

            with open(saved_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert len(data) == 2
            assert data[0]["review_id"] == "r1"
            assert data[0]["theme"] == "Onboarding / KYC"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

