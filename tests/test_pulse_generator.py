"""
Tests for PulseGenerator — Context assembly, LLM report generation,
output validation, quote integrity, and Markdown-to-HTML conversion.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.generation.pulse_generator import (
    PulseGenerator,
    PulseOutput,
    markdown_to_html,
    _format_stars,
    _format_date,
)

# ── Fixtures ──────────────────────────────────────────────────────────────

MOCK_TOP_THEMES = [
    {
        "theme": "Onboarding / KYC",
        "count": 142,
        "weighted_score": 4.85,
        "sentiment_breakdown": {"negative": 78.0, "positive": 12.0, "neutral": 10.0},
        "top_sub_themes": [
            {"sub_theme": "KYC verification delays", "count": 80},
            {"sub_theme": "Document upload issues", "count": 45},
        ],
    },
    {
        "theme": "App Performance / Bugs",
        "count": 89,
        "weighted_score": 3.92,
        "sentiment_breakdown": {"negative": 65.0, "positive": 20.0, "neutral": 15.0},
        "top_sub_themes": [
            {"sub_theme": "Crashes", "count": 50},
            {"sub_theme": "Slow loading", "count": 25},
        ],
    },
    {
        "theme": "Payments / UPI",
        "count": 67,
        "weighted_score": 3.21,
        "sentiment_breakdown": {"negative": 45.0, "positive": 40.0, "neutral": 15.0},
        "top_sub_themes": [
            {"sub_theme": "UPI failures", "count": 40},
            {"sub_theme": "SIP payments", "count": 18},
        ],
    },
]

MOCK_SELECTED_QUOTES = [
    {
        "review_id": "q1",
        "theme": "Onboarding / KYC",
        "original_text": "KYC process took 5 days! Very frustrating, transaction not going through.",
        "rating": 2,
        "author": "Rahul M.",
        "date": "2026-09-15T00:00:00Z",
        "selected_quote": True,
    },
    {
        "review_id": "q2",
        "theme": "App Performance / Bugs",
        "original_text": "App crashes every time I open my portfolio after the recent update.",
        "rating": 1,
        "author": "Priya S.",
        "date": "2026-09-16T00:00:00Z",
        "selected_quote": True,
    },
    {
        "review_id": "q3",
        "theme": "Payments / UPI",
        "original_text": "UPI payment failed and money was debited from account without being credited.",
        "rating": 1,
        "author": "Amit K.",
        "date": "2026-09-17T00:00:00Z",
        "selected_quote": True,
    },
]

SAMPLE_VALID_MARKDOWN = """# Groww Weekly Pulse — 2026-W40

**Executive Summary:** KYC verification delays surged this week causing significant user frustration, while crash reports spiked following the Android update.

## 📊 Top Themes

### 1. Onboarding / KYC (142 reviews, 78.0% negative) ↑
KYC processing times remain the primary friction point for new users. Delays of 3-7 days have blocked trading activity and driven severe negative sentiment.

### 2. App Performance / Bugs (89 reviews, 65.0% negative) →
App stability issues were concentrated around portfolio screen crashes. The v6.2.1 release appears to have introduced regression errors on newer devices.

### 3. Payments / UPI (67 reviews, 45.0% negative) ↓
UPI payment drop-offs saw improvement compared to last week. However, debit-without-credit incidents remain high during market opening hours.

## 💬 User Quotes

> ★★☆☆☆ — "KYC process took 5 days! Very frustrating, transaction not going through." — *Rahul M., Sep 15*

> ★☆☆☆☆ — "App crashes every time I open my portfolio after the recent update." — *Priya S., Sep 16*

> ★☆☆☆☆ — "UPI payment failed and money was debited from account without being credited." — *Amit K., Sep 17*

## 💡 Action Ideas

1. **[KYC]** Establish automated escalations with eKYC vendors for verifications exceeding 24 hours.
2. **[Bugs]** Roll out a hotfix addressing the null pointer crash on portfolio tab render.
3. **[UPI]** Implement instant in-app status check and automated refunds for unsettled transactions.
"""


# ── Context Assembly & Trends ─────────────────────────────────────────────

class TestContextAssembly:

    def test_compare_trends_with_previous_week(self):
        """Trends identify moves up (↑), down (↓), unchanged (→), and new (🆕)."""
        generator = PulseGenerator(api_key="test-key", provider="gemini")

        previous_themes = [
            {"theme": "Payments / UPI"},           # Was #1, now #3 (↓)
            {"theme": "Onboarding / KYC"},         # Was #2, now #1 (↑)
            {"theme": "Statements / Tax Reports"},  # Was #3, dropped out
        ]

        current = [
            {"theme": "Onboarding / KYC"},         # #1
            {"theme": "App Performance / Bugs"},   # #2, not in prev top 3 (🆕)
            {"theme": "Payments / UPI"},           # #3
        ]

        trends = generator.compare_trends(current, previous_themes)
        assert trends[0]["trend"] == "↑"
        assert trends[1]["trend"] == "🆕"
        assert trends[2]["trend"] == "↓"

    def test_compare_trends_without_previous_week(self):
        """When no previous themes exist, trend is empty string."""
        generator = PulseGenerator(api_key="test-key", provider="gemini")
        current = [{"theme": "Onboarding / KYC"}]
        trends = generator.compare_trends(current, None)
        assert trends[0]["trend"] == ""

    def test_assemble_context_structure(self):
        """Context assembly packs themes, quotes, and sentiment data."""
        generator = PulseGenerator(api_key="test-key", provider="gemini")
        ctx = generator.assemble_context(
            top_themes=MOCK_TOP_THEMES,
            selected_quotes=MOCK_SELECTED_QUOTES,
            week="2026-W40",
            previous_themes=None,
        )

        assert ctx["week"] == "2026-W40"
        assert "Onboarding / KYC" in ctx["themes_context"]
        assert "78.0% negative" in ctx["themes_context"]
        assert "Rahul M." in ctx["quotes_context"]
        assert "KYC process took 5 days" in ctx["quotes_context"]
        assert "Total clean reviews" in ctx["sentiment_context"]


# ── Output Validation & Quote Integrity ───────────────────────────────────

class TestValidation:

    def test_valid_output_passes(self):
        """A properly structured report passes all validation checks."""
        generator = PulseGenerator(api_key="test-key", provider="gemini")
        is_valid, errors = generator.validate_output(SAMPLE_VALID_MARKDOWN, MOCK_SELECTED_QUOTES)
        assert is_valid is True
        assert len(errors) == 0

    def test_missing_executive_summary_fails(self):
        """Report missing executive summary is flagged as invalid."""
        generator = PulseGenerator(api_key="test-key", provider="gemini")
        broken_md = SAMPLE_VALID_MARKDOWN.replace("**Executive Summary:**", "Summary:")
        is_valid, errors = generator.validate_output(broken_md, MOCK_SELECTED_QUOTES)
        assert is_valid is False
        assert any("Executive Summary" in e for e in errors)

    def test_missing_themes_fails(self):
        """Report with fewer than 3 theme headings is flagged as invalid."""
        generator = PulseGenerator(api_key="test-key", provider="gemini")
        # Remove two theme headings
        broken_md = SAMPLE_VALID_MARKDOWN.replace("### 2.", "2.").replace("### 3.", "3.")
        is_valid, errors = generator.validate_output(broken_md, MOCK_SELECTED_QUOTES)
        assert is_valid is False
        assert any("Expected 3 theme headings" in e for e in errors)

    def test_missing_quotes_fails(self):
        """Report with fewer than 3 blockquotes is flagged as invalid."""
        generator = PulseGenerator(api_key="test-key", provider="gemini")
        broken_md = SAMPLE_VALID_MARKDOWN.replace(">", "-")
        is_valid, errors = generator.validate_output(broken_md, MOCK_SELECTED_QUOTES)
        assert is_valid is False
        assert any("blockquotes" in e for e in errors)

    def test_quote_integrity_verifies_verbatim(self):
        """Verifies exact verbatim matching for selected quotes."""
        generator = PulseGenerator(api_key="test-key", provider="gemini")
        assert generator.check_quote_integrity(SAMPLE_VALID_MARKDOWN, MOCK_SELECTED_QUOTES) is True

        # When quote text is missing/paraphrased
        altered_md = SAMPLE_VALID_MARKDOWN.replace("KYC process took 5 days", "Verification was very slow")
        assert generator.check_quote_integrity(altered_md, MOCK_SELECTED_QUOTES) is False

    def test_enforce_quote_integrity_replaces_quotes(self):
        """enforce_quote_integrity replaces paraphrased quotes with exact verbatim text."""
        generator = PulseGenerator(api_key="test-key", provider="gemini")
        paraphrased_md = SAMPLE_VALID_MARKDOWN.replace(
            "KYC process took 5 days! Very frustrating, transaction not going through.",
            "I had a lot of KYC delay problems."
        )
        corrected_md = generator.enforce_quote_integrity(paraphrased_md, MOCK_SELECTED_QUOTES)
        assert "KYC process took 5 days! Very frustrating, transaction not going through." in corrected_md


# ── Markdown to HTML Conversion ───────────────────────────────────────────

class TestMarkdownToHtml:

    def test_markdown_to_html_wraps_in_template(self):
        """Produces full HTML document with styling and converted tags."""
        html = markdown_to_html(SAMPLE_VALID_MARKDOWN)
        assert "<!DOCTYPE html>" in html
        assert "<html>" in html
        assert "<style>" in html
        assert "<h1>Groww Weekly Pulse — 2026-W40</h1>" in html
        assert "<blockquote>" in html
        assert "<li>" in html


# ── Helpers ───────────────────────────────────────────────────────────────

class TestHelpers:

    def test_format_stars(self):
        assert _format_stars(1) == "★☆☆☆☆"
        assert _format_stars(3) == "★★★☆☆"
        assert _format_stars(5) == "★★★★★"
        assert _format_stars(None) == "★★★☆☆"

    def test_format_date(self):
        assert _format_date("2026-09-15T00:00:00Z") == "Sep 15"
        assert _format_date(None) == "Recent"


# ── Generation with Mocks ─────────────────────────────────────────────────

class TestPulseGeneration:

    @patch("src.generation.pulse_generator.groq")
    def test_generate_with_groq(self, mock_groq):
        """Full generation flow with Groq returns valid PulseOutput and persists files."""
        mock_client = MagicMock()
        mock_groq.Groq.return_value = mock_client

        mock_completion = MagicMock()
        mock_message = MagicMock()
        mock_message.content = SAMPLE_VALID_MARKDOWN
        mock_completion.choices = [MagicMock(message=mock_message)]
        mock_client.chat.completions.create.return_value = mock_completion

        test_week = "2099-W99"
        generator = PulseGenerator(api_key="gsk_test123", provider="groq", model="openai/gpt-oss-120b")
        try:
            output = generator.generate(
                top_themes=MOCK_TOP_THEMES,
                selected_quotes=MOCK_SELECTED_QUOTES,
                week=test_week,
            )

            assert isinstance(output, PulseOutput)
            assert output.week == test_week
            assert output.is_valid is True
            assert len(output.themes) == 3
            assert "Executive Summary" in output.markdown
            assert "<html>" in output.html

            # Verify files were saved
            md_file = Path(f"data/pulses/pulse_{test_week}.md")
            html_file = Path(f"data/pulses/pulse_{test_week}.html")
            assert md_file.exists()
            assert html_file.exists()
        finally:
            for p in [Path(f"data/pulses/pulse_{test_week}.md"), Path(f"data/pulses/pulse_{test_week}.html")]:
                if p.exists():
                    p.unlink()

    @patch("src.generation.pulse_generator.groq")
    def test_generate_reprompts_on_missing_section(self, mock_groq):
        """When first LLM response is missing executive summary, generator re-prompts and recovers."""
        mock_client = MagicMock()
        mock_groq.Groq.return_value = mock_client

        # First response is missing executive summary
        broken_response = SAMPLE_VALID_MARKDOWN.replace("**Executive Summary:**", "Summary:")
        # Second response is valid
        good_response = SAMPLE_VALID_MARKDOWN

        mock_msg1 = MagicMock(content=broken_response)
        mock_comp1 = MagicMock(choices=[MagicMock(message=mock_msg1)])
        mock_msg2 = MagicMock(content=good_response)
        mock_comp2 = MagicMock(choices=[MagicMock(message=mock_msg2)])

        mock_client.chat.completions.create.side_effect = [mock_comp1, mock_comp2]

        test_week = "2099-W98"
        generator = PulseGenerator(api_key="gsk_test123", provider="groq", model="openai/gpt-oss-120b")
        try:
            output = generator.generate(
                top_themes=MOCK_TOP_THEMES,
                selected_quotes=MOCK_SELECTED_QUOTES,
                week=test_week,
            )

            assert output.is_valid is True
            # Verified that chat completions was called twice (initial + reprompt)
            assert mock_client.chat.completions.create.call_count == 2
        finally:
            for p in [Path(f"data/pulses/pulse_{test_week}.md"), Path(f"data/pulses/pulse_{test_week}.html")]:
                if p.exists():
                    p.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
